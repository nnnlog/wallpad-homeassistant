"""What the floor sensors show."""

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import FakeWallpad, snapshot, wait_until


def _floor(hass: HomeAssistant, car: int) -> str | None:
    state = hass.states.get(f"sensor.elevator_car_{car}")
    return state.state if state is not None else None


async def test_each_car_shows_its_floor(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    assert _floor(hass, 1) == "3F"
    assert _floor(hass, 2) == STATE_UNKNOWN
    assert _floor(hass, 3) == "B1"
    assert _floor(hass, 4) is None


async def test_a_push_moves_a_car(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeWallpad
) -> None:
    await server.push(snapshot("4F, 2F, B1"))
    await wait_until(lambda: _floor(hass, 1) == "4F")
    assert _floor(hass, 2) == "2F"


async def test_a_car_is_added_when_it_first_appears(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeWallpad
) -> None:
    await server.push(snapshot("3F, -, B1, 9F"))
    await wait_until(lambda: _floor(hass, 4) == "9F")


async def test_positions_going_away_leave_the_floors_unknown(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeWallpad
) -> None:
    await server.push(snapshot("no positions"))
    await wait_until(lambda: _floor(hass, 1) == STATE_UNKNOWN)
    assert _floor(hass, 3) == STATE_UNKNOWN


async def test_a_change_to_another_feature_writes_nothing(
    hass: HomeAssistant, loaded: MockConfigEntry, server: FakeWallpad
) -> None:
    updates: list[None] = []
    remove = loaded.runtime_data.async_add_listener(lambda: updates.append(None))
    await server.push(snapshot("3F, -, B1", other="streaming"))
    # The socket keeps order, so once this one has landed the one before it has been handled.
    await server.push(snapshot("4F, -, B1"))
    await wait_until(lambda: _floor(hass, 1) == "4F")
    remove()
    assert len(updates) == 1
