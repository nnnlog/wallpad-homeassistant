"""The two elevator calls."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import WallpadError
from .const import CONTROL_CALL_DOWN, CONTROL_CALL_UP
from .coordinator import ElevatorCoordinator, WallpadConfigEntry
from .entity import WallpadEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WallpadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            CallButton(coordinator, "call_up", CONTROL_CALL_UP, "mdi:arrow-up-bold"),
            CallButton(coordinator, "call_down", CONTROL_CALL_DOWN, "mdi:arrow-down-bold"),
        ]
    )


class CallButton(WallpadEntity, ButtonEntity):
    def __init__(
        self, coordinator: ElevatorCoordinator, key: str, control_id: str, icon: str
    ) -> None:
        super().__init__(coordinator, key)
        self._control_id = control_id
        self._attr_translation_key = key
        self._attr_icon = icon

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.call(self._control_id)
        except WallpadError as err:
            raise HomeAssistantError(str(err)) from err
