"""Client for the wallpad server's API: one REST read and the control WebSocket."""

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import aiohttp
from yarl import URL

from . import const

_LOGGER = logging.getLogger(__name__)

_NO_POSITIONS = "no positions"
_NO_FLOOR = "-"


class WallpadError(Exception):
    """A request to the wallpad server failed. The message is written for the user."""


class CannotConnectError(WallpadError):
    """The server could not be reached."""


class NoElevatorError(WallpadError):
    """The server answered but offers no elevator calls."""


@dataclass(frozen=True)
class ElevatorState:
    """The floor of each car in car order. ``None`` is a car with no known floor."""

    cars: tuple[str | None, ...]


def _parse_cars(row: str) -> tuple[str | None, ...]:
    """Read the ``cars`` status row, for example ``6F, -, B2``."""
    if not row or row == _NO_POSITIONS:
        return ()
    return tuple(None if car == _NO_FLOOR else car for car in row.split(", "))


def _elevator_state(snapshot: dict[str, Any]) -> ElevatorState:
    for status in snapshot.get("statuses", []):
        if status.get("featureId") == const.FEATURE_ID:
            return ElevatorState(_parse_cars(status.get("fields", {}).get("cars", "")))
    return ElevatorState(())


class WallpadClient:
    """One server. ``run`` holds the socket that ``call`` sends on."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int) -> None:
        self._session = session
        self._host = host
        self._port = port
        self._socket: aiohttp.ClientWebSocketResponse | None = None
        self._last_state: ElevatorState | None = None
        self._last_id = 0
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}

    def _url(self, scheme: str, path: str) -> URL:
        return URL.build(scheme=scheme, host=self._host, port=self._port, path=path)

    async def check_elevator(self) -> None:
        """Raise unless the server is reachable and offers both elevator calls."""
        try:
            async with (
                asyncio.timeout(const.REQUEST_TIMEOUT_S),
                self._session.get(self._url("http", const.FEATURES_PATH)) as response,
            ):
                response.raise_for_status()
                body = await response.json(content_type=None)
        except (aiohttp.ClientError, OSError, ValueError) as err:
            raise CannotConnectError(f"could not reach the wallpad server: {err}") from err
        features = body.get("features", []) if isinstance(body, dict) else []
        for feature in features:
            if feature.get("id") == const.FEATURE_ID:
                controls = feature.get("capability", {}).get("controls", [])
                offered = {control.get("id") for control in controls}
                if {const.CONTROL_CALL_UP, const.CONTROL_CALL_DOWN} <= offered:
                    return
        raise NoElevatorError("the wallpad server does not offer elevator calls")

    async def run(
        self,
        on_state: Callable[[ElevatorState], None],
        on_disconnect: Callable[[], None],
    ) -> None:
        """Stay connected until cancelled, reporting each change and each lost connection."""
        delay = const.RECONNECT_MIN_S
        while True:
            try:
                async with asyncio.timeout(const.REQUEST_TIMEOUT_S):
                    socket = await self._session.ws_connect(
                        self._url("ws", const.SOCKET_PATH), heartbeat=const.HEARTBEAT_S
                    )
            except (aiohttp.ClientError, OSError) as err:
                _LOGGER.debug("Could not connect to the wallpad server: %s", err)
            else:
                delay = const.RECONNECT_MIN_S
                await self._serve(socket, on_state)
            on_disconnect()
            await asyncio.sleep(delay)
            delay = min(delay * 2, const.RECONNECT_MAX_S)

    async def _serve(
        self,
        socket: aiohttp.ClientWebSocketResponse,
        on_state: Callable[[ElevatorState], None],
    ) -> None:
        self._socket = socket
        try:
            async for message in socket:
                if message.type is aiohttp.WSMsgType.TEXT:
                    self._receive(message.data, on_state)
        finally:
            self._socket = None
            self._last_state = None
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(WallpadError("the wallpad server connection was lost"))
            await socket.close()

    def _receive(self, text: str, on_state: Callable[[ElevatorState], None]) -> None:
        try:
            message = json.loads(text)
        except ValueError:
            _LOGGER.warning("Ignoring a message from the wallpad server that is not JSON")
            return
        if "snapshot" in message:
            # A snapshot goes out when any feature changes, so most leave the elevator as it was.
            state = _elevator_state(message["snapshot"])
            if state != self._last_state:
                self._last_state = state
                on_state(state)
            return
        future = self._pending.get(message.get("replyTo", 0))
        if future is not None and not future.done():
            future.set_result(message)

    async def call(self, control_id: str) -> None:
        """Send one elevator call and wait for its answer.

        Never resent. A call whose connection drops raises here, and the user decides whether to
        press again.
        """
        socket = self._socket
        if socket is None:
            raise WallpadError("not connected to the wallpad server")
        self._last_id += 1
        command_id = self._last_id
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[command_id] = future
        try:
            async with asyncio.timeout(const.INVOKE_TIMEOUT_S):
                await socket.send_json(
                    {
                        "id": command_id,
                        "invoke": {
                            "featureId": const.FEATURE_ID,
                            "controlId": control_id,
                            "params": {},
                        },
                    }
                )
                reply = await future
        except TimeoutError as err:
            raise WallpadError("the wallpad server did not answer") from err
        except (aiohttp.ClientError, ConnectionError) as err:
            raise WallpadError("the wallpad server connection was lost") from err
        finally:
            del self._pending[command_id]
        if "error" in reply:
            raise WallpadError(reply["error"]["message"])
        if not reply["result"]["ok"]:
            raise WallpadError(reply["result"]["message"])
