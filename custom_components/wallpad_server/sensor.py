"""One sensor per elevator car: the floor it is on."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ElevatorCoordinator, WallpadConfigEntry
from .entity import WallpadEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WallpadConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    added = 0

    @callback
    def add_new_cars() -> None:
        """The server says how many cars there are, so they are added as they appear."""
        nonlocal added
        count = len(coordinator.data.cars) if coordinator.data is not None else 0
        if count > added:
            async_add_entities(CarSensor(coordinator, n) for n in range(added + 1, count + 1))
            added = count

    entry.async_on_unload(coordinator.async_add_listener(add_new_cars))


class CarSensor(WallpadEntity, SensorEntity):
    _attr_icon = "mdi:elevator"
    _attr_translation_key = "car"

    def __init__(self, coordinator: ElevatorCoordinator, number: int) -> None:
        super().__init__(coordinator, f"car_{number}")
        self._index = number - 1
        self._attr_translation_placeholders = {"number": str(number)}

    @property
    def native_value(self) -> str | None:
        cars = self.coordinator.data.cars
        return cars[self._index] if self._index < len(cars) else None
