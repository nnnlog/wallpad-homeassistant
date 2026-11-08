"""A fake wallpad server on a real socket, speaking the JSON the real one speaks."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any
from unittest.mock import patch

import pytest
from aiohttp import WSMsgType, web
from aiohttp.test_utils import TestServer
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wallpad_server.const import DOMAIN

HOST = "127.0.0.1"


def elevator_feature() -> dict[str, Any]:
    return {
        "id": "elevator",
        "label": "Elevator",
        "capability": {
            "controls": [
                {"id": "call-up-here", "label": "Up", "deviceControl": True, "params": []},
                {"id": "call-down-here", "label": "Down", "deviceControl": True, "params": []},
            ],
            "monitors": [{"id": "cars", "label": "Cars"}],
            "handlers": [],
            "hasVideo": False,
            "hasAudio": False,
            "hasPlayback": False,
        },
        "system": False,
    }


def snapshot(cars: str, *, other: str = "stopped") -> dict[str, Any]:
    return {
        "snapshot": {
            "statuses": [
                {"featureId": "doorcam", "fields": {"state": other}},
                {"featureId": "elevator", "fields": {"state": "watching", "cars": cars}},
            ],
            "policy": {"mode": "locked", "armed": False, "remainingS": 0.0, "reason": ""},
        }
    }


class FakeWallpad:
    def __init__(self) -> None:
        self.features: list[dict[str, Any]] = [elevator_feature()]
        self.first_message: dict[str, Any] = snapshot("3F, -, B1")
        self.commands: list[dict[str, Any]] = []
        # What a command is answered with: a body, or None for no answer at all.
        self.answer: dict[str, Any] | None = {
            "result": {"ok": True, "message": "call queued", "preview": "", "sent": False}
        }
        self.sockets: list[web.WebSocketResponse] = []
        self.connections = 0
        self.refuse_sockets = False
        self.port = 0

    async def serve_features(self, _request: web.Request) -> web.Response:
        return web.json_response({"features": self.features})

    async def serve_socket(self, request: web.Request) -> web.WebSocketResponse:
        if self.refuse_sockets:
            raise web.HTTPServiceUnavailable
        socket = web.WebSocketResponse()
        await socket.prepare(request)
        self.connections += 1
        self.sockets.append(socket)
        await socket.send_json(self.first_message)
        async for message in socket:
            if message.type is WSMsgType.TEXT:
                command = json.loads(message.data)
                self.commands.append(command)
                if self.answer is not None:
                    await socket.send_json({**self.answer, "replyTo": command["id"]})
        return socket

    async def push(self, message: dict[str, Any]) -> None:
        for socket in self.sockets:
            await socket.send_json(message)

    async def drop_connections(self) -> None:
        sockets, self.sockets = self.sockets, []
        for socket in sockets:
            await socket.close()


async def wait_until(condition: Callable[[], bool]) -> None:
    """Real sockets are in play, so this waits on the event loop rather than on hass."""
    async with asyncio.timeout(5):
        while not condition():
            await asyncio.sleep(0.01)


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture(autouse=True)
def _quick_reconnect() -> Any:
    with patch("custom_components.wallpad_server.const.RECONNECT_MIN_S", 0.01):
        yield


@pytest.fixture
async def server(socket_enabled: None) -> AsyncIterator[FakeWallpad]:
    fake = FakeWallpad()
    app = web.Application()
    app.router.add_get("/api/v1/features", fake.serve_features)
    app.router.add_get("/api/v1/ws", fake.serve_socket)
    test_server = TestServer(app, host=HOST)
    await test_server.start_server()
    fake.port = test_server.port
    yield fake
    await fake.drop_connections()
    await test_server.close()


@pytest.fixture
def entry(hass: HomeAssistant, server: FakeWallpad) -> MockConfigEntry:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{HOST}:{server.port}",
        data={CONF_HOST: HOST, CONF_PORT: server.port},
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
async def loaded(
    hass: HomeAssistant, entry: MockConfigEntry, server: FakeWallpad
) -> AsyncIterator[MockConfigEntry]:
    """The integration set up, with the fake's first message already applied."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await wait_until(lambda: server.connections == 1 and entry.runtime_data.last_update_success)
    await hass.async_block_till_done()
    yield entry
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
