"""Platform for sensor integration."""

import logging
import json
from typing import Any, Callable, List
from datetime import datetime

from wyzeapy import Wyzeapy
from wyzeapy.services.camera_service import Camera
from wyzeapy.services.lock_service import Lock
from wyzeapy.services.switch_service import Switch, SwitchUsageService
from wyzeapy.services.irrigation_service import IrrigationService, Irrigation, Zone

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    RestoreSensor,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    PERCENTAGE,
    UnitOfEnergy,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.entity_registry import async_get
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_CLIENT, DOMAIN, LOCK_UPDATED, CAMERA_UPDATED, IRRIGATION_UPDATED
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"
CAMERAS_WITH_BATTERIES = ["WVOD1", "HL_WCO2", "AN_RSCW", "GW_BE1"]
OUTDOOR_PLUGS = ["WLPPO"]


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Any], bool], None],
) -> None:
    """
    This function sets up the config_entry

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
    for camera in cameras:
        if camera.product_model in CAMERAS_WITH_BATTERIES:
            sensors.append(WyzeCameraBatterySensor(camera))

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

        # Add diagnostic sensors (existing)
        sensors.extend([
            WyzeIrrigationRSSI(irrigation_service, device),
            WyzeIrrigationIP(irrigation_service, device),
            WyzeIrrigationSSID(irrigation_service, device),
        ])

        # Add new feature sensors
        sensors.extend([
            WyzeIrrigationCurrentZone(irrigation_service, device),
            WyzeIrrigationNextScheduledRun(irrigation_service, device),
            WyzeIrrigationActiveSchedules(irrigation_service, device),
            WyzeIrrigationLastRunDuration(irrigation_service, device),
        ])

        # Add per-zone sensors
        for zone in device.zones:
            if zone.enabled:
                sensors.extend([
                    WyzeIrrigationZoneSoilMoisture(irrigation_service, device, zone),
                    WyzeIrrigationZoneSmartDuration(irrigation_service, device, zone),
                    WyzeIrrigationZoneRemainingTime(irrigation_service, device, zone),
                    WyzeIrrigationZoneLastWatered(irrigation_service, device, zone),
                ])

    async_add_entities(sensors, True)


class WyzeLockBatterySensor(SensorEntity):
    """Representation of a Wyze Lock or Lock Keypad Battery"""

    @property
    def enabled(self):
        return self._enabled

    LOCK_BATTERY = "lock_battery"
    KEYPAD_BATTERY = "keypad_battery"

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, lock, battery_type):
        self._enabled = None
        self._lock = lock
        self._battery_type = battery_type
        # make the battery unavailable by default, this will be toggled after the first update from the battery entity that
        # has battery data.
        self._available = False

    @callback
    def handle_lock_update(self, lock: Lock) -> None:
        """
        Helper function to
        Enable lock when Keypad has battery and
        Make it avaliable when either the lock battery or keypad battery exists
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
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LOCK_UPDATED}-{self._lock.mac}",
                self.handle_lock_update,
            )
        )

    @property
    def name(self) -> str:
        battery_type = self._battery_type.replace("_", " ").title()
        return f"{self._lock.nickname} {battery_type}"

    @property
    def unique_id(self):
        return f"{self._lock.nickname}.{self._battery_type}"

    @property
    def available(self) -> bool:
        return self._available

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def entity_registry_enabled_default(self) -> bool:
        if self._battery_type == self.KEYPAD_BATTERY:
            # The keypad battery may not be available if the lock has no keypad
            return False
        # The battery voltage will always be available for the lock
        return True

    @property
    def device_info(self):
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
        elif self._battery_type == self.KEYPAD_BATTERY:
            return str(self._lock.raw_dict.get("keypad", {}).get("power"))
        return 0

    @enabled.setter
    def enabled(self, value):
        self._enabled = value


class WyzeCameraBatterySensor(SensorEntity):
    """Representation of a Wyze Camera Battery"""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, camera):
        self._camera = camera

    @callback
    def handle_camera_update(self, camera: Camera) -> None:
        self._camera = camera
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{CAMERA_UPDATED}-{self._camera.mac}",
                self.handle_camera_update,
            )
        )

    @property
    def name(self) -> str:
        return f"{self._camera.nickname} Battery"

    @property
    def unique_id(self):
        return f"{self._camera.nickname}.battery"

    @property
    def should_poll(self) -> bool:
        return False

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
        return self._camera.device_params.get("electricity")


class WyzePlugEnergySensor(RestoreSensor):
    """Respresents an Outdoor Plug Total Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3
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
        self._switch.usage_history = None

    @property
    def name(self) -> str:
        """Get the name of the sensor."""
        return "Total Energy Usage"

    @property
    def unique_id(self):
        """Get the unique ID of the sensor."""
        return f"{self._switch.nickname}.energy-{self._switch.mac}"

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

    def update_energy(self):
        """Update the energy sensor."""
        _now = int(datetime.utcnow().hour)
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

    async def async_will_remove_from_hass(self) -> None:
        """Remove updater."""
        self._switch_usage_service.unregister_updater(self._switch)


class WyzePlugDailyEnergySensor(RestoreSensor):
    """Respresents an Outdoor Plug Daily Energy Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 3

    def __init__(self, switch: Switch) -> None:
        """Initialize a daily energy sensor."""
        self._switch = switch

    @property
    def name(self) -> str:
        """Get the name of the sensor."""
        return "Daily Energy Usage"

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

    async def _async_reset_at_midnight(self, now: datetime):
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

        registry = async_get(self.hass)
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


class WyzeIrrigationBaseSensor(SensorEntity):
    """Base class for Wyze Irrigation sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, irrigation_service: IrrigationService, irrigation: Irrigation) -> None:
        """Initialize the irrigation base sensor."""
        self._irrigation_service = irrigation_service
        self._device = irrigation

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.mac)},
            name=self._device.nickname,
            manufacturer="WyzeLabs",
            model=self._device.product_model,
            serial_number=self._device.sn,
            connections={(dr.CONNECTION_NETWORK_MAC, self._device.mac)},
        )

    @callback
    def handle_irrigation_update(self, irrigation: Irrigation) -> None:
        """Update the irrigation's state via dispatcher."""
        self._device = irrigation
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{IRRIGATION_UPDATED}-{self._device.mac}",
                self.handle_irrigation_update,
            )
        )
        # Only register the updater once per device (first sensor to be added)
        # The updater will dispatch to all entities
        if not hasattr(self._irrigation_service, f"_updater_registered_{self._device.mac}"):
            setattr(self._irrigation_service, f"_updater_registered_{self._device.mac}", True)

            @callback
            def callback_wrapper(irrigation: Irrigation):
                """Wrapper to dispatch updates to all entities."""
                async_dispatcher_send(self.hass, f"{IRRIGATION_UPDATED}-{self._device.mac}", irrigation)

            self._device.callback_function = callback_wrapper
            self._irrigation_service.register_updater(self._device, 30)
            await self._irrigation_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed."""
        # Don't unregister the updater as other entities may still need it
        pass


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


class WyzeIrrigationCurrentZone(WyzeIrrigationBaseSensor):
    """Representation of the currently running zone."""

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
        """Return the currently running zone name or Idle."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the schedule_runs API endpoint
        if hasattr(self._device, 'current_running_zone'):
            return self._device.current_running_zone
        return "Idle"

    @property
    def icon(self) -> str:
        """Return the icon for the current zone sensor."""
        return "mdi:sprinkler" if self.native_value != "Idle" else "mdi:sprinkler-off"


class WyzeIrrigationNextScheduledRun(WyzeIrrigationBaseSensor):
    """Representation of the next scheduled run time."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Next Scheduled Run"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-next-run"

    @property
    def native_value(self) -> datetime:
        """Return the next scheduled run time."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the schedule_runs API endpoint
        if hasattr(self._device, 'next_scheduled_run'):
            return self._device.next_scheduled_run
        return None

    @property
    def icon(self) -> str:
        """Return the icon for the next run sensor."""
        return "mdi:calendar-clock"

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attrs = {}
        if hasattr(self._device, 'next_schedule_name'):
            attrs["schedule_name"] = self._device.next_schedule_name
        if hasattr(self._device, 'next_schedule_zones'):
            attrs["zones"] = self._device.next_schedule_zones
        return attrs


class WyzeIrrigationActiveSchedules(WyzeIrrigationBaseSensor):
    """Representation of the number of active schedules."""

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
        """Return the number of active schedules."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the schedule API endpoint
        if hasattr(self._device, 'active_schedules_count'):
            return self._device.active_schedules_count
        return 0

    @property
    def icon(self) -> str:
        """Return the icon for the active schedules sensor."""
        return "mdi:calendar-multiple"

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attrs = {}
        if hasattr(self._device, 'schedule_list'):
            attrs["schedules"] = self._device.schedule_list
        return attrs


class WyzeIrrigationLastRunDuration(WyzeIrrigationBaseSensor):
    """Representation of the last run duration."""

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
        """Return the last run duration in minutes."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the schedule_runs API endpoint
        if hasattr(self._device, 'last_run_duration'):
            return self._device.last_run_duration // 60  # Convert seconds to minutes
        return 0

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "min"

    @property
    def icon(self) -> str:
        """Return the icon for the last run duration sensor."""
        return "mdi:timer-outline"

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attrs = {}
        if hasattr(self._device, 'last_run_zones'):
            attrs["zones_run"] = self._device.last_run_zones
        if hasattr(self._device, 'last_run_end_time'):
            attrs["end_time"] = self._device.last_run_end_time
        return attrs


class WyzeIrrigationZoneBaseSensor(SensorEntity):
    """Base class for Wyze Irrigation zone-specific sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, irrigation_service: IrrigationService, irrigation: Irrigation, zone: Zone) -> None:
        """Initialize the irrigation zone base sensor."""
        self._irrigation_service = irrigation_service
        self._device = irrigation
        self._zone = zone

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.mac)},
            name=self._device.nickname,
            manufacturer="WyzeLabs",
            model=self._device.product_model,
            serial_number=self._device.sn,
            connections={(dr.CONNECTION_NETWORK_MAC, self._device.mac)},
        )

    @callback
    def handle_irrigation_update(self, irrigation: Irrigation) -> None:
        """Update the irrigation's state via dispatcher."""
        self._device = irrigation
        # Update the zone reference
        for zone in self._device.zones:
            if zone.zone_number == self._zone.zone_number:
                self._zone = zone
                break
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{IRRIGATION_UPDATED}-{self._device.mac}",
                self.handle_irrigation_update,
            )
        )
        # Only register the updater once per device (first sensor to be added)
        # The updater will dispatch to all entities
        if not hasattr(self._irrigation_service, f"_updater_registered_{self._device.mac}"):
            setattr(self._irrigation_service, f"_updater_registered_{self._device.mac}", True)

            @callback
            def callback_wrapper(irrigation: Irrigation):
                """Wrapper to dispatch updates to all entities."""
                async_dispatcher_send(self.hass, f"{IRRIGATION_UPDATED}-{self._device.mac}", irrigation)

            self._device.callback_function = callback_wrapper
            self._irrigation_service.register_updater(self._device, 30)
            await self._irrigation_service.start_update_manager()
        return await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when removed."""
        # Don't unregister the updater as other entities may still need it
        pass


class WyzeIrrigationZoneSoilMoisture(WyzeIrrigationZoneBaseSensor):
    """Representation of a zone's soil moisture level."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._zone.name} Soil Moisture"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-zone-{self._zone.zone_number}-soil-moisture"

    @property
    def native_value(self) -> float:
        """Return the soil moisture percentage."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the zone details API endpoint
        if hasattr(self._zone, 'soil_moisture_level_at_end_of_day_pct'):
            return round(self._zone.soil_moisture_level_at_end_of_day_pct * 100, 1)
        return None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def icon(self) -> str:
        """Return the icon for the soil moisture sensor."""
        if self.native_value is None:
            return "mdi:water-percent"
        elif self.native_value < 20:
            return "mdi:water-alert"
        elif self.native_value < 50:
            return "mdi:water-minus"
        else:
            return "mdi:water-check"

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attrs = {
            "zone_number": self._zone.zone_number,
            "zone_id": self._zone.zone_id,
        }
        # Add zone configuration details
        if hasattr(self._zone, 'crop_type'):
            attrs["crop_type"] = self._zone.crop_type
        if hasattr(self._zone, 'soil_type'):
            attrs["soil_type"] = self._zone.soil_type
        if hasattr(self._zone, 'slope_type'):
            attrs["slope_type"] = self._zone.slope_type
        if hasattr(self._zone, 'exposure_type'):
            attrs["exposure_type"] = self._zone.exposure_type
        if hasattr(self._zone, 'nozzle_type'):
            attrs["nozzle_type"] = self._zone.nozzle_type
        if hasattr(self._zone, 'area'):
            attrs["area_sq_ft"] = self._zone.area
        if hasattr(self._zone, 'flow_rate'):
            attrs["flow_rate_gpm"] = self._zone.flow_rate
        if hasattr(self._zone, 'root_depth'):
            attrs["root_depth_inches"] = self._zone.root_depth
        return attrs


class WyzeIrrigationZoneSmartDuration(WyzeIrrigationZoneBaseSensor):
    """Representation of a zone's AI-calculated smart duration."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._zone.name} Smart Duration"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-zone-{self._zone.zone_number}-smart-duration"

    @property
    def native_value(self) -> int:
        """Return the smart duration in minutes."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the zone details API endpoint
        if hasattr(self._zone, 'smart_duration'):
            return self._zone.smart_duration // 60  # Convert seconds to minutes
        return None

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "min"

    @property
    def icon(self) -> str:
        """Return the icon for the smart duration sensor."""
        return "mdi:brain"

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attrs = {
            "zone_number": self._zone.zone_number,
            "zone_id": self._zone.zone_id,
        }
        if hasattr(self._zone, 'smart_duration'):
            attrs["duration_seconds"] = self._zone.smart_duration
        return attrs


class WyzeIrrigationZoneRemainingTime(WyzeIrrigationZoneBaseSensor):
    """Representation of a zone's remaining watering time."""

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
        """Return the remaining time in minutes."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the schedule_runs API endpoint
        if hasattr(self._zone, 'remaining_time'):
            return self._zone.remaining_time // 60  # Convert seconds to minutes
        return 0

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return "min"

    @property
    def icon(self) -> str:
        """Return the icon for the remaining time sensor."""
        return "mdi:timer-sand" if self.native_value > 0 else "mdi:timer-off"

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attrs = {
            "zone_number": self._zone.zone_number,
            "zone_id": self._zone.zone_id,
        }
        if hasattr(self._zone, 'remaining_time'):
            attrs["remaining_seconds"] = self._zone.remaining_time
        if hasattr(self._zone, 'is_running'):
            attrs["is_running"] = self._zone.is_running
        return attrs


class WyzeIrrigationZoneLastWatered(WyzeIrrigationZoneBaseSensor):
    """Representation of when a zone was last watered."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._zone.name} Last Watered"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-zone-{self._zone.zone_number}-last-watered"

    @property
    def native_value(self) -> datetime:
        """Return the timestamp of the last watering."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the zone details API endpoint with latest_events
        if hasattr(self._zone, 'last_watered_time'):
            return self._zone.last_watered_time
        return None

    @property
    def icon(self) -> str:
        """Return the icon for the last watered sensor."""
        return "mdi:clock-check-outline"

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attrs = {
            "zone_number": self._zone.zone_number,
            "zone_id": self._zone.zone_id,
        }
        # Add watering history if available
        if hasattr(self._zone, 'latest_events'):
            attrs["recent_waterings"] = self._zone.latest_events
        if hasattr(self._zone, 'last_watered_duration'):
            attrs["last_duration_seconds"] = self._zone.last_watered_duration
        if hasattr(self._zone, 'last_schedule_name'):
            attrs["last_schedule"] = self._zone.last_schedule_name
        return attrs
