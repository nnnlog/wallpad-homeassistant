"""Asks for the server's address when the integration is added."""

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import CannotConnectError, NoElevatorError, WallpadClient
from .const import DOMAIN

_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str, vol.Required(CONF_PORT): cv.port})


class WallpadServerConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host, port = user_input[CONF_HOST].strip(), user_input[CONF_PORT]
            address = f"{host}:{port}"
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            client = WallpadClient(async_get_clientsession(self.hass), host, port)
            try:
                await client.check_elevator()
            except CannotConnectError:
                errors["base"] = "cannot_connect"
            except NoElevatorError:
                errors["base"] = "no_elevator"
            else:
                return self.async_create_entry(
                    title=address, data={CONF_HOST: host, CONF_PORT: port}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_SCHEMA, user_input),
            errors=errors,
        )
