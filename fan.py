"""Fan platform for Iotics — combined fan on/off + speed control."""

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

SPEED_COUNT = 4


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Iotics combined fan entities."""
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

        entity = IoticsCombinedFan(
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


class IoticsCombinedFan(FanEntity):
    """Combined fan entity — on/off + speed in one entity."""

    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF

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

    def _get_state(self, eid: str, default: str = "off") -> str:
        return self._coordinator.entity_state.get(eid, default)

    @property
    def is_on(self) -> bool:
        fan_switch = f"switch.iotics_{self._room_slug}_fan"
        return self._get_state(fan_switch) == "on"

    @property
    def percentage(self) -> int:
        speed_eid = f"number.iotics_{self._room_slug}_fan_speed"
        try:
            speed = int(self._get_state(speed_eid, "0"))
        except (ValueError, TypeError):
            speed = 0
        return int(speed / SPEED_COUNT * 100)

    @property
    def speed_count(self) -> int:
        return SPEED_COUNT

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        fan_switch = f"switch.iotics_{self._room_slug}_fan"
        self._coordinator.entity_state[fan_switch] = "on"
        self.async_write_ha_state()
        self.hass.async_create_task(self._send_http("f1", "1"))

    async def async_turn_off(self, **kwargs: Any) -> None:
        fan_switch = f"switch.iotics_{self._room_slug}_fan"
        self._coordinator.entity_state[fan_switch] = "off"
        self.async_write_ha_state()
        self.hass.async_create_task(self._send_http("f1", "0"))

    async def async_set_percentage(self, percentage: int) -> None:
        speed_step = round(percentage / 25)
        if speed_step < 0:
            speed_step = 0
        if speed_step > SPEED_COUNT:
            speed_step = SPEED_COUNT
        speed_eid = f"number.iotics_{self._room_slug}_fan_speed"
        self._coordinator.entity_state[speed_eid] = str(speed_step)
        if speed_step > 0:
            fan_switch = f"switch.iotics_{self._room_slug}_fan"
            self._coordinator.entity_state[fan_switch] = "on"
        self.async_write_ha_state()
        self.hass.async_create_task(self._send_http("l1", str(speed_step)))

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