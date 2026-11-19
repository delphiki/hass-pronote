"""The Pronote integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ServiceValidationError
from homeassistant.helpers import config_validation as cv

import voluptuous as vol

from datetime import timedelta

import logging

from .coordinator import PronoteDataUpdateCoordinator

from .const import DOMAIN, PLATFORMS, DEFAULT_REFRESH_INTERVAL

_LOGGER = logging.getLogger(__name__)

SERVICE_MARK_AS_READ = "mark_as_read"
MARK_AS_READ_SCHEMA = vol.Schema(
    {
        vol.Required("key"): cv.string,
        vol.Optional("read", default=True): cv.boolean,
        vol.Optional("acknowledge", default=False): cv.boolean,
    }
)


async def async_migrate_entry(hass, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:

        new = {**config_entry.data}
        new["connection_type"] = "username_password"

        hass.config_entries.async_update_entry(config_entry, data=new, version=2)

    _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pronote from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = PronoteDataUpdateCoordinator(hass, entry)

    await coordinator.async_refresh()

    # Stop polling if credentials are rejected
    if isinstance(coordinator.last_exception, ConfigEntryAuthFailed):
        raise coordinator.last_exception

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    if not hass.services.has_service(DOMAIN, SERVICE_MARK_AS_READ):

        async def _mark_as_read(call: ServiceCall) -> None:
            """Queue the mark and refresh: it is applied with the client of the regular update."""
            coordinators = [
                data["coordinator"]
                for data in hass.data[DOMAIN].values()
                if data["coordinator"].queue_read_mark(
                    call.data["key"], call.data["read"], call.data["acknowledge"]
                )
            ]
            if not coordinators:
                raise ServiceValidationError(f"Unknown information key: {call.data['key']}")
            for coordinator in coordinators:
                await coordinator.async_request_refresh()

        hass.services.async_register(
            DOMAIN, SERVICE_MARK_AS_READ, _mark_as_read, schema=MARK_AS_READ_SCHEMA
        )

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if not coordinator.last_update_success:
        unsub = None

        @callback
        def _stop_listening() -> None:
            nonlocal unsub
            if unsub is not None:
                unsub()
                unsub = None

        @callback
        def _reload_on_recovery() -> None:
            if coordinator.last_update_success:
                _stop_listening()
                hass.async_create_task(
                    hass.config_entries.async_reload(entry.entry_id)
                )

        unsub = coordinator.async_add_listener(_reload_on_recovery)
        entry.async_on_unload(_stop_listening)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    hass.data[DOMAIN][entry.entry_id]["coordinator"].update_interval = timedelta(
        minutes=entry.options.get("refresh_interval", DEFAULT_REFRESH_INTERVAL)
    )

    return True
