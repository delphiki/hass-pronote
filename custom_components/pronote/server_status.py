"""Pronote server status sensor (independent availability probe)."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta

import aiohttp

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# How often the server is probed, independent of the data refresh interval.
PROBE_INTERVAL = timedelta(minutes=5)

# Short timeout: we only need the HTTP status, never the page body.
PROBE_TIMEOUT = 15

# Stable state slugs (the UI shows localized labels via translations).
STATE_OPERATIONAL = "operational"
STATE_MAINTENANCE = "maintenance"
STATE_ERROR = "error"
STATE_UNREACHABLE = "unreachable"

SERVER_STATES = [
    STATE_OPERATIONAL,
    STATE_MAINTENANCE,
    STATE_ERROR,
    STATE_UNREACHABLE,
]


def get_pronote_base_url(config_data) -> str | None:
    """Derive the base Pronote URL (https://host/pronote/) from config data.

    Works for both QR-code entries (``qr_code_url``) and username/password
    entries (``url``), stripping any query string and trailing ``*.html`` page.
    """
    raw = config_data.get("qr_code_url") or config_data.get("url")
    if not raw:
        return None
    raw = raw.split("?", 1)[0]
    raw = re.sub(r"/[^/]+\.html$", "/", raw)
    if not raw.endswith("/"):
        raw += "/"
    return raw


def server_status_from_http(status: int | None) -> str:
    """Map an HTTP status (or None for a network failure) to a server state.

    - any response below 400 (200 login page, 3xx redirect to an ENT) -> operational
    - 503 "Service Unavailable" (Pronote app pool stopped) -> maintenance
    - any other 4xx/5xx -> error
    - no response at all (timeout, DNS, connection refused) -> unreachable
    """
    if status is None:
        return STATE_UNREACHABLE
    if status < 400:
        return STATE_OPERATIONAL
    if status == 503:
        return STATE_MAINTENANCE
    return STATE_ERROR


class PronoteServerStatusSensor(SensorEntity):
    """Reports the status of the Pronote server for this child.

    This entity is intentionally decoupled from the data coordinator and from
    pronotepy: it answers "what is the Pronote server doing?", not "did the full
    login succeed?". It performs its own lightweight HTTP probe and stays
    available even while the server is down, so it can report that state. Its
    identity is derived from the config entry so it works even when Pronote has
    never been reachable.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "server_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = SERVER_STATES
    _attr_should_poll = False

    def __init__(self, config_entry: ConfigEntry, base_url: str) -> None:
        """Initialize the Pronote server status sensor."""
        self._base_url = base_url

        # Derive the child name (and matching sensor prefix) from the config
        # entry rather than from coordinator data, so this sensor works even
        # when Pronote has never been reachable. For a parent account
        # ``data["child"]`` holds the selected child's name; for a student
        # account it falls back to the entry title (which is that name). This
        # mirrors the coordinator's sensor_prefix computation so the unique_id
        # and device identifier match the data entities exactly.
        child_name = config_entry.data.get("child") or config_entry.title
        sensor_prefix = re.sub("[^A-Za-z]", "_", child_name.lower())

        self._attr_unique_id = f"{DOMAIN}_{sensor_prefix}_server_status"
        self._attr_device_info = DeviceInfo(
            name=f"Pronote - {child_name}",
            identifiers={(DOMAIN, child_name)},
            manufacturer="Pronote",
            model=child_name,
        )

        self._attr_native_value = None
        self._http_status: int | None = None
        self._last_checked: str | None = None

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            "http_status": self._http_status,
            "last_checked": self._last_checked,
            "probed_url": self._base_url,
        }

    async def async_added_to_hass(self) -> None:
        """Probe once on startup, then schedule periodic probes."""
        await self._async_probe()
        self.async_write_ha_state()
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_scheduled_probe, PROBE_INTERVAL
            )
        )

    async def _async_scheduled_probe(self, now) -> None:
        """Run a probe on the timer and push the new state."""
        await self._async_probe()
        self.async_write_ha_state()

    async def _async_probe(self) -> None:
        """Probe the Pronote server and update the status state."""
        session = async_get_clientsession(self.hass)
        status: int | None = None
        try:
            async with session.get(
                self._base_url,
                timeout=aiohttp.ClientTimeout(total=PROBE_TIMEOUT),
                allow_redirects=True,
            ) as response:
                status = response.status
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.debug(
                "Pronote server status probe failed for %s: %s", self._base_url, err
            )
            status = None

        self._http_status = status
        self._attr_native_value = server_status_from_http(status)
        self._last_checked = dt_util.now().isoformat()
