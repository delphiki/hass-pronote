"""Re-authenticate an account, by pasting or scanning the new QR code."""

from unittest.mock import patch
from urllib.parse import urlparse

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import QR, qr_client

QR_LOGIN = "custom_components.pronote.config_flow.get_client_from_qr_code"
UP_LOGIN = "custom_components.pronote.config_flow.get_client_from_username_password"
SETUP = "custom_components.pronote.async_setup_entry"

QR_DATA = {
    "account_type": "parent",
    "connection_type": "qrcode",
    "child": "Alice",
    "qr_code_url": "https://x/pronote/mobile.parent.html",
    "qr_code_username": "old-user",
    "qr_code_password": "old-pass",
    "qr_code_uuid": "old-uuid",
}
UP_DATA = {
    "account_type": "eleve",
    "connection_type": "username_password",
    "url": "https://x/pronote/",
    "username": "u",
    "password": "p",
}


def _entry(hass, data):
    entry = MockConfigEntry(domain="pronote", version=2, title="Alice", data=dict(data))
    entry.add_to_hass(hass)
    return entry


async def _reauth(hass, entry):
    with patch(SETUP, return_value=True):
        return await entry.start_reauth_flow(hass)


async def _scan_then_pin(hass, hass_client_no_auth, entry, pin_input):
    result = await _reauth(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reauth_scan"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "reauth_scan"
    assert result["url"].startswith("https://ha.example.com/api/pronote/qr_scan/")
    client = await hass_client_no_auth()
    response = await client.post(urlparse(result["url"]).path, json={"qr": QR})
    assert response.status == 200
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_scan_pin"
    with patch(SETUP, return_value=True):
        return await hass.config_entries.flow.async_configure(result["flow_id"], pin_input)


async def test_qr_reauth_shows_menu(hass: HomeAssistant, https_ha) -> None:
    result = await _reauth(hass, _entry(hass, QR_DATA))
    assert result["type"] is FlowResultType.MENU
    assert list(result["menu_options"]) == ["reauth_confirm", "reauth_scan"]


async def test_qr_reauth_by_scan(hass: HomeAssistant, https_ha, hass_client_no_auth) -> None:
    entry = _entry(hass, QR_DATA)
    new = qr_client(username="new-user", password="new-pass", uuid="new-uuid")
    with patch(QR_LOGIN, return_value=new):
        result = await _scan_then_pin(
            hass, hass_client_no_auth, entry, {"qr_code_pin": "1234", "device_name": "HA"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["qr_code_username"] == "new-user"
    assert entry.data["qr_code_password"] == "new-pass"
    assert entry.data["qr_code_uuid"] == "new-uuid"
    assert entry.data["device_name"] == "HA"
    assert entry.data["child"] == "Alice"
    assert "qr_code_json" not in entry.data
    assert "qr_code_pin" not in entry.data
    assert hass.config_entries.async_entries("pronote") == [entry]


async def test_qr_reauth_scan_refused(
    hass: HomeAssistant, https_ha, hass_client_no_auth
) -> None:
    """Wrong PIN or expired QR code: retype the PIN or scan again."""
    entry = _entry(hass, QR_DATA)
    with patch(QR_LOGIN, return_value=None):
        result = await _scan_then_pin(hass, hass_client_no_auth, entry, {"qr_code_pin": "0000"})
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reauth_scan_failed"
    assert list(result["menu_options"]) == ["reauth_scan_pin", "reauth_scan"]
    assert dict(entry.data) == QR_DATA

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reauth_scan"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "reauth_scan"


async def test_qr_reauth_scan_without_https(hass: HomeAssistant, http_only_ha) -> None:
    result = await _reauth(hass, _entry(hass, QR_DATA))
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reauth_scan"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "https_required"}


async def test_qr_reauth_by_paste(hass: HomeAssistant, https_ha) -> None:
    entry = _entry(hass, QR_DATA)
    result = await _reauth(hass, entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "reauth_confirm"}
    )
    assert result["step_id"] == "reauth_confirm"
    with patch(QR_LOGIN, return_value=qr_client(password="new-pass")), patch(
        SETUP, return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"qr_code_json": QR, "qr_code_pin": "1234"}
        )
    assert result["reason"] == "reauth_successful"
    assert entry.data["qr_code_password"] == "new-pass"
    assert "qr_code_json" not in entry.data


async def test_up_reauth(hass: HomeAssistant, https_ha) -> None:
    entry = _entry(hass, UP_DATA)
    result = await _reauth(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    new_input = {"url": "https://x/pronote/", "username": "u", "password": "new"}
    with patch(UP_LOGIN, return_value=object()), patch(SETUP, return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], new_input)
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new"


async def test_up_reauth_refused(hass: HomeAssistant, https_ha) -> None:
    entry = _entry(hass, UP_DATA)
    result = await _reauth(hass, entry)
    new_input = {"url": "https://x/pronote/", "username": "u", "password": "bad"}
    with patch(UP_LOGIN, return_value=None):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], new_input)
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["password"] == "p"
