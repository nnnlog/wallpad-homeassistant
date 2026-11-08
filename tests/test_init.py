"""Setting up, tearing down, and what a lost connection looks like."""

from aiohttp.test_utils import unused_port
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wallpad_server.const import DOMAIN

from .conftest import HOST, FakeWallpad, snapshot, wait_until

_ENTITIES = ("sensor.elevator_car_1", "button.elevator_call_up", "button.elevator_call_down")


def _state(hass: HomeAssistant, entity_id: str) -> str:
    return hass.states.get(entity_id).state


async def test_setup_and_unload(
    hass: HomeAssistant, entry: MockConfigEntry, server: FakeWallpad
) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    await wait_until(lambda: entry.runtime_data.last_update_success)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    await wait_until(lambda: server.sockets[0].closed)


async def test_a_server_that_is_down_is_retried(hass: HomeAssistant, socket_enabled: None) -> None:
    down = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST, CONF_PORT: unused_port()})
    down.add_to_hass(hass)
    await hass.config_entries.async_setup(down.entry_id)
    await hass.async_block_till_done()
    assert down.state is ConfigEntryState.SETUP_RETRY


async def test_buttons_wait_for_the_first_snapshot(
    hass: HomeAssistant, entry: MockConfigEntry, server: FakeWallpad
) -> None:
    server.first_message = {"error": {"message": "nothing yet"}}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await wait_until(lambda: server.connections == 1)
    assert _state(hass, "button.elevator_call_up") == STATE_UNAVAILABLE
    await server.push(snapshot("3F"))
    await wait_until(lambda: _state(hass, "button.elevator_call_up") != STATE_UNAVAILABLE)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_a_lost_connection_makes_everything_unavailable_until_it_returns(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeWallpad
) -> None:
    for entity_id in _ENTITIES:
        assert _state(hass, entity_id) != STATE_UNAVAILABLE
    server.refuse_sockets = True
    await server.drop_connections()
    await wait_until(lambda: _state(hass, "button.elevator_call_up") == STATE_UNAVAILABLE)
    for entity_id in _ENTITIES:
        assert _state(hass, entity_id) == STATE_UNAVAILABLE

    # A floor nobody has seen, so what shows afterwards came from the new connection.
    server.first_message = snapshot("7F, -, B1")
    server.refuse_sockets = False
    await wait_until(lambda: _state(hass, "sensor.elevator_car_1") == "7F")
    for entity_id in _ENTITIES:
        assert _state(hass, entity_id) != STATE_UNAVAILABLE
    assert server.connections == 2
