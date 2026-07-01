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
from homeassistant.const import ATTR_ATTRIBUTION, EntityCategory
from homeassistant.core import HomeAssistant
from wyzeapy import Wyzeapy, CameraService, SensorService
from wyzeapy.services.camera_service import Camera
from wyzeapy.services.irrigation_service import Irrigation, IrrigationService
from wyzeapy.services.sensor_service import Sensor
from wyzeapy.types import DeviceTypes
from .irrigation import WyzeIrrigationEntity, WyzeIrrigationZoneEntity
from .token_manager import token_exception_handler

from .const import DOMAIN, CONF_CLIENT

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

    cameras = [
        WyzeCameraMotion(camera_service, camera)
        for camera in await camera_service.get_cameras()
    ]
    sensors = [
        WyzeSensor(sensor_service, sensor)
        for sensor in await sensor_service.get_sensors()
    ]

    async_add_entities(cameras, True)
    async_add_entities(sensors, True)

    # Irrigation (Wyze Sprinkler Controller) binary sensors
    irrigation_service = await client.irrigation_service
    irrigation_entities: List[Any] = []
    for device in await irrigation_service.get_irrigations():
        device = await irrigation_service.update(device)
        # Device-level smart-skip (weather intelligence) status
        irrigation_entities.extend(
            [
                WyzeIrrigationSkipBinarySensor(
                    irrigation_service, device, "skip_rain", "Rain Skip", "mdi:weather-rainy"
                ),
                WyzeIrrigationSkipBinarySensor(
                    irrigation_service, device, "skip_wind", "Wind Skip", "mdi:weather-windy"
                ),
                WyzeIrrigationSkipBinarySensor(
                    irrigation_service, device, "skip_low_temp", "Freeze Skip", "mdi:snowflake"
                ),
                WyzeIrrigationSkipBinarySensor(
                    irrigation_service, device, "skip_saturation", "Saturation Skip", "mdi:water-alert"
                ),
                WyzeIrrigationSchedulesEnabled(irrigation_service, device),
            ]
        )
        # Per-zone running status
        for zone in device.zones:
            if zone.enabled:
                irrigation_entities.append(
                    WyzeIrrigationZoneRunning(irrigation_service, device, zone)
                )

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


class WyzeIrrigationZoneRunning(WyzeIrrigationZoneEntity, BinarySensorEntity):
    """Binary sensor: is this irrigation zone currently watering."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:sprinkler-variant"

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return f"{self._zone.name} Running"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the binary sensor."""
        return f"{self._device.mac}-zone-{self._zone.zone_number}-running"

    @property
    def is_on(self) -> bool:
        """Return True if the zone is currently running."""
        return bool(getattr(self._zone, "is_running", False))

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes, including any zone characteristics the API provides."""
        attrs = {
            "zone_number": self._zone.zone_number,
            "zone_id": getattr(self._zone, "zone_id", None),
            "remaining_time_seconds": getattr(self._zone, "remaining_time", 0),
        }
        for key in ("crop_type", "soil_type", "nozzle_type", "exposure", "slope"):
            value = getattr(self._zone, key, None)
            if value is not None:
                attrs[key] = value
        return attrs


class WyzeIrrigationSkipBinarySensor(WyzeIrrigationEntity, BinarySensorEntity):
    """Binary sensor reflecting a device smart-skip (weather intelligence) setting.

    ``on`` means the device is configured to skip watering for the given
    condition (rain / wind / freeze / saturation).
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        irrigation_service: IrrigationService,
        irrigation: Irrigation,
        attribute: str,
        label: str,
        icon: str,
    ) -> None:
        """Initialize the smart-skip binary sensor."""
        super().__init__(irrigation_service, irrigation)
        self._attribute = attribute
        self._label = label
        self._attr_icon = icon

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return self._label

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the binary sensor."""
        return f"{self._device.mac}-{self._attribute.replace('_', '-')}"

    @property
    def is_on(self) -> bool:
        """Return True if this smart-skip condition is enabled."""
        return bool(getattr(self._device, self._attribute, False))


class WyzeIrrigationSchedulesEnabled(WyzeIrrigationEntity, BinarySensorEntity):
    """Binary sensor: whether scheduled irrigation programs are enabled on the device."""

    _attr_icon = "mdi:calendar-check"

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return "Schedules Enabled"

    @property
    def unique_id(self) -> str:
        """Return a unique ID for the binary sensor."""
        return f"{self._device.mac}-schedules-enabled"

    @property
    def is_on(self) -> bool:
        """Return True if scheduled programs are enabled."""
        return bool(getattr(self._device, "schedules_enabled", False))
