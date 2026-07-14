"""Entity manager for dynamic flight device trackers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, ENTITY_STALE_THRESHOLD_SECONDS
from .device_tracker import FlightDeviceTracker

_LOGGER = logging.getLogger(__name__)


class FlightTrackerEntityManager:
    """Manages dynamic creation/removal of flight device tracker entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: Any,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize the entity manager."""
        self.hass = hass
        self.coordinator = coordinator
        self.async_add_entities = async_add_entities
        self._entities: dict[str, FlightDeviceTracker] = {}
        self._stale_timestamps: dict[str, float] = {}

    async def update_entities(self) -> None:
        """Update entities based on current flight data."""
        current_flights = set(self.coordinator.data.flights.keys())
        existing_entities = set(self._entities.keys())

        # Add new entities
        new_flights = current_flights - existing_entities
        if new_flights:
            new_entities = [
                FlightDeviceTracker(self.coordinator, hex_code)
                for hex_code in new_flights
            ]
            self.async_add_entities(new_entities)
            for entity in new_entities:
                self._entities[entity._flight_hex] = entity
            _LOGGER.debug("Added %d new flight entities", len(new_entities))

        # Remove stale entities
        for hex_code in existing_entities - current_flights:
            if hex_code in self._entities:
                entity = self._entities[hex_code]
                # Mark for delayed removal to avoid flicker
                self._stale_timestamps[hex_code] = self.hass.loop.time()

        # Check stale entities for actual removal
        await self._cleanup_stale_entities()

    async def _cleanup_stale_entities(self) -> None:
        """Remove entities that have been stale for too long."""
        now = self.hass.loop.time()
        to_remove = []

        for hex_code, stale_time in self._stale_timestamps.items():
            if now - stale_time > ENTITY_STALE_THRESHOLD_SECONDS:
                if hex_code in self._entities:
                    entity = self._entities[hex_code]
                    await entity.async_remove()
                    del self._entities[hex_code]
                    to_remove.append(hex_code)
                    _LOGGER.debug("Removed stale flight entity: %s", hex_code)

        for hex_code in to_remove:
            del self._stale_timestamps[hex_code]

    async def cleanup_stale_entities(self, current_flight_hexes: list[str]) -> None:
        """Clean up entities not in current flight list."""
        current_set = set(current_flight_hexes)
        for hex_code in list(self._entities.keys()):
            if hex_code not in current_set:
                if hex_code not in self._stale_timestamps:
                    self._stale_timestamps[hex_code] = self.hass.loop.time()