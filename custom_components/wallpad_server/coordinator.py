"""Holds the latest elevator state and tells the entities when it changes."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import ElevatorState, WallpadClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type WallpadConfigEntry = ConfigEntry[ElevatorCoordinator]


class ElevatorCoordinator(DataUpdateCoordinator[ElevatorState]):
    """Fed by the client's socket, so it has no update interval."""

    config_entry: WallpadConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: WallpadConfigEntry, client: WallpadClient
    ) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN)
        self.client = client
        # Entities stay unavailable until the first snapshot arrives.
        self.last_update_success = False

    @callback
    def handle_state(self, state: ElevatorState) -> None:
        self.async_set_updated_data(state)

    @callback
    def handle_disconnect(self) -> None:
        self.async_set_update_error(ConnectionError("the connection was lost"))
