"""Adding the integration: the address is asked for, and checked before it is kept."""

from unittest.mock import patch

import pytest
import voluptuous as vol
from aiohttp.test_utils import unused_port
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wallpad_server.const import DOMAIN

from .conftest import HOST, FakeWallpad, elevator_feature


async def _submit(hass: HomeAssistant, host: str, port: int):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: host, CONF_PORT: port}
    )


async def test_the_form_has_no_address_of_its_own(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    keys = {str(key): key for key in result["data_schema"].schema}
    assert set(keys) == {CONF_HOST, CONF_PORT}
    for key in keys.values():
        assert isinstance(key, vol.Required)
        assert key.default is vol.UNDEFINED


async def test_a_reachable_server_is_kept(hass: HomeAssistant, server: FakeWallpad) -> None:
    with patch("custom_components.wallpad_server.async_setup_entry", return_value=True):
        result = await _submit(hass, HOST, server.port)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: HOST, CONF_PORT: server.port}
    assert result["result"].unique_id == f"{HOST}:{server.port}"


async def test_an_unreachable_server_is_refused(hass: HomeAssistant, socket_enabled: None) -> None:
    result = await _submit(hass, HOST, unused_port())
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    "features",
    [
        pytest.param([], id="no elevator"),
        pytest.param(
            [{**elevator_feature(), "capability": {"controls": []}}], id="no call controls"
        ),
    ],
)
async def test_a_server_without_elevator_calls_is_refused(
    hass: HomeAssistant, server: FakeWallpad, features: list
) -> None:
    server.features = features
    result = await _submit(hass, HOST, server.port)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_elevator"}


async def test_the_same_server_is_not_added_twice(hass: HomeAssistant, server: FakeWallpad) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=f"{HOST}:{server.port}").add_to_hass(hass)
    result = await _submit(hass, HOST, server.port)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
