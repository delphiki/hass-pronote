"""Config flow for Pronote integration."""
from __future__ import annotations

import logging
from typing import Any
import uuid

import voluptuous as vol

from datetime import time

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import callback

### Hotfix for python 3.13 https://github.com/bain3/pronotepy/pull/317#issuecomment-2523257656
import autoslot
from itertools import tee
import dis
def assignments_to_self(method) -> set:
    instance_var = next(iter(method.__code__.co_varnames), 'self')
    instructions = dis.Bytecode(method)
    i0, i1 = tee(instructions)
    next(i1, None)
    names = set()
    for a, b in zip(i0, i1):
        accessing_self = (
            a.opname in ("LOAD_FAST", "LOAD_DEREF") and a.argval == instance_var
        ) or (a.opname == "LOAD_FAST_LOAD_FAST" and a.argval[1] == instance_var)
        storing_attribute = b.opname == "STORE_ATTR"
        if accessing_self and storing_attribute:
            names.add(b.argval)
    return names
autoslot.assignments_to_self = assignments_to_self
### End Hotfix

import pronotepy
from .pronote_helper import *

from pronotepy.ent import *

from .const import (
    DOMAIN,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_ALARM_OFFSET,
    DEFAULT_LUNCH_BREAK_TIME,
)


_LOGGER = logging.getLogger(__name__)


def get_ent_list() -> dict[str]:
    ent_functions = dir(pronotepy.ent)
    ent = []
    for func in ent_functions:
        if func.startswith('__') or func in ['ent', 'complex_ent', 'generic_func']:
            continue
        ent.append(func)
    return ent

STEP_USER_CONNECTION_TYPE = vol.Schema(
    {
        vol.Required("connection_type"): vol.In({'username_password': 'Username and password', 'qrcode': 'QRCode'}),
        vol.Required("account_type"): vol.In({'eleve': 'Student', 'parent': 'Parent'})
    }
)

STEP_USER_DATA_SCHEMA_UP = vol.Schema(
    {
        vol.Required("url"): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("ent"): vol.In(get_ent_list()),
        vol.Optional("device_name"): str,
        vol.Optional("account_pin"): str
    }
)

STEP_USER_DATA_SCHEMA_QR = vol.Schema(
    {
        vol.Required("qr_code_json"): str,
        vol.Required("qr_code_pin"): str,
        vol.Optional("device_name"): str,
        vol.Optional("account_pin"): str
    }
)

@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pronote."""

    VERSION = 2
    pronote_client = None

    def __init__(self) -> None:
        self._user_inputs: dict = {}

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""
        _LOGGER.debug("Setup process initiated by user.")

        if user_input is None:
            _LOGGER.info("Selecting connection")

            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_CONNECTION_TYPE
            )
        _LOGGER.info("Selected connection: %s", user_input)
        self._user_inputs.update(user_input)

        if user_input['connection_type'] == 'username_password':
            return await self.async_step_username_password_login()
        else:
            return await self.async_step_qr_code_login()

    async def async_step_username_password_login(self, user_input: dict | None = None) -> FlowResult:
        """Handle the rest step."""
        _LOGGER.info("async_step_up: Connecting via user/password")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.debug("User Input: %s", user_input)
                user_input['account_type'] = self._user_inputs['account_type']
                self._user_inputs.update(user_input)
                client = await self.hass.async_add_executor_job(get_client_from_username_password, self._user_inputs)

                if client is None:
                    raise InvalidAuth
            except pronotepy.exceptions.CryptoError:
                errors["base"] = "invalid_auth"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                if user_input['account_type'] == 'parent':
                    _LOGGER.debug("_User Inputs UP Parent: %s", self._user_inputs)
                    self.pronote_client = client
                    return await self.async_step_parent()

                _LOGGER.debug("_User Inputs UP: %s", self._user_inputs)
                return self.async_create_entry(title=client.info.name, data=self._user_inputs)


        return self.async_show_form(
            step_id="username_password_login", data_schema=STEP_USER_DATA_SCHEMA_UP, errors=errors
        )

    async def async_step_qr_code_login(self, user_input: dict | None = None) -> FlowResult:
        """Handle the rest step."""
        _LOGGER.info("async_step_up: Connecting via qrcode")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.debug("User Input: %s", self._user_inputs)
                user_input['account_type'] = self._user_inputs['account_type']
                user_input['qr_code_uuid'] = str(uuid.uuid4())

                client = await self.hass.async_add_executor_job(get_client_from_qr_code, user_input)

                if client is None:
                    raise InvalidAuth
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                self._user_inputs['qr_code_url'] = client.pronote_url
                self._user_inputs['qr_code_username'] = client.username
                self._user_inputs['qr_code_password'] = client.password
                self._user_inputs['qr_code_uuid'] = client.uuid

                if self._user_inputs['account_type'] == 'parent':
                    self.pronote_client = client
                    return await self.async_step_parent()

                return self.async_create_entry(title=client.info.name, data=self._user_inputs)


        return self.async_show_form(
            step_id="qr_code_login", data_schema=STEP_USER_DATA_SCHEMA_QR, errors=errors
        )

    async def async_step_parent(
        self, user_input=None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        children: dict[str, str] = {}
        for child in self.pronote_client.children:
            children[child.name] = child.name

        STEP_PARENT_DATA_SCHEMA = vol.Schema(
            {
                vol.Required("child"): vol.In(children),
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="parent", data_schema=STEP_PARENT_DATA_SCHEMA, errors=errors, description_placeholders={"title": "Enfant(s)"}

            )

        self._user_inputs['child'] = user_input['child']
        _LOGGER.debug("Parent Input UP: %s", self._user_inputs)
        return self.async_create_entry(title=children[user_input['child']]+" (via compte parent)", data=self._user_inputs)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("nickname", default=self.config_entry.options.get("nickname")): vol.All(vol.Coerce(str), vol.Length(min=0)),
                    vol.Optional("refresh_interval", default=self.config_entry.options.get("refresh_interval", DEFAULT_REFRESH_INTERVAL)): int,
                    vol.Optional("lunch_break_time", default=self.config_entry.options.get("lunch_break_time", DEFAULT_LUNCH_BREAK_TIME)): str,
                    vol.Optional("alarm_offset", default=self.config_entry.options.get("alarm_offset", DEFAULT_ALARM_OFFSET)): int,
                }
            ),
        )