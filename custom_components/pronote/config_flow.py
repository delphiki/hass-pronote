"""Config flow for Pronote integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
import subprocess #required to get the qrcode token
import json

from homeassistant import config_entries
from homeassistant.core import callback
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


STEP_USER_DATA_SCHEMA_UP = vol.Schema(
    {
        vol.Required("url"): str,
        vol.Required("account_type"): vol.In({'eleve': 'Élève', 'parent': 'Parent'}),
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("ent"): vol.In(get_ent_list())
    }
)

STEP_USER_DATA_SCHEMA_QR = vol.Schema(
    {
        vol.Required("account_type"): vol.In({'eleve': 'Élève', 'parent': 'Parent'}),
        vol.Required("qr_code_json"): str,
        vol.Required("qr_code_pin"): str,
        vol.Required("qr_code_uuid"): str
    }
)


def auth_test_up(data) -> pronotepy.Client | pronotepy.ParentClient | None:
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
    
def auth_test_qr(data) -> pronotepy.Client | pronotepy.ParentClient | None:
    
    # login with qrcode json 
    qr_code_json = json.loads(data['qr_code_json'])
    qr_code_pin = data['qr_code_pin']
    uuid = data['qr_code_uuid']
    
    # get the initial client using qr_code
    client = pronotepy.Client.qrcode_login(qr_code_json, qr_code_pin, uuid)
    
    #get the longterm client with the credentials from qr_code client
    client = pronotepy.Client.token_login(client.pronote_url,client.username,client.password,client.uuid)
    
    # set some varibales used in coordinator
    data['qr_code_url']=client.pronote_url
    data['qr_code_username']=client.username
    
    # save password to file, password changes with every login
    qrcredentials = open(f"/config/custom_components/pronote/qrcredentials_{data['qr_code_username']}.txt", "w+")
    qrcredentials.writelines([client.password])
    qrcredentials.close()

    return client    


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pronote."""

    VERSION = 1
    user_step_data = {}
    pronote_client = None  
    _user_inputs: dict = {}

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""
        _LOGGER.debug("Setup process initiated by user.")

        if user_input is None:
            _LOGGER.info("Selecting connection")

            data_schema = {
                vol.Required("connection_type"): vol.In({'normal': 'UserPwd', 'qrcode': 'QRCode'})
            }

            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(data_schema)
            )
        _LOGGER.info("Selected connection: %s", user_input)
        self._user_inputs.update(user_input)
        
        if user_input['connection_type'] == 'normal':
            return await self.async_step_up()
        else:
            return await self.async_step_qr()

    async def async_step_up(self, user_input: dict | None = None) -> FlowResult:
        _LOGGER.info("async_step_up: Connecting via user/password")
        """Handle the rest step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.debug("User Input: %s", user_input)
                client = await self.hass.async_add_executor_job(auth_test_up, user_input)

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
                    self._user_inputs.update(user_input)
                    _LOGGER.debug("_User Inputs UP Parent: %s", self._user_inputs)
                    self.user_step_data = self._user_inputs
                    self.pronote_client = client
                    return await self.async_step_parent()
                self._user_inputs.update(user_input)
                _LOGGER.debug("_User Inputs UP: %s", self._user_inputs)
                return self.async_create_entry(title=client.info.name, data=self._user_inputs)
        

        return self.async_show_form(
            step_id="up", data_schema=STEP_USER_DATA_SCHEMA_UP,errors=errors
        )

    async def async_step_qr(self, user_input: dict | None = None) -> FlowResult:
        _LOGGER.info("async_step_up: Connecting via qrcode")
        """Handle the rest step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.debug("User Input: %s", user_input)
                client = await self.hass.async_add_executor_job(auth_test_qr, user_input)

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
                self._user_inputs.update(user_input)
                _LOGGER.debug("_User Inputs QR: %s", self._user_inputs)
                return self.async_create_entry(title=client.info.name, data=self._user_inputs)
        

        return self.async_show_form(
            step_id="qr", data_schema=STEP_USER_DATA_SCHEMA_QR,errors=errors
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
        _LOGGER.debug("Parent Input UP: %s", self.user_step_data)
        return self.async_create_entry(title=children[user_input['child']]+" (via compte parent)", data=self.user_step_data)        


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
