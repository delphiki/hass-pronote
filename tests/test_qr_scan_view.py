"""Scan page and the QR code it posts back, served without auth."""

from urllib.parse import urlparse

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .conftest import QR


async def _scan_path(hass) -> tuple[str, str]:
    result = await hass.config_entries.flow.async_init(
        "pronote", context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"connection_type": "qrcode_scan", "account_type": "parent"}
    )
    return result["flow_id"], urlparse(result["url"]).path


async def test_page_and_static_files(hass: HomeAssistant, https_ha, hass_client_no_auth) -> None:
    _, path = await _scan_path(hass)
    client = await hass_client_no_auth()
    page = await (await client.get(path)).text()
    assert "__STATIC_URL__" not in page
    assert 'src="/api/pronote/qr_scan_static/pronote.png"' in page
    assert 'src="/static/icons/favicon-192x192.png"' in page
    assert '"/api/pronote/qr_scan_static/jsQR.js"' in page
    assert '"/api/pronote/qr_scan_static/qrcode.js"' in page
    for name, content_type in (
        ("pronote.png", "image/png"),
        ("jsQR.js", "text/javascript"),
        ("qrcode.js", "text/javascript"),
    ):
        response = await client.get(f"/api/pronote/qr_scan_static/{name}")
        assert response.status == 200, name
        assert response.content_type == content_type, name


async def test_unknown_flow(hass: HomeAssistant, https_ha, hass_client_no_auth) -> None:
    await _scan_path(hass)
    client = await hass_client_no_auth()
    assert (await client.get("/api/pronote/qr_scan/nope")).status == 404
    assert (await client.post("/api/pronote/qr_scan/nope", json={"qr": QR})).status == 404


async def test_flow_not_waiting_for_scan(
    hass: HomeAssistant, https_ha, hass_client_no_auth
) -> None:
    """Once the QR code is received, the flow left the scan step: link is dead."""
    flow_id, path = await _scan_path(hass)
    client = await hass_client_no_auth()
    assert (await client.post(path, json={"qr": QR})).status == 200
    await hass.async_block_till_done()
    await hass.config_entries.flow.async_configure(flow_id)
    assert (await client.get(path)).status == 404
    assert (await client.post(path, json={"qr": QR})).status == 404


async def test_rejects_non_pronote_qr(hass: HomeAssistant, https_ha, hass_client_no_auth) -> None:
    flow_id, path = await _scan_path(hass)
    client = await hass_client_no_auth()
    for body in ({"qr": "https://example.com"}, {"qr": '{"url": "x"}'}, {"nope": 1}, [1]):
        assert (await client.post(path, json=body)).status == 400, body
    assert (await client.post(path, data="not json")).status == 400
    assert hass.config_entries.flow.async_get(flow_id)["step_id"] == "qr_scan"
