"""Light platform for Iotics — dimmer (brightness) and LED indicator lights."""

from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, COORDINATOR
from .iotics_api import slugify, IoticsApiClient

_LOGGER = logging.getLogger(__name__)

DIMMER_MAX = 9


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Iotics light entities (dimmers + device LEDs)."""
    coordinator = hass.data[DOMAIN][COORDINATOR]
    devices = coordinator.data
    buttons = IoticsApiClient.extract_buttons(devices)

    entities = []

    # One dimmer light entity per d* (on/off) button
    for b in buttons:
        if not b.get("is_dimmer"):
            continue
        if not (b["btn"].startswith("d") and not b["btn"].startswith("dl")):
            continue

        room_slug = slugify(b["device_name"])
        unique_id = f"iotics_{room_slug}_combined_dimmer"
        entity_id = f"light.iotics_{room_slug}_combined_dimmer"

        entity = IoticsDimmerLight(
            coordinator=coordinator,
            entity_id_str=entity_id,
            name=f"{b['device_name']} Dimmer",
            device_name=b["device_name"],
            token=b["token"],
            ip=b["ip"],
            unique_id=unique_id,
        )
        entities.append(entity)
        # Register under both the on/off key and the level key so MQTT updates
        # for both d* and dl* buttons refresh this single entity.
        coordinator.entities_by_id[entity.entity_id] = entity
        coordinator.entities_by_id[entity.entity_id + "_level"] = entity

    # Device-level internal LED (ledstatus) → one on/off light per device
    for dev in devices:
        token = dev["hardwaretoken"]
        room_slug = slugify(dev["hardwarename"])
        ip = dev.get("ip", "")
        led_eid = f"light.iotics_{room_slug}_led"

        led_entity = IoticsLedLight(
            coordinator=coordinator,
            entity_id_str=led_eid,
            name="LED",
            device_name=dev["hardwarename"],
            token=token,
            ip=ip,
            unique_id=f"iotics_{room_slug}_led",
        )
        entities.append(led_entity)
        coordinator.entities_by_id[led_entity.entity_id] = led_entity

    async_add_entities(entities)


# ---------------------------------------------------------------------------
# LED indicator light (on/off only)
# ---------------------------------------------------------------------------

class IoticsLedLight(LightEntity):
    """Internal LED/indicator light inside the Iotics touch switch."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, token)},
            name=device_name,
            manufacturer="Iotics",
            model="Iotics Smart Switch",
        )

    @property
    def is_on(self) -> bool:
        return self._coordinator.entity_state.get(self.entity_id, "off") == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._coordinator.entity_state[self.entity_id] = "on"
        self.async_write_ha_state()
        self.hass.async_create_task(self._send_http("1"))

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._coordinator.entity_state[self.entity_id] = "off"
        self.async_write_ha_state()
        self.hass.async_create_task(self._send_http("0"))

    async def _send_http(self, status: str) -> None:
        import urllib.request
        import asyncio
        loop = asyncio.get_event_loop()
        url = f"http://{self._current_ip()}/action?button=led&status={status}"
        try:
            await loop.run_in_executor(
                None, lambda: urllib.request.urlopen(url, timeout=3).read()
            )
        except Exception as err:
            _LOGGER.error("HTTP command to %s failed: %s", url, err)

    def _current_ip(self) -> str:
        for dev in self._coordinator.data:
            if dev.get("hardwaretoken") == self._token and dev.get("ip"):
                return dev["ip"]
        return self._ip


# ---------------------------------------------------------------------------
# Dimmer light (on/off + brightness)
# ---------------------------------------------------------------------------

class IoticsDimmerLight(LightEntity):
    """Iotics dimmer — single light entity with brightness slider (0-100%)."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

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
    def _level_eid(self) -> str:
        """Entity-state key used to store the current brightness level (0-9)."""
        return f"{self.entity_id}_level"

    @property
    def is_on(self) -> bool:
        return self._coordinator.entity_state.get(self.entity_id, "off") == "on"

    @property
    def brightness(self) -> int:
        """Return brightness scaled to 0-255."""
        try:
            lvl = int(self._coordinator.entity_state.get(self._level_eid, "0"))
        except (ValueError, TypeError):
            lvl = 0
        return int(lvl / DIMMER_MAX * 255)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._coordinator.entity_state[self.entity_id] = "on"
        brightness = kwargs.get("brightness")
        if brightness is not None:
            dim_step = max(0, min(DIMMER_MAX, round(brightness / 255 * DIMMER_MAX)))
            self._coordinator.entity_state[self._level_eid] = str(dim_step)
            self.async_write_ha_state()
            self.hass.async_create_task(self._send_http("d1", "1"))
            self.hass.async_create_task(self._send_http("dl1", str(dim_step)))
        else:
            self.async_write_ha_state()
            self.hass.async_create_task(self._send_http("d1", "1"))

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._coordinator.entity_state[self.entity_id] = "off"
        self.async_write_ha_state()
        self.hass.async_create_task(self._send_http("d1", "0"))

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
        for dev in self._coordinator.data:
            if dev.get("hardwaretoken") == self._token and dev.get("ip"):
                return dev["ip"]
        return self._ip