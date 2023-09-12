"""Config flow for Pronote integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

import pronotepy

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


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("url"): str,
        vol.Required("account_type"): vol.In({'eleve': 'Élève', 'parent': 'Parent'}),
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("ent"): vol.In(get_ent_list()),
    }
)


def auth_test(data) -> pronotepy.Client | pronotepy.ParentClient | None:
    url = data['url'] + ('parent' if data['account_type'] ==
                         'parent' else 'eleve') + '.html'

    ent = None
    if 'ent' in data:
        ent = getattr(pronotepy.ent, data['ent'])

    if not ent:
        url += '?login=true'

    try:
        client = (pronotepy.ParentClient if data['account_type'] ==
                  'parent' else pronotepy.Client)(url, data['username'], data['password'], ent)
        _LOGGER.info(client.info.name)
    except Exception as err:
        _LOGGER.critical(err)
        return None

    return client


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pronote."""

    VERSION = 1
    user_step_data = {}
    pronote_client = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = await self.hass.async_add_executor_job(auth_test, user_input)

                if client is None:
                    raise InvalidAuth
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if user_input['account_type'] == 'parent':
                    self.user_step_data = user_input
                    self.pronote_client = client
                    return await self.async_step_parent()

                return self.async_create_entry(title=client.info.name, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
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

        self.user_step_data['child'] = user_input['child']

        return self.async_create_entry(title=children[user_input['child']]+" (via compte parent)", data=self.user_step_data)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
