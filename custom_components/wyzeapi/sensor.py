"""Platform for sensor integration."""

from collections.abc import Callable
import datetime
import json
import logging
from typing import Any

from wyzeapy import Wyzeapy
from wyzeapy.services.camera_service import Camera
from wyzeapy.services.irrigation_service import Irrigation, IrrigationService, Zone
from wyzeapy.services.lock_service import Lock
from wyzeapy.services.switch_service import Switch, SwitchUsageService

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)

from .const import (
    CAMERA_UPDATED,
    CONF_CLIENT,
    DOMAIN,
    LOCK_UPDATED,
    RESET_BUTTON_PRESSED,
)
from .irrigation import WyzeIrrigationEntity, WyzeIrrigationZoneEntity
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
CAMERAS_WITH_BATTERIES = ["WVOD1", "HL_WCO2", "AN_RSCW", "GW_BE1"]
OUTDOOR_PLUGS = ["WLPPO"]


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Any], bool], None],
) -> None:
    """This function sets up the config_entry.

    :param hass: Home Assistant instance
    :param config_entry: The current config_entry
    :param async_add_entities: This function adds entities to the config_entry
    :return:
    """
    _LOGGER.debug("""Creating new WyzeApi sensor component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]

    # Get the list of locks so that we can create lock and keypad battery sensors
    lock_service = await client.lock_service
    camera_service = await client.camera_service
    switch_usage_service = await client.switch_usage_service
    irrigation_service = await client.irrigation_service

    locks = await lock_service.get_locks()
    sensors = []
    for lock in locks:
        sensors.append(WyzeLockBatterySensor(lock, WyzeLockBatterySensor.LOCK_BATTERY))
        sensors.append(
            WyzeLockBatterySensor(lock, WyzeLockBatterySensor.KEYPAD_BATTERY)
        )

    cameras = await camera_service.get_cameras()
    sensors.extend(
        [
            WyzeCameraBatterySensor(camera)
            for camera in cameras
            if camera.product_model in CAMERAS_WITH_BATTERIES
        ]
    )

    plugs = await switch_usage_service.get_switches()
    for plug in plugs:
        if plug.product_model in OUTDOOR_PLUGS:
            sensors.append(WyzePlugEnergySensor(plug, switch_usage_service))
            sensors.append(WyzePlugDailyEnergySensor(plug))

    # Get all irrigation devices
    irrigation_devices = await irrigation_service.get_irrigations()

    # Create sensor entities for each irrigation device
    for device in irrigation_devices:
        # Update the device to get its properties
        device = await irrigation_service.update(device)
        # Diagnostic + status sensors (device level)
        sensors.extend(
            [
                WyzeIrrigationRSSI(irrigation_service, device),
                WyzeIrrigationIP(irrigation_service, device),
                WyzeIrrigationSSID(irrigation_service, device),
                WyzeIrrigationCurrentZone(irrigation_service, device),
                WyzeIrrigationNextScheduledRun(irrigation_service, device),
                WyzeIrrigationActiveSchedules(irrigation_service, device),
                WyzeIrrigationLastRunDuration(irrigation_service, device),
            ]
        )
        # Per-zone status sensors
        for zone in device.zones:
            if zone.enabled:
                sensors.extend(
                    [
                        WyzeIrrigationZoneSmartDuration(irrigation_service, device, zone),
                        WyzeIrrigationZoneRemainingTime(irrigation_service, device, zone),
                        WyzeIrrigationZoneLastWatered(irrigation_service, device, zone),
                    ]
                )

    async_add_entities(sensors, True)


class WyzeLockBatterySensor(SensorEntity):
    """Representation of a Wyze Lock or Lock Keypad Battery."""

    @property
    def enabled(self):
        """Return if the sensor is enabled."""
        return self._enabled

    LOCK_BATTERY = "lock_battery"
    KEYPAD_BATTERY = "keypad_battery"

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_should_poll = False

    def __init__(self, lock, battery_type) -> None:
        """Initialize the sensor."""
        self._enabled = None
        self._lock = lock
        self._battery_type = battery_type
        # make the battery unavailable by default, this will be toggled after the first update from the battery entity that
        # has battery data.
        self._available = False

    @callback
    def handle_lock_update(self, lock: Lock) -> None:
        """Helper function to Enable lock when Keypad has a battery.

        Make it avaliable when either the lock battery or keypad battery exists.
        """
        self._lock = lock
        if self._lock.raw_dict.get("power") and self._battery_type == self.LOCK_BATTERY:
            self._available = True
        if (
            self._lock.raw_dict.get("keypad", {}).get("power")
            and self._battery_type == self.KEYPAD_BATTERY
        ):
            if self.enabled is False:
                self.enabled = True
            self._available = True
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add listener on startup."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LOCK_UPDATED}-{self._lock.mac}",
                self.handle_lock_update,
            )
        )

    @property
    def name(self) -> str:
        """Name of the Sensor."""
        battery_type = self._battery_type.replace("_", " ").title()
        return f"{self._lock.nickname} {battery_type}"

    @property
    def unique_id(self):
        """Unique ID of the sensor."""
        return f"{self._lock.nickname}.{self._battery_type}"

    @property
    def available(self) -> bool:
        """Return if the sensor is available."""
        return self._available

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled."""
        if self._battery_type == self.KEYPAD_BATTERY:
            # The keypad battery may not be available if the lock has no keypad
            return False
        # The battery voltage will always be available for the lock
        return True

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._lock.mac)},
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._lock.mac,
                )
            },
            "name": f"{self._lock.nickname}.{self._battery_type}",
        }

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device model": f"{self._lock.product_model}.{self._battery_type}",
        }

    @property
    def native_value(self):
        """Return the state of the device."""
        if self._battery_type == self.LOCK_BATTERY:
            return str(self._lock.raw_dict.get("power"))
        if self._battery_type == self.KEYPAD_BATTERY:
            return str(self._lock.raw_dict.get("keypad", {}).get("power"))
        return 0

    @enabled.setter
    def enabled(self, value):
        self._enabled = value


class WyzeCameraBatterySensor(SensorEntity):
    """Representation of a Wyze Camera Battery."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_should_poll = False

    def __init__(self, camera) -> None:
        """Initialize the sensor."""
        self._camera = camera

    @callback
    def handle_camera_update(self, camera: Camera) -> None:
        """Handle camera updates."""
        self._camera = camera
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Add listener on startup."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{CAMERA_UPDATED}-{self._camera.mac}",
                self.handle_camera_update,
            )
        )

    @property
    def name(self) -> str:
        """Return the entity name."""
        return f"{self._camera.nickname} Battery"

    @property
    def unique_id(self):
        """Unique ID of the sensor."""
        return f"{self._camera.nickname}.battery"

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._camera.mac)},
            "connections": {
                (
                    dr.CONNECTION_NETWORK_MAC,
                    self._camera.mac,
                )
            },
            "name": self._camera.nickname,
            "model": self._camera.product_model,
            "manufacturer": "WyzeLabs",
        }

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device model": f"{self._camera.product_model}.battery",
        }

    @property
    def native_value(self):
        """Return the value of the sensor."""
        return self._camera.device_params.get("electricity")


class WyzePlugEnergySensor(RestoreSensor):
    """Respresents an Outdoor Plug Total Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3
    _attr_should_poll = False
    _attr_name = "Total Energy Usage"
    _previous_hour = None
    _previous_value = None
    _past_hours_previous_value = None
    _current_value = 0
    _past_hours_value = 0
    _hourly_energy_usage_added = 0

    def __init__(
        self, switch: Switch, switch_usage_service: SwitchUsageService
    ) -> None:
        """Initialize an energy sensor."""
        self._switch = switch
        self._switch_usage_service = switch_usage_service
        self._switch.usage_history = None  # type: ignore[attr-defined]

    @property
    def unique_id(self):
        """Get the unique ID of the sensor."""
        return f"{self._switch.nickname}.energy-{self._switch.mac}"

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._switch.mac)},
            "name": self._switch.nickname,
        }

    def update_energy(self):
        """Update the energy sensor."""
        _now = int(datetime.datetime.now(datetime.UTC).hour)
        self._hourly_energy_usage_added = 0

        if (
            self._switch.usage_history and len(self._switch.usage_history) > 0
        ):  # Confirm there is data
            _raw_data = self._switch.usage_history
            _LOGGER.debug(_raw_data)
            _current_day_list = json.loads(_raw_data[0]["data"])
            if _now == 0:  # Handle rolling to the next UTC day
                self._past_hours_value = _current_day_list[23] / 1000
                if len(_raw_data) > 1:  # New Day's value
                    _next_day_list = json.loads(_raw_data[1]["data"])
                    self._current_value = _next_day_list[_now] / 1000
                else:
                    self._current_value = 0
            else:
                self._past_hours_value = _current_day_list[_now - 1] / 1000
                self._current_value = _current_day_list[_now] / 1000

            # Set inital values to current values on startup.
            # Has to be done after we check for current or next UTC day
            if self._previous_hour is None:
                self._previous_hour = _now
            if self._past_hours_previous_value is None:
                self._past_hours_previous_value = self._past_hours_value
            if self._previous_value is None:
                self._previous_value = self._current_value

            if _now != self._previous_hour:  # New Hour
                if self._past_hours_value > self._previous_value:
                    self._hourly_energy_usage_added = (
                        self._past_hours_value - self._previous_value
                    )
                self._hourly_energy_usage_added += self._current_value
                self._previous_value = self._current_value
                self._previous_hour = _now
                self._past_hours_previous_value = self._past_hours_value

            else:  # Current Hour
                if self._current_value > self._previous_value:
                    self._hourly_energy_usage_added += round(
                        self._current_value - self._previous_value, 3
                    )
                    self._previous_value = self._current_value

                if self._past_hours_value > self._past_hours_previous_value:
                    self._hourly_energy_usage_added += round(
                        self._past_hours_value - self._past_hours_previous_value, 3
                    )
                    self._past_hours_previous_value = self._past_hours_value

            _LOGGER.debug(
                "Total Value Added to device %s is %s",
                self._switch.mac,
                self._hourly_energy_usage_added,
            )

        return self._hourly_energy_usage_added

    @callback
    def async_update_callback(self, switch: Switch):
        """Update the sensor's state."""
        self._switch = switch
        self.update_energy()
        self._attr_native_value += self._hourly_energy_usage_added
        self.async_write_ha_state()

    @callback
    def reset_energy_use(self, switch: Switch):
        """Reset the Energy Usage."""
        _LOGGER.debug("Resetting Usage of %s to 0", self._switch.nickname)
        self._switch = switch
        self._attr_native_value = 0
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register Updater for the sensor and get previous data."""
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value
        else:
            self._attr_native_value = 0
        self._switch.callback_function = self.async_update_callback
        self._switch_usage_service.register_updater(
            self._switch, 120
        )  # Every 2 minutes seems to work fine, probably could be longer
        await self._switch_usage_service.start_update_manager()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{RESET_BUTTON_PRESSED}-{self._switch.mac}",
                self.reset_energy_use,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove updater."""
        self._switch_usage_service.unregister_updater(self._switch)


class WyzePlugDailyEnergySensor(RestoreSensor):
    """Respresents an Outdoor Plug Daily Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3
    _attr_name = "Daily Energy Usage"

    def __init__(self, switch: Switch) -> None:
        """Initialize a daily energy sensor."""
        self._switch = switch

    @property
    def unique_id(self):
        """Get the unique ID of the sensor."""
        return f"{self._switch.nickname}.daily_energy-{self._switch.mac}"

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._switch.mac)},
            "name": self._switch.nickname,
        }

    @callback
    def _update_daily_sensor(self, event):
        """Update the sensor when the total sensor updates."""
        event_data = event.data
        new_state = event_data["new_state"]
        old_state = event_data["old_state"]

        if not old_state or not new_state:
            return

        updated_energy = float(new_state.state) - float(old_state.state)
        self._attr_native_value += updated_energy
        self.async_write_ha_state()

    async def _async_reset_at_midnight(self, now: datetime) -> None:
        """Reset the daily sensor."""
        self._attr_native_value = 0
        _LOGGER.debug("Resetting daily energy sensor %s to 0", self._switch.mac)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Get previous data and add listeners."""

        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value
        else:
            self._attr_native_value = 0

        registry = er.async_get(self.hass)
        entity_id_total_sensor = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{self._switch.nickname}.energy-{self._switch.mac}"
        )

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [entity_id_total_sensor], self._update_daily_sensor
            )
        )

        self.async_on_remove(
            async_track_time_change(
                self.hass, self._async_reset_at_midnight, hour=0, minute=0, second=0
            )
        )


class WyzeIrrigationBaseSensor(WyzeIrrigationEntity, SensorEntity):
    """Base class for device-level Wyze Irrigation sensors.

    Device info, dispatcher subscription and single-updater wiring come from
    :class:`WyzeIrrigationEntity`.
    """


class WyzeIrrigationZoneSensor(WyzeIrrigationZoneEntity, SensorEntity):
    """Base class for per-zone Wyze Irrigation sensors."""


class WyzeIrrigationRSSI(WyzeIrrigationBaseSensor):
    """Representation of a Wyze Irrigation RSSI sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "RSSI"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-rssi"

    @property
    def native_value(self) -> int:
        """Return the RSSI value."""
        return self._device.RSSI

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "dBm"


class WyzeIrrigationIP(WyzeIrrigationBaseSensor):
    """Representation of a Wyze Irrigation IP sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "IP Address"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-ip"

    @property
    def native_value(self) -> str:
        """Return the IP address."""
        return self._device.IP


class WyzeIrrigationSSID(WyzeIrrigationBaseSensor):
    """Representation of a Wyze Irrigation SSID sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "SSID"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-ssid"

    @property
    def native_value(self) -> str:
        """Return the SSID."""
        return self._device.ssid


def _parse_utc(timestamp: str | None) -> datetime.datetime | None:
    """Parse an ISO-8601 UTC timestamp (``...Z``) into an aware datetime."""
    if not timestamp:
        return None
    try:
        return datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class WyzeIrrigationCurrentZone(WyzeIrrigationBaseSensor):
    """Name of the zone currently watering (or 'Idle')."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Current Zone"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-current-zone"

    @property
    def native_value(self) -> str:
        """Return the currently running zone name, or 'Idle'."""
        return getattr(self._device, "current_running_zone", None) or "Idle"

    @property
    def icon(self) -> str:
        """Return the icon for the current zone sensor."""
        return "mdi:sprinkler" if self.native_value != "Idle" else "mdi:sprinkler-off"


class WyzeIrrigationNextScheduledRun(WyzeIrrigationBaseSensor):
    """Timestamp of the next scheduled run."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Next Scheduled Run"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-next-run"

    @property
    def native_value(self) -> datetime.datetime | None:
        """Return the next scheduled run time."""
        return _parse_utc(getattr(self._device, "next_scheduled_run", None))


class WyzeIrrigationActiveSchedules(WyzeIrrigationBaseSensor):
    """Number of enabled configured schedules."""

    _attr_icon = "mdi:calendar-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Active Schedules"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-active-schedules"

    @property
    def native_value(self) -> int:
        """Return the number of enabled schedules."""
        return int(getattr(self._device, "active_schedules_count", 0) or 0)


class WyzeIrrigationLastRunDuration(WyzeIrrigationBaseSensor):
    """Duration of the most recent completed run (minutes)."""

    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = "min"
    _attr_device_class = SensorDeviceClass.DURATION

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Last Run Duration"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-last-run-duration"

    @property
    def native_value(self) -> int:
        """Return the last completed run duration in minutes."""
        return int(getattr(self._device, "last_run_duration", 0) or 0) // 60

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        return {
            "last_run_end_time": getattr(self._device, "last_run_end_time", None),
            "duration_seconds": getattr(self._device, "last_run_duration", 0),
        }


class WyzeIrrigationZoneSmartDuration(WyzeIrrigationZoneSensor):
    """Configured smart-watering duration for a zone (minutes)."""

    _attr_icon = "mdi:timer-cog-outline"
    _attr_native_unit_of_measurement = "min"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_entity_registry_enabled_default = False

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._zone.name} Smart Duration"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-zone-{self._zone.zone_number}-smart-duration"

    @property
    def native_value(self) -> int | None:
        """Return the smart duration in minutes."""
        value = getattr(self._zone, "smart_duration", None)
        return value // 60 if value is not None else None


class WyzeIrrigationZoneRemainingTime(WyzeIrrigationZoneSensor):
    """Remaining watering time for a currently running zone (minutes)."""

    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "min"
    _attr_device_class = SensorDeviceClass.DURATION

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._zone.name} Remaining Time"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-zone-{self._zone.zone_number}-remaining-time"

    @property
    def native_value(self) -> int:
        """Return the remaining time in minutes (0 when idle)."""
        return int(getattr(self._zone, "remaining_time", 0) or 0) // 60

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        return {"remaining_seconds": getattr(self._zone, "remaining_time", 0)}


class WyzeIrrigationZoneLastWatered(WyzeIrrigationZoneSensor):
    """Timestamp a zone last finished watering."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:water-check"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._zone.name} Last Watered"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-zone-{self._zone.zone_number}-last-watered"

    @property
    def native_value(self) -> datetime.datetime | None:
        """Return the last-watered timestamp."""
        return _parse_utc(getattr(self._zone, "last_watered", None))
