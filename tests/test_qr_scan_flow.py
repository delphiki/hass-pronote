"""Set up a QR code account by scanning it with the phone camera."""

from unittest.mock import patch
from urllib.parse import urlparse

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import QR, qr_client

LOGIN = "custom_components.pronote.config_flow.get_client_from_qr_code"


async def _start(hass, connection_type="qrcode_scan", account_type="parent"):
    result = await hass.config_entries.flow.async_init(
        "pronote", context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": connection_type, "account_type": account_type},
    )


async def _scan(hass, client, result):
    response = await client.post(urlparse(result["url"]).path, json={"qr": QR})
    assert response.status == 200
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(result["flow_id"])


async def test_scan_option_offered(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        "pronote", context={"source": config_entries.SOURCE_USER}
    )
    choices = result["data_schema"].schema["connection_type"].container
    assert choices["qrcode_scan"] == "Experimental: scan QR code from your phone"
    assert {"username_password", "qrcode"} <= set(choices)


async def test_scan_full_flow_parent(
    hass: HomeAssistant, https_ha, hass_client_no_auth
) -> None:
    calls = []

    def login(data):
        calls.append(dict(data))
        return qr_client()

    with patch(LOGIN, login):
        result = await _start(hass)
        assert result["type"] is FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "qr_scan"
        assert result["url"].startswith("https://ha.example.com/api/pronote/qr_scan/")
        assert result["description_placeholders"] == {"url": result["url"]}

        result = await _scan(hass, await hass_client_no_auth(), result)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "qr_scan_pin"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"qr_code_pin": "1234"}
        )
        assert result["step_id"] == "parent"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"child": "Alice"}
        )
        assert result["step_id"] == "nickname"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"nickname": "Ali"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Alice (via compte parent)"
    assert result["data"]["connection_type"] == "qrcode"
    assert result["data"]["qr_code_username"] == "tok-user"
    assert result["data"]["qr_code_password"] == "tok-pass"
    assert result["data"]["child"] == "Alice"
    assert "qr_code_json" not in result["data"]
    assert calls[0]["qr_code_json"] == QR
    assert calls[0]["qr_code_pin"] == "1234"
    assert calls[0]["account_type"] == "parent"


async def _refused_login(hass, hass_client_no_auth):
    result = await _start(hass)
    result = await _scan(hass, await hass_client_no_auth(), result)
    with patch(LOGIN, return_value=None):
        return await hass.config_entries.flow.async_configure(
            result["flow_id"], {"qr_code_pin": "0000"}
        )


async def test_scan_refused_offers_retry(
    hass: HomeAssistant, https_ha, hass_client_no_auth
) -> None:
    """Wrong PIN or expired QR code: retype the PIN or scan again."""
    result = await _refused_login(hass, hass_client_no_auth)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "qr_scan_failed"
    assert list(result["menu_options"]) == ["qr_scan_pin", "qr_scan"]
    assert hass.config_entries.async_entries("pronote") == []


async def test_scan_refused_retype_pin(
    hass: HomeAssistant, https_ha, hass_client_no_auth
) -> None:
    result = await _refused_login(hass, hass_client_no_auth)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "qr_scan_pin"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "qr_scan_pin"
    with patch(LOGIN, return_value=qr_client()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"qr_code_pin": "1234"}
        )
    assert result["step_id"] == "parent"


async def test_scan_refused_scan_again(
    hass: HomeAssistant, https_ha, hass_client_no_auth
) -> None:
    result = await _refused_login(hass, hass_client_no_auth)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "qr_scan"}
    )
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["step_id"] == "qr_scan"
    result = await _scan(hass, await hass_client_no_auth(), result)
    assert result["step_id"] == "qr_scan_pin"


async def test_scan_without_https(hass: HomeAssistant, http_only_ha) -> None:
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "qr_code_login"
    assert result["errors"] == {"base": "https_required"}


async def test_paste_flow_unchanged(hass: HomeAssistant, https_ha) -> None:
    student = qr_client()
    student.info.name = "DUPONT Alice"
    with patch(LOGIN, return_value=student):
        result = await _start(hass, connection_type="qrcode", account_type="eleve")
        assert result["step_id"] == "qr_code_login"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"qr_code_json": QR, "qr_code_pin": "1234"}
        )
        assert result["step_id"] == "nickname"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"nickname": "X"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "DUPONT Alice"
    assert result["data"]["connection_type"] == "qrcode"
    assert result["data"]["qr_code_password"] == "tok-pass"
