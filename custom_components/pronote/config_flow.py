"""Config flow for Pronote integration."""
from __future__ import annotations

import logging
from typing import Any
import uuid

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

import pronotepy
from .pronote_helper import *

from pronotepy.ent import *

from .const import DOMAIN


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
        vol.Optional("ent"): vol.In(get_ent_list())
    }
)

STEP_USER_DATA_SCHEMA_QR = vol.Schema(
    {
        vol.Required("qr_code_json"): str,
        vol.Required("qr_code_pin"): str
    }
)

@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pronote."""

    VERSION = 2
    pronote_client = None
    _user_inputs: dict = {}

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

                client = await self.hass.async_add_executor_job(get_client_from_qr_code, user_input, self.hass.config.config_dir)

                if client is None:
                    raise InvalidAuth
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                self._user_inputs['qr_code_url'] = client.pronote_url
                self._user_inputs['qr_code_username'] = client.username
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


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
