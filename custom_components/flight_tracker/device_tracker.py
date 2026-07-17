"""Device tracker entities for Flight Tracker integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import (  # type: ignore[import-untyped]
    SourceType,
    TrackerEntity,
)
from homeassistant.config_entries import ConfigEntry  # type: ignore[import-untyped]
from homeassistant.core import HomeAssistant, callback  # type: ignore[import-untyped]
from homeassistant.helpers.entity import DeviceInfo  # type: ignore[import-untyped]
from homeassistant.helpers.entity_platform import AddEntitiesCallback  # type: ignore[import-untyped]
from homeassistant.helpers.update_coordinator import CoordinatorEntity  # type: ignore[import-untyped]

from .const import (
    ATTR_AIRCRAFT_TYPE,
    ATTR_ALTITUDE,
    ATTR_ALTITUDE_GEOMETRIC,
    ATTR_CALLSIGN,
    ATTR_CATEGORY,
    ATTR_CATEGORY_LABEL,
    ATTR_DESTINATION,
    ATTR_DISTANCE_KM,
    ATTR_HEADING,
    ATTR_ICAO24,
    ATTR_IMAGE_URL,
    ATTR_LAST_SEEN,
    ATTR_OPERATOR,
    ATTR_ORIGIN,
    ATTR_REGISTRATION,
    ATTR_RSSI,
    ATTR_SOURCE_API,
    ATTR_SPEED,
    ATTR_SQUAWK,
    ATTR_VERTICAL_RATE,
    DEVICE_TRACKER_ICON,
    DOMAIN,
)
from .models import Flight, FlightTrackerCoordinator
from .entity_manager import FlightTrackerEntityManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device tracker entities."""
    coordinator: FlightTrackerCoordinator = entry.runtime_data

    # Create entity manager
    entity_manager = FlightTrackerEntityManager(hass, coordinator, async_add_entities)
    coordinator._entity_manager = entity_manager

    # Initial entity creation
    await entity_manager.update_entities()


class FlightDeviceTracker(CoordinatorEntity[FlightTrackerCoordinator], TrackerEntity):
    """Device tracker for a flight."""

    _attr_icon = DEVICE_TRACKER_ICON
    _attr_source_type = SourceType.GPS
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FlightTrackerCoordinator,
        flight_hex: str,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._flight_hex = flight_hex
        self._attr_unique_id = f"{DOMAIN}_{flight_hex}"
        self._attr_name = None  # Use flight callsign/hex as name via property

    @property
    def flight(self) -> Flight | None:
        """Get flight data from coordinator."""
        return self.coordinator.data.flights.get(self._flight_hex)

    @property
    def latitude(self) -> float | None:
        """Return latitude."""
        if self.flight:
            return self.flight.latitude
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude."""
        if self.flight:
            return self.flight.longitude
        return None

    @property
    def name(self) -> str | None:
        """Return name for the flight."""
        if self.flight and self.flight.callsign:
            return self.flight.callsign.strip()
        return self._flight_hex.upper()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if not self.flight:
            return None

        f = self.flight
        return {
            ATTR_CALLSIGN: f.callsign,
            ATTR_REGISTRATION: f.registration,
            ATTR_ICAO24: f.icao24,
            ATTR_ALTITUDE: f.altitude,
            ATTR_ALTITUDE_GEOMETRIC: f.altitude_geometric,
            ATTR_SPEED: f.speed,
            ATTR_HEADING: f.heading,
            ATTR_VERTICAL_RATE: f.vertical_rate,
            ATTR_SQUAWK: f.squawk,
            ATTR_CATEGORY: f.category,
            ATTR_CATEGORY_LABEL: f.category_label,
            ATTR_AIRCRAFT_TYPE: f.aircraft_type,
            ATTR_OPERATOR: f.operator,
            ATTR_ORIGIN: f.origin,
            ATTR_DESTINATION: f.destination,
            ATTR_IMAGE_URL: f.image_url,
            ATTR_LAST_SEEN: f.last_seen,
            ATTR_SOURCE_API: f.source_api,
            ATTR_RSSI: f.rssi,
            ATTR_DISTANCE_KM: f.distance_km,
        }

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        if not self.flight:
            return None

        f = self.flight
        return DeviceInfo(
            identifiers={(DOMAIN, f.hex)},
            name=f.callsign or f.hex.upper(),
            manufacturer=f.operator or "Unknown",
            model=f.aircraft_type or "Unknown",
            entry_type=None,
            configuration_url=f.image_url if f.image_url else None,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from coordinator."""
        # Entity will be removed by entity manager if flight disappears
        super()._handle_coordinator_update()
