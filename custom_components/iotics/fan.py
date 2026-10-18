"""Fan platform for Iotics — simple on/off fan entity (no speed control)."""

from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, COORDINATOR
from .iotics_api import slugify, IoticsApiClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Iotics fan entities (one per fan device, on/off only)."""
    coordinator = hass.data[DOMAIN][COORDINATOR]
    devices = coordinator.data
    buttons = IoticsApiClient.extract_buttons(devices)

    entities = []
    for b in buttons:
        if b["btn"] != "f1":
            continue
        room_slug = slugify(b["device_name"])
        unique_id = f"iotics_{room_slug}_combined_fan"
        entity_id = f"fan.iotics_{room_slug}_combined_fan"

        entity = IoticsFan(
            coordinator=coordinator,
            entity_id_str=entity_id,
            name=f"{b['device_name']} Fan",
            device_name=b["device_name"],
            token=b["token"],
            ip=b["ip"],
            unique_id=unique_id,
        )
        entities.append(entity)
        coordinator.entities_by_id[entity.entity_id] = entity

    async_add_entities(entities)


class IoticsFan(FanEntity):
    """Iotics fan entity — on/off only, no speed control."""

    _attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

    def __init__(
        self,
        coordinator,
        entity_id_str: str,
        name: str,
        device_name: str,
        token: str,
        ip: str,
        unique_id: str,
    ) -> None:
        self.entity_id = entity_id_str
        self._coordinator = coordinator
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._token = token
        self._ip = ip
        self._room_slug = slugify(device_name)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, token)},
            name=device_name,
            manufacturer="Iotics",
            model="Iotics Smart Switch",
        )

    @property
    def is_on(self) -> bool:
        return self._coordinator.entity_state.get(self.entity_id, "off") == "on"

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        self._coordinator.entity_state[self.entity_id] = "on"
        self.async_write_ha_state()
        self.hass.async_create_task(self._send_http("f1", "1"))

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._coordinator.entity_state[self.entity_id] = "off"
        self.async_write_ha_state()
        self.hass.async_create_task(self._send_http("f1", "0"))

    async def _send_http(self, btn: str, status: str) -> None:
        import urllib.request
        import asyncio
        loop = asyncio.get_event_loop()
        url = f"http://{self._current_ip()}/action?button={btn}&status={status}"
        try:
            await loop.run_in_executor(
                None, lambda: urllib.request.urlopen(url, timeout=3).read()
            )
        except Exception as err:
            _LOGGER.error("HTTP command to %s failed: %s", url, err)

    def _current_ip(self) -> str:
        """Return the freshest known device IP from the coordinator."""
        for dev in self._coordinator.data:
            if dev.get("hardwaretoken") == self._token and dev.get("ip"):
                return dev["ip"]
        return self._ip