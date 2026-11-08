"""Elevator position and calls from a wallpad server."""

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import WallpadClient, WallpadError
from .const import DOMAIN
from .coordinator import ElevatorCoordinator, WallpadConfigEntry

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WallpadConfigEntry) -> bool:
    client = WallpadClient(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_PORT]
    )
    try:
        await client.check_elevator()
    except WallpadError as err:
        raise ConfigEntryNotReady(str(err)) from err
    coordinator = ElevatorCoordinator(hass, entry, client)
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_create_background_task(
        hass,
        client.run(coordinator.handle_state, coordinator.handle_disconnect),
        f"{DOMAIN} connection",
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WallpadConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
