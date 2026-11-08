"""The two calls: what is sent, and what a failure looks like."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import FakeWallpad, wait_until


async def _press(hass: HomeAssistant, button: str) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": f"button.elevator_{button}"}, blocking=True
    )


@pytest.mark.parametrize(
    ("button", "control"),
    [("call_up", "call-up-here"), ("call_down", "call-down-here")],
)
async def test_a_press_sends_its_control(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeWallpad, button: str, control: str
) -> None:
    await _press(hass, button)
    assert server.commands == [
        {
            "id": 1,
            "invoke": {"featureId": "elevator", "controlId": control, "params": {}},
        }
    ]


async def test_a_refusal_reaches_the_user(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeWallpad
) -> None:
    server.answer = {
        "result": {"ok": False, "message": "not ready yet", "preview": "", "sent": False}
    }
    with pytest.raises(HomeAssistantError, match="not ready yet"):
        await _press(hass, "call_up")


async def test_an_error_reply_reaches_the_user(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeWallpad
) -> None:
    server.answer = {"error": {"message": "malformed command"}}
    with pytest.raises(HomeAssistantError, match="malformed command"):
        await _press(hass, "call_down")


async def test_a_server_that_never_answers_times_out(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeWallpad
) -> None:
    server.answer = None
    with (
        patch("custom_components.wallpad_server.const.INVOKE_TIMEOUT_S", 0.01),
        pytest.raises(HomeAssistantError, match="did not answer"),
    ):
        await _press(hass, "call_up")


async def test_a_call_cut_off_by_a_lost_connection_is_not_resent(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeWallpad
) -> None:
    server.answer = None
    press = hass.async_create_task(_press(hass, "call_up"))
    await wait_until(lambda: len(server.commands) == 1)
    await server.drop_connections()
    with pytest.raises(HomeAssistantError, match="connection was lost"):
        await press
    await wait_until(lambda: server.connections == 2)
    await hass.async_block_till_done()
    assert len(server.commands) == 1
