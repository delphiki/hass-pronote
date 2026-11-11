"""Scan the Pronote QR code with the phone camera, from the config flow.

The config flow opens the scan page as an external step. The page decodes the
QR code in the browser and posts its content back here, which feeds the flow.
"""

from __future__ import annotations

import json
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers.http import KEY_HASS
from homeassistant.helpers.network import NoURLAvailableError, get_url

from .const import DOMAIN

SCAN_STEP_IDS = frozenset({"qr_scan", "reauth_scan"})
URL_PATH = "/api/pronote/qr_scan/{flow_id}"
STATIC_URL = "/api/pronote/qr_scan_static"
JSQR_URL = f"{STATIC_URL}/jsQR.js"

_STATIC_DIR = Path(__file__).parent / "qr_scan_static"
_SETUP_DONE = f"{DOMAIN}_qr_scan_setup"


async def async_setup_scan(hass: HomeAssistant) -> None:
    """Register the scan page and its static files (jsQR, icon), once."""
    if hass.data.get(_SETUP_DONE):
        return
    hass.data[_SETUP_DONE] = True
    page = await hass.async_add_executor_job((_STATIC_DIR / "scan.html").read_text)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(_STATIC_DIR), True)]
    )
    hass.http.register_view(QrScanView(page.replace("__STATIC_URL__", STATIC_URL)))


def async_scan_url(hass: HomeAssistant, flow_id: str) -> str | None:
    """Absolute HTTPS URL of the scan page, None without an HTTPS URL."""
    try:
        base = get_url(hass, require_ssl=True, prefer_external=True)
    except NoURLAvailableError:
        return None
    return base + URL_PATH.format(flow_id=flow_id)


def _is_pronote_qr(text: str) -> bool:
    try:
        qr_code = json.loads(text)
    except (TypeError, ValueError):
        return False
    return isinstance(qr_code, dict) and "jeton" in qr_code and "url" in qr_code


def _flow_waits_for_scan(hass: HomeAssistant, flow_id: str) -> bool:
    try:
        flow = hass.config_entries.flow.async_get(flow_id)
    except UnknownFlow:
        return False
    return flow["handler"] == DOMAIN and flow["step_id"] in SCAN_STEP_IDS


class QrScanView(HomeAssistantView):
    """Scan page (GET) and the QR code it reads (POST)."""

    url = URL_PATH
    name = "api:pronote:qr_scan"
    # Opened in a new tab without the HA token, like an OAuth callback: the
    # flow id is the key, and only a Pronote flow waiting on a scan step is fed.
    requires_auth = False

    def __init__(self, page: str) -> None:
        self._page = page

    async def get(self, request: web.Request, flow_id: str) -> web.Response:
        if not _flow_waits_for_scan(request.app[KEY_HASS], flow_id):
            return web.Response(status=404)
        return web.Response(text=self._page, content_type="text/html")

    async def post(self, request: web.Request, flow_id: str) -> web.Response:
        hass = request.app[KEY_HASS]
        if not _flow_waits_for_scan(hass, flow_id):
            return self.json_message("Unknown flow", 404)
        try:
            qr_code = (await request.json())["qr"]
        except (ValueError, KeyError, TypeError):
            qr_code = None
        if not isinstance(qr_code, str) or not _is_pronote_qr(qr_code):
            return self.json_message("Not a Pronote QR code", 400)
        await hass.config_entries.flow.async_configure(
            flow_id=flow_id, user_input={"qr_code_json": qr_code}
        )
        return self.json({"ok": True})
