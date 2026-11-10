"""Shared fixtures."""

from types import SimpleNamespace

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

import custom_components.pronote  # noqa: F401

QR = (
    '{"jeton": "' + "A" * 120 + '", "login": "ABCDEF123", '
    '"url": "https://x.index-education.net/pronote/mobile.parent.html"}'
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def https_ha(hass: HomeAssistant) -> None:
    """HA reachable over HTTPS from outside, as needed by the camera."""
    assert await async_setup_component(hass, "http", {})
    await hass.config.async_update(
        external_url="https://ha.example.com", internal_url="http://192.168.1.2:8123"
    )


@pytest.fixture
async def http_only_ha(hass: HomeAssistant) -> None:
    """HA only reachable over plain HTTP."""
    assert await async_setup_component(hass, "http", {})
    await hass.config.async_update(
        external_url="http://192.168.1.2:8123", internal_url="http://192.168.1.2:8123"
    )


def qr_client(username="tok-user", password="tok-pass", uuid="uuid-1"):
    """What get_client_from_qr_code returns for a parent account."""
    return SimpleNamespace(
        pronote_url="https://x.index-education.net/pronote/mobile.parent.html",
        username=username,
        password=password,
        uuid=uuid,
        info=SimpleNamespace(name="DUPONT Parent"),
        children=[SimpleNamespace(name="Alice"), SimpleNamespace(name="Bob")],
    )
