"""Shared helpers and base entities for Wyze irrigation (BS_WK1 Sprinkler Controller).

The Wyze irrigation device exposes many entities (device sensors, per-zone
sensors, per-zone binary sensors, buttons and numbers). They must all be kept
in sync from a *single* background updater per device rather than each entity
registering its own — otherwise the library's ``callback_function`` (one slot
per device) is repeatedly overwritten and multiple updaters leak.

This module centralises that: the first entity to be added for a device
registers one updater whose callback fans out via the dispatcher; every entity
subscribes to that dispatcher signal. A per-device reference count tears the
updater down once the last entity is removed.
"""

import logging

from wyzeapy.services.irrigation_service import Irrigation, IrrigationService

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, IRRIGATION_UPDATED

_LOGGER = logging.getLogger(__name__)

# Key under hass.data[DOMAIN] holding the per-device updater registry.
IRRIGATION_UPDATERS = "irrigation_updaters"
# Poll interval (seconds). Each poll makes several API calls (iot_prop, zones,
# schedule_runs, device_info, schedules) so we keep it modest.
UPDATE_INTERVAL = 60


def irrigation_signal(mac: str) -> str:
    """Return the per-device dispatcher signal name."""
    return f"{IRRIGATION_UPDATED}-{mac}"


async def async_register_irrigation_updater(
    hass: HomeAssistant, service: IrrigationService, device: Irrigation
) -> None:
    """Ensure exactly one background updater exists for ``device``.

    The first caller registers the updater (its callback dispatches the freshly
    updated device to all subscribed entities); subsequent callers just bump the
    reference count.
    """
    store = hass.data.setdefault(DOMAIN, {}).setdefault(IRRIGATION_UPDATERS, {})
    entry = store.get(device.mac)
    if entry is not None:
        entry["count"] += 1
        return

    @callback
    def _dispatch(updated: Irrigation) -> None:
        async_dispatcher_send(hass, irrigation_signal(device.mac), updated)

    device.callback_function = _dispatch
    service.register_updater(device, UPDATE_INTERVAL)
    await service.start_update_manager()
    store[device.mac] = {"count": 1, "device": device, "service": service}


@callback
def async_deregister_irrigation_entity(hass: HomeAssistant, device: Irrigation) -> None:
    """Drop one reference to a device's updater, tearing it down at zero."""
    store = hass.data.get(DOMAIN, {}).get(IRRIGATION_UPDATERS, {})
    entry = store.get(device.mac)
    if entry is None:
        return
    entry["count"] -= 1
    if entry["count"] <= 0:
        try:
            entry["service"].unregister_updater(entry["device"])
        except Exception as err:  # pragma: no cover - defensive cleanup
            _LOGGER.debug("Error unregistering irrigation updater: %s", err)
        store.pop(device.mac, None)


class WyzeIrrigationEntity:
    """Mixin providing device info and single-updater wiring for irrigation entities.

    Combine with a platform entity base, e.g.
    ``class Foo(WyzeIrrigationEntity, SensorEntity): ...``.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, irrigation_service: IrrigationService, irrigation: Irrigation
    ) -> None:
        """Initialize the irrigation entity."""
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
    def _handle_irrigation_update(self, irrigation: Irrigation) -> None:
        """Store the freshly updated device and write state."""
        self._device = irrigation
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates and ensure the device updater is running."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                irrigation_signal(self._device.mac),
                self._handle_irrigation_update,
            )
        )
        await async_register_irrigation_updater(
            self.hass, self._irrigation_service, self._device
        )
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Release this entity's hold on the device updater."""
        async_deregister_irrigation_entity(self.hass, self._device)
        await super().async_will_remove_from_hass()


class WyzeIrrigationZoneEntity(WyzeIrrigationEntity):
    """Irrigation entity bound to a specific zone.

    Re-resolves its ``_zone`` from the updated device on every refresh so zone
    state (running / remaining time / last watered) stays current.
    """

    def __init__(
        self,
        irrigation_service: IrrigationService,
        irrigation: Irrigation,
        zone,
    ) -> None:
        """Initialize the zone-bound irrigation entity."""
        super().__init__(irrigation_service, irrigation)
        self._zone = zone
        self._zone_number = zone.zone_number

    @callback
    def _handle_irrigation_update(self, irrigation: Irrigation) -> None:
        """Store the updated device, re-resolve this zone, and write state."""
        self._device = irrigation
        for zone in irrigation.zones:
            if zone.zone_number == self._zone_number:
                self._zone = zone
                break
        self.async_write_ha_state()
