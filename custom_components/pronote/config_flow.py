"""Config flow for Pronote integration."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any
import uuid

import voluptuous as vol

from datetime import time

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.file_upload import process_uploaded_file
from homeassistant.helpers.selector import FileSelector, FileSelectorConfig

### Hotfix for python 3.13/3.14 https://github.com/bain3/pronotepy/pull/317#issuecomment-2523257656
import autoslot
import dis


def assignments_to_self(method) -> set:
    instance_var = next(iter(method.__code__.co_varnames), "self")
    instructions = list(dis.Bytecode(method))
    names = set()
    for i, inst in enumerate(instructions):
        if inst.opname == "STORE_ATTR" and i > 0:
            prev = instructions[i - 1]
            # Handle any LOAD_FAST variant (LOAD_FAST, LOAD_FAST_BORROW, etc.) or LOAD_DEREF
            is_load = "LOAD_FAST" in prev.opname or prev.opname == "LOAD_DEREF"
            if not is_load:
                continue
            if isinstance(prev.argval, tuple):
                # Combined instruction (e.g. LOAD_FAST_LOAD_FAST), self is in the tuple
                if instance_var in prev.argval:
                    names.add(inst.argval)
            elif prev.argval == instance_var:
                names.add(inst.argval)
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
        if func.startswith("__") or func in ["ent", "complex_ent", "generic_func"]:
            continue
        ent.append(func)
    return ent


STEP_USER_CONNECTION_TYPE = vol.Schema(
    {
        vol.Required("connection_type"): vol.In(
            {"username_password": "Username and password", "qrcode": "QRCode"}
        ),
        vol.Required("account_type"): vol.In({"eleve": "Student", "parent": "Parent"}),
    }
)

STEP_USER_DATA_SCHEMA_UP = vol.Schema(
    {
        vol.Required("url"): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("ent"): vol.In(get_ent_list()),
        vol.Optional("device_name"): str,
        vol.Optional("account_pin"): str,
    }
)

STEP_USER_DATA_SCHEMA_QR = vol.Schema(
    {
        vol.Optional("qr_code_json"): str,
        vol.Optional("qr_code_image"): FileSelector(
            FileSelectorConfig(accept="image/*")
        ),
        vol.Required("qr_code_pin"): str,
        vol.Optional("device_name"): str,
        vol.Optional("account_pin"): str,
    }
)


def decode_qr_code_image(hass: HomeAssistant, file_id: str) -> str:
    """Read the Pronote QR code JSON from an uploaded picture."""
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode
    except (ImportError, OSError) as ex:
        # pyzbar needs the zbar system library
        _LOGGER.warning("Can't read the QR code picture: %s", ex)
        raise InvalidQRCode from ex

    try:
        with process_uploaded_file(hass, file_id) as file_path:
            with Image.open(file_path) as image:
                codes = decode(image)
    except (OSError, ValueError) as ex:
        _LOGGER.info("Can't read the QR code picture: %s", ex)
        raise InvalidQRCode from ex

    for code in codes:
        try:
            qr_code = json.loads(code.data)
        except ValueError:
            continue
        if isinstance(qr_code, dict) and "jeton" in qr_code:
            return code.data.decode()
    raise InvalidQRCode


async def async_get_qr_code_json(hass: HomeAssistant, user_input: dict) -> None:
    """Put the QR code JSON in user_input, from the picture if there is no JSON."""
    file_id = user_input.pop("qr_code_image", None)
    if file_id and not user_input.get("qr_code_json"):
        user_input["qr_code_json"] = await hass.async_add_executor_job(
            decode_qr_code_image, hass, file_id
        )
    if not user_input.get("qr_code_json"):
        raise InvalidQRCode


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

        if user_input["connection_type"] == "username_password":
            return await self.async_step_username_password_login()
        else:
            return await self.async_step_qr_code_login()

    async def async_step_username_password_login(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the rest step."""
        _LOGGER.info("async_step_up: Connecting via user/password")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.debug("User Input: %s", user_input)
                user_input["account_type"] = self._user_inputs["account_type"]
                self._user_inputs.update(user_input)
                client = await self.hass.async_add_executor_job(
                    get_client_from_username_password, self._user_inputs
                )

                if client is None:
                    raise InvalidAuth
            except AUTH_ERRORS:
                errors["base"] = "invalid_auth"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            else:
                self.pronote_client = client

                if user_input["account_type"] == "parent":
                    _LOGGER.debug("_User Inputs UP Parent: %s", self._user_inputs)
                    return await self.async_step_parent()

                return await self.async_step_nickname()

        return self.async_show_form(
            step_id="username_password_login",
            data_schema=STEP_USER_DATA_SCHEMA_UP,
            errors=errors,
        )

    async def async_step_qr_code_login(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the rest step."""
        _LOGGER.info("async_step_up: Connecting via qrcode")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.debug("User Input: %s", self._user_inputs)
                user_input["account_type"] = self._user_inputs["account_type"]
                user_input["qr_code_uuid"] = str(uuid.uuid4())
                await async_get_qr_code_json(self.hass, user_input)

                client = await self.hass.async_add_executor_job(
                    get_client_from_qr_code, user_input
                )

                if client is None:
                    raise InvalidAuth
            except InvalidQRCode:
                errors["base"] = "invalid_qr_code"
            except (InvalidAuth, *AUTH_ERRORS):
                errors["base"] = "invalid_auth"
            else:
                self._user_inputs["qr_code_url"] = client.pronote_url
                self._user_inputs["qr_code_username"] = client.username
                self._user_inputs["qr_code_password"] = client.password
                self._user_inputs["qr_code_uuid"] = client.uuid

                self.pronote_client = client

                if self._user_inputs["account_type"] == "parent":
                    return await self.async_step_parent()

                return await self.async_step_nickname()

        return self.async_show_form(
            step_id="qr_code_login", data_schema=STEP_USER_DATA_SCHEMA_QR, errors=errors
        )

    async def async_step_parent(self, user_input=None) -> FlowResult:
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
                step_id="parent",
                data_schema=STEP_PARENT_DATA_SCHEMA,
                errors=errors,
                description_placeholders={"title": "Enfant(s)"},
            )

        self._user_inputs["child"] = user_input["child"]
        _LOGGER.debug("Parent Input UP: %s", self._user_inputs)
        return await self.async_step_nickname()

    async def async_step_nickname(self, user_input: dict | None = None) -> FlowResult:
        """Handle nickname step."""

        child_name = self.pronote_client.info.name
        title = child_name
        if self._user_inputs.get("account_type") == "parent":
            child_name = self._user_inputs["child"]
            title = f"{child_name} (via compte parent)"

        if user_input is not None:
            self._user_inputs.update(user_input)

            return self.async_create_entry(
                title=title,
                data=self._user_inputs,
                options={"nickname": self._user_inputs["nickname"]},
            )

        STEP_NICKNAME_SCHEMA = vol.Schema(
            {
                vol.Optional(
                    "nickname",
                    default=f"{child_name.split(' ')[-1] if ' ' in child_name else child_name}",
                ): str,
            }
        )

        return self.async_show_form(
            step_id="nickname",
            data_schema=STEP_NICKNAME_SCHEMA,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication when Pronote rejects credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Ask for new credentials to keep the same entry and entities."""
        entry = self._get_reauth_entry()
        is_qr_code = entry.data["connection_type"] == "qrcode"
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                if is_qr_code:
                    await async_get_qr_code_json(self.hass, user_input)
                data = {**entry.data, **user_input}
                client = await self.hass.async_add_executor_job(
                    (
                        get_client_from_qr_code
                        if is_qr_code
                        else get_client_from_username_password
                    ),
                    data,
                )
                if client is None:
                    raise InvalidAuth
            except InvalidQRCode:
                errors["base"] = "invalid_qr_code"
            except (InvalidAuth, *AUTH_ERRORS):
                errors["base"] = "invalid_auth"
            else:
                updates = user_input
                if is_qr_code:
                    # don't keep the QR code, only the result
                    updates = {
                        "qr_code_url": client.pronote_url,
                        "qr_code_username": client.username,
                        "qr_code_password": client.password,
                        "qr_code_uuid": client.uuid,
                        "uuid": client.uuid,
                    }
                    # we keep the 2FA answers, so the next token login won't ask for it
                    for key in ("account_pin", "device_name"):
                        if user_input.get(key):
                            updates[key] = user_input[key]
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, **updates}
                )
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        schema = STEP_USER_DATA_SCHEMA_QR if is_qr_code else STEP_USER_DATA_SCHEMA_UP
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                schema, {k: v for k, v in entry.data.items() if k != "password"}
            ),
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry.entry_id)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class InvalidQRCode(HomeAssistantError):
    """Error to indicate no Pronote QR code was found."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry_id: str) -> None:
        """Initialize options flow."""
        self.config_entry_id = config_entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        config_entry = self.hass.config_entries.async_get_entry(self.config_entry_id)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "nickname", default=config_entry.options.get("nickname")
                    ): vol.All(vol.Coerce(str), vol.Length(min=0)),
                    vol.Optional(
                        "refresh_interval",
                        default=config_entry.options.get(
                            "refresh_interval", DEFAULT_REFRESH_INTERVAL
                        ),
                    ): int,
                    vol.Optional(
                        "lunch_break_time",
                        default=config_entry.options.get(
                            "lunch_break_time", DEFAULT_LUNCH_BREAK_TIME
                        ),
                    ): str,
                    vol.Optional(
                        "alarm_offset",
                        default=config_entry.options.get(
                            "alarm_offset", DEFAULT_ALARM_OFFSET
                        ),
                    ): int,
                }
            ),
        )
