"""
This module describes the connection between Home Assistant and Wyze for the Sensors
"""

import logging
import time
from typing import Callable, List, Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from wyzeapy import Wyzeapy, CameraService, SensorService
from wyzeapy.services.camera_service import Camera
from wyzeapy.services.sensor_service import Sensor
from wyzeapy.services.irrigation_service import IrrigationService, Irrigation, Zone
from wyzeapy.types import DeviceTypes
from .token_manager import token_exception_handler

from .const import DOMAIN, CONF_CLIENT, IRRIGATION_UPDATED

_LOGGER = logging.getLogger(__name__)
ATTRIBUTION = "Data provided by Wyze"


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Any], bool], None],
):
    """
    This function sets up the config entry for use in Home Assistant

    :param hass: Home Assistant instance
    :param config_entry: The current config_entry
    :param async_add_entities: This function adds entities to the config_entry
    :return:
    """

    _LOGGER.debug("""Creating new WyzeApi binary sensor component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]

    sensor_service = await client.sensor_service
    camera_service = await client.camera_service
    irrigation_service = await client.irrigation_service

    cameras = [
        WyzeCameraMotion(camera_service, camera)
        for camera in await camera_service.get_cameras()
    ]
    sensors = [
        WyzeSensor(sensor_service, sensor)
        for sensor in await sensor_service.get_sensors()
    ]

    # Add irrigation binary sensors
    irrigation_devices = await irrigation_service.get_irrigations()
    irrigation_entities = []
    for device in irrigation_devices:
        # Update the device to get its zones
        device = await irrigation_service.update(device)

        # Add per-zone running status binary sensors
        for zone in device.zones:
            if zone.enabled:
                irrigation_entities.append(WyzeIrrigationZoneRunning(irrigation_service, device, zone))

        # Add device-level weather skip binary sensors
        irrigation_entities.extend([
            WyzeIrrigationRainDelay(irrigation_service, device),
            WyzeIrrigationWindDelay(irrigation_service, device),
            WyzeIrrigationFreezeDelay(irrigation_service, device),
            WyzeIrrigationSaturationDelay(irrigation_service, device),
        ])

    async_add_entities(cameras, True)
    async_add_entities(sensors, True)
    async_add_entities(irrigation_entities, True)


class WyzeSensor(BinarySensorEntity):
    """
    A representation of the WyzeSensor for use in Home Assistant
    """

    def __init__(self, sensor_service: SensorService, sensor: Sensor):
        """Initializes the class"""
        self._sensor_service = sensor_service
        self._sensor = sensor
        self._last_event = int(str(int(time.time())) + "000")

    async def async_added_to_hass(self) -> None:
        """Registers for updates when the entity is added to Home Assistant"""
        await self._sensor_service.register_for_updates(
            self._sensor, self.process_update
        )

    async def async_will_remove_from_hass(self) -> None:
        await self._sensor_service.deregister_for_updates(self._sensor)

    def process_update(self, sensor: Sensor):
        """
        This function processes an update for the Wyze Sensor

        :param sensor: The sensor with the updated values
        """
        self._sensor = sensor
        self.schedule_update_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._sensor.mac)},
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._sensor.product_model,
        }

    @property
    def available(self) -> bool:
        return True

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._sensor.nickname

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def is_on(self):
        """Return true if sensor detects motion"""
        return self._sensor.detected

    @property
    def unique_id(self):
        return "{}-motion".format(self._sensor.mac)

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device model": self._sensor.product_model,
            "mac": self.unique_id,
        }

    @property
    def device_class(self):
        # pylint: disable=R1705
        if self._sensor.type is DeviceTypes.MOTION_SENSOR:
            return BinarySensorDeviceClass.MOTION
        elif self._sensor.type is DeviceTypes.CONTACT_SENSOR:
            return BinarySensorDeviceClass.DOOR
        else:
            raise RuntimeError(
                f"The device type {self._sensor.type} is not supported by this class"
            )


class WyzeCameraMotion(BinarySensorEntity):
    """
    A representation of the Wyze Camera for use as a binary sensor in Home Assistant
    """

    _is_on = False
    _last_event = time.time() * 1000

    def __init__(self, camera_service: CameraService, camera: Camera):
        self._camera_service = camera_service
        self._camera = camera

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._camera.mac)},
            "name": self.name,
            "manufacturer": "WyzeLabs",
            "model": self._camera.product_model,
        }

    @property
    def available(self) -> bool:
        return self._camera.available

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._camera.nickname

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def is_on(self):
        """Return true if the binary sensor is on"""
        return self._is_on

    @property
    def unique_id(self):
        return "{}-motion".format(self._camera.mac)

    @property
    def extra_state_attributes(self):
        """Return device attributes of the entity."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "device model": self._camera.product_model,
            "mac": self.unique_id,
        }

    @property
    def device_class(self):
        return BinarySensorDeviceClass.MOTION

    async def async_added_to_hass(self) -> None:
        await self._camera_service.register_for_updates(
            self._camera, self.process_update
        )

    async def async_will_remove_from_hass(self) -> None:
        await self._camera_service.deregister_for_updates(self._camera)

    @token_exception_handler
    def process_update(self, camera: Camera) -> None:
        """
        Is called by the update worker for events to update the values in this sensor

        :param camera: An updated version of the current camera
        """
        self._camera = camera

        if camera.last_event_ts > self._last_event:
            self._is_on = True
            self._last_event = camera.last_event_ts
        else:
            self._is_on = False
            self._last_event = camera.last_event_ts

        self.schedule_update_ha_state()


class WyzeIrrigationBaseBinarySensor(BinarySensorEntity):
    """Base class for Wyze Irrigation binary sensors."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, irrigation_service: IrrigationService, irrigation: Irrigation) -> None:
        """Initialize the irrigation base binary sensor."""
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


class WyzeIrrigationZoneRunning(BinarySensorEntity):
    """Representation of a Wyze Irrigation Zone Running Status."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, irrigation_service: IrrigationService, irrigation: Irrigation, zone: Zone) -> None:
        """Initialize the irrigation zone running binary sensor."""
        self._irrigation_service = irrigation_service
        self._device = irrigation
        self._zone = zone

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._zone.name} Running"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-zone-{self._zone.zone_number}-running"

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

    @property
    def is_on(self) -> bool:
        """Return true if the zone is currently running."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the schedule_runs API endpoint
        # For now, we'll check if the zone has a running status attribute
        return getattr(self._zone, 'is_running', False)

    @property
    def icon(self) -> str:
        """Return the icon for the zone running status."""
        return "mdi:sprinkler-variant" if self.is_on else "mdi:sprinkler-variant"

    @property
    def extra_state_attributes(self) -> dict:
        """Return entity specific state attributes."""
        attrs = {
            "zone_number": self._zone.zone_number,
            "zone_id": self._zone.zone_id,
        }
        # Add remaining time if available
        if hasattr(self._zone, 'remaining_time'):
            attrs["remaining_time_seconds"] = self._zone.remaining_time
        return attrs

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


class WyzeIrrigationRainDelay(WyzeIrrigationBaseBinarySensor):
    """Representation of a Wyze Irrigation Rain Delay Status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Rain Delay Active"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-rain-delay"

    @property
    def is_on(self) -> bool:
        """Return true if rain delay is active."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the schedule API endpoint
        return getattr(self._device, 'rain_delay_active', False)

    @property
    def icon(self) -> str:
        """Return the icon for the rain delay status."""
        return "mdi:weather-rainy" if self.is_on else "mdi:weather-sunny"


class WyzeIrrigationWindDelay(WyzeIrrigationBaseBinarySensor):
    """Representation of a Wyze Irrigation Wind Delay Status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Wind Delay Active"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-wind-delay"

    @property
    def is_on(self) -> bool:
        """Return true if wind delay is active."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the schedule API endpoint
        return getattr(self._device, 'wind_delay_active', False)

    @property
    def icon(self) -> str:
        """Return the icon for the wind delay status."""
        return "mdi:weather-windy" if self.is_on else "mdi:weather-sunny"


class WyzeIrrigationFreezeDelay(WyzeIrrigationBaseBinarySensor):
    """Representation of a Wyze Irrigation Freeze Delay Status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Freeze Delay Active"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-freeze-delay"

    @property
    def is_on(self) -> bool:
        """Return true if freeze delay is active."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the schedule API endpoint
        return getattr(self._device, 'freeze_delay_active', False)

    @property
    def icon(self) -> str:
        """Return the icon for the freeze delay status."""
        return "mdi:snowflake" if self.is_on else "mdi:weather-sunny"


class WyzeIrrigationSaturationDelay(WyzeIrrigationBaseBinarySensor):
    """Representation of a Wyze Irrigation Saturation Delay Status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return "Saturation Delay Active"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the sensor."""
        return f"{self._device.mac}-saturation-delay"

    @property
    def is_on(self) -> bool:
        """Return true if saturation delay is active."""
        # This will need to be implemented once the wyzeapy library
        # provides access to the schedule API endpoint
        return getattr(self._device, 'saturation_delay_active', False)

    @property
    def icon(self) -> str:
        """Return the icon for the saturation delay status."""
        return "mdi:water-alert" if self.is_on else "mdi:water-check"
