"""Config flow for Pronote integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
import uuid

import voluptuous as vol

from datetime import time

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import callback
from homeassistant.helpers.redact import async_redact_data
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig

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

from .qr_scan import async_scan_url, async_setup_scan
from .const import (
    DOMAIN,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_ALARM_OFFSET,
    DEFAULT_LUNCH_BREAK_TIME,
)


_LOGGER = logging.getLogger(__name__)

# Not written to the logs
TO_REDACT = {
    "password",
    "account_pin",
    "qr_code_json",
    "qr_code_pin",
    "qr_code_password",
    "qr_code_uuid",
}


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
        vol.Required("connection_type"): SelectSelector(
            SelectSelectorConfig(
                options=["username_password", "qrcode", "qrcode_scan"],
                translation_key="connection_type",
            )
        ),
        vol.Required("account_type"): SelectSelector(
            SelectSelectorConfig(options=["eleve", "parent"], translation_key="account_type")
        ),
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
        vol.Required("qr_code_json"): str,
        vol.Required("qr_code_pin"): str,
        vol.Optional("device_name"): str,
        vol.Optional("account_pin"): str,
    }
)

# after a camera scan, the QR code JSON is already known
STEP_QR_PIN_SCHEMA = vol.Schema(
    {
        vol.Required("qr_code_pin"): str,
        vol.Optional("device_name"): str,
        vol.Optional("account_pin"): str,
    }
)


@config_entries.HANDLERS.register(DOMAIN)
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Pronote."""

    VERSION = 2
    pronote_client = None

    def __init__(self) -> None:
        self._user_inputs: dict = {}
        self._scanned_qr: str | None = None

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
        if user_input["connection_type"] == "qrcode_scan":
            # a scanned QR code account is a QR code account
            self._user_inputs["connection_type"] = "qrcode"
            return await self.async_step_qr_scan()
        return await self.async_step_qr_code_login()

    async def async_step_username_password_login(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the rest step."""
        _LOGGER.info("async_step_up: Connecting via user/password")
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.debug(
                    "User Input: %s", async_redact_data(user_input, TO_REDACT)
                )
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
                    _LOGGER.debug(
                        "_User Inputs UP Parent: %s",
                        async_redact_data(self._user_inputs, TO_REDACT),
                    )
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
            if await self._async_login_with_qr(user_input):
                return await self._async_qr_logged_in()
            errors["base"] = "invalid_auth"

        return self._async_show_qr_code_login(errors)

    def _async_show_qr_code_login(self, errors: dict[str, str]) -> FlowResult:
        return self.async_show_form(
            step_id="qr_code_login", data_schema=STEP_USER_DATA_SCHEMA_QR, errors=errors
        )

    async def _async_get_client(self, login, data: dict):
        """Log in to Pronote, None when the credentials are refused."""
        try:
            return await self.hass.async_add_executor_job(login, data)
        except AUTH_ERRORS:
            return None

    async def _async_login_with_qr(self, user_input: dict) -> bool:
        """Log in with a QR code and keep the credentials it gives."""
        _LOGGER.debug("User Input: %s", async_redact_data(self._user_inputs, TO_REDACT))
        user_input["account_type"] = self._user_inputs["account_type"]
        user_input["qr_code_uuid"] = str(uuid.uuid4())
        client = await self._async_get_client(get_client_from_qr_code, user_input)
        if client is None:
            return False

        self._user_inputs["qr_code_url"] = client.pronote_url
        self._user_inputs["qr_code_username"] = client.username
        self._user_inputs["qr_code_password"] = client.password
        self._user_inputs["qr_code_uuid"] = client.uuid
        self.pronote_client = client
        return True

    async def _async_qr_logged_in(self) -> FlowResult:
        if self._user_inputs["account_type"] == "parent":
            return await self.async_step_parent()
        return await self.async_step_nickname()

    async def _async_scan_step(
        self, step_id: str, user_input: dict | None, next_step_id: str, no_https
    ) -> FlowResult:
        """Open the scan page (external step), or call `no_https` without HTTPS."""
        if user_input is not None:
            self._scanned_qr = user_input["qr_code_json"]
            return self.async_external_step_done(next_step_id=next_step_id)
        await async_setup_scan(self.hass)
        if (url := async_scan_url(self.hass, self.flow_id)) is None:
            return no_https({"base": "https_required"})
        return self.async_external_step(
            step_id=step_id, url=url, description_placeholders={"url": url}
        )

    async def async_step_qr_scan(self, user_input: dict | None = None) -> FlowResult:
        """Scan the QR code with the phone camera."""
        return await self._async_scan_step(
            "qr_scan", user_input, "qr_scan_pin", self._async_show_qr_code_login
        )

    async def async_step_qr_scan_pin(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Ask the PIN of the scanned QR code, then log in."""
        if user_input is None:
            return self.async_show_form(step_id="qr_scan_pin", data_schema=STEP_QR_PIN_SCHEMA)
        if await self._async_login_with_qr({**user_input, "qr_code_json": self._scanned_qr}):
            return await self._async_qr_logged_in()
        return await self.async_step_qr_scan_failed()

    async def async_step_qr_scan_failed(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Wrong PIN or expired QR code: retype the PIN or scan again."""
        return self.async_show_menu(
            step_id="qr_scan_failed", menu_options=["qr_scan_pin", "qr_scan"]
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
        _LOGGER.debug(
            "Parent Input UP: %s", async_redact_data(self._user_inputs, TO_REDACT)
        )
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
        if entry_data["connection_type"] == "qrcode":
            return await self.async_step_reauth_menu()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_menu(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Paste the new QR code JSON or scan it."""
        return self.async_show_menu(
            step_id="reauth_menu",
            menu_options=["reauth_confirm", "reauth_scan"],
            description_placeholders={"name": self._get_reauth_entry().title},
        )

    def _async_show_reauth_confirm(self, errors: dict[str, str]) -> FlowResult:
        entry = self._get_reauth_entry()
        is_qr_code = entry.data["connection_type"] == "qrcode"
        schema = STEP_USER_DATA_SCHEMA_QR if is_qr_code else STEP_USER_DATA_SCHEMA_UP
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                schema, {k: v for k, v in entry.data.items() if k != "password"}
            ),
            errors=errors,
            description_placeholders={"name": entry.title},
        )

    def _async_finish_qr_reauth(self, client, user_input: dict) -> FlowResult:
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
        return self.async_update_reload_and_abort(
            self._get_reauth_entry(), data_updates=updates
        )

    async def async_step_reauth_scan(self, user_input: dict | None = None) -> FlowResult:
        """Scan the new QR code with the phone camera."""
        return await self._async_scan_step(
            "reauth_scan", user_input, "reauth_scan_pin", self._async_show_reauth_confirm
        )

    async def async_step_reauth_scan_pin(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Ask the PIN of the scanned QR code, then log in again."""
        entry = self._get_reauth_entry()
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_scan_pin",
                data_schema=STEP_QR_PIN_SCHEMA,
                description_placeholders={"name": entry.title},
            )
        data = {**entry.data, **user_input, "qr_code_json": self._scanned_qr}
        if (client := await self._async_get_client(get_client_from_qr_code, data)) is None:
            return await self.async_step_reauth_scan_failed()
        return self._async_finish_qr_reauth(client, user_input)

    async def async_step_reauth_scan_failed(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Wrong PIN or expired QR code: retype the PIN or scan again."""
        return self.async_show_menu(
            step_id="reauth_scan_failed", menu_options=["reauth_scan_pin", "reauth_scan"]
        )

    async def async_step_reauth_confirm(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Ask for new credentials to keep the same entry and entities."""
        if user_input is None:
            return self._async_show_reauth_confirm({})
        entry = self._get_reauth_entry()
        is_qr_code = entry.data["connection_type"] == "qrcode"
        login = get_client_from_qr_code if is_qr_code else get_client_from_username_password
        if (client := await self._async_get_client(login, {**entry.data, **user_input})) is None:
            return self._async_show_reauth_confirm({"base": "invalid_auth"})
        if is_qr_code:
            return self._async_finish_qr_reauth(client, user_input)
        return self.async_update_reload_and_abort(entry, data_updates=user_input)

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
