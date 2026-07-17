"""Sensor entities for Flight Tracker."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .coordinator import FlightTrackerCoordinator

from homeassistant.components.sensor import (  # type: ignore[import-untyped]
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry  # type: ignore[import-untyped]
from homeassistant.const import (  # type: ignore[import-untyped]
    UnitOfLength,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant  # type: ignore[import-untyped]
from homeassistant.helpers.entity_platform import AddEntitiesCallback  # type: ignore[import-untyped]
from homeassistant.helpers.update_coordinator import CoordinatorEntity  # type: ignore[import-untyped]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: FlightTrackerCoordinator = entry.runtime_data

    entities = [
        TotalFlightsSensor(coordinator),
        NearestFlightSensor(coordinator),
        HighestFlightSensor(coordinator),
        FastestFlightSensor(coordinator),
        ImagesCachedSensor(coordinator),
        CategoryBreakdownSensor(coordinator),
        SourceBreakdownSensor(coordinator),
    ]

    async_add_entities(entities)


class FlightTrackerBaseSensor(CoordinatorEntity[FlightTrackerCoordinator], SensorEntity):
    """Base class for flight tracker sensors."""

    _attr_has_entity_name = True
    _attr_attribution = "Data from ADSB.fi, ADSB.lol, ADSB.com, Planespotters"

    def __init__(self, coordinator: FlightTrackerCoordinator, sensor_type: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._sensor_type = sensor_type
        self._attr_unique_id = f"flight_tracker_{sensor_type}"
        self._attr_name = sensor_type.replace("_", " ").title()


class TotalFlightsSensor(FlightTrackerBaseSensor):
    """Total flight count sensor."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "flights"
    _attr_icon = "mdi:airplane"

    def __init__(self, coordinator: FlightTrackerCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "total_flights")

    @property
    def native_value(self) -> int:
        """Return total flight count."""
        return len(self.coordinator.data.flights)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        stats = self.coordinator.data.stats
        return {
            "in_radius": stats.get("in_radius", 0),
            "by_category": stats.get("by_category", {}),
            "by_source": stats.get("by_source", {}),
            "last_update": stats.get("last_update"),
            "websocket_connected": self.coordinator.data.websocket_connected,
        }


class NearestFlightSensor(FlightTrackerBaseSensor):
    """Nearest flight sensor."""

    _attr_icon = "mdi:map-marker-distance"
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS

    def __init__(self, coordinator: FlightTrackerCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "nearest_flight")

    @property
    def native_value(self) -> float | None:
        """Return distance to nearest flight in km."""
        flights = self.coordinator.data.flights
        if not flights:
            return None

        nearest = min(flights.values(), key=lambda f: f.distance_km if f.distance_km is not None else float("inf"))
        return round(nearest.distance_km, 1) if nearest.distance_km else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attributes of nearest flight."""
        flights = self.coordinator.data.flights
        if not flights:
            return None

        nearest = min(flights.values(), key=lambda f: f.distance_km if f.distance_km is not None else float("inf"))

        return {
            "callsign": nearest.callsign,
            "registration": nearest.registration,
            "icao24": nearest.icao24,
            "altitude": nearest.altitude,
            "speed": nearest.speed,
            "heading": nearest.heading,
            "aircraft_type": nearest.aircraft_type,
            "operator": nearest.operator,
            "category": nearest.category_label,
            "image_url": nearest.image_url,
            "source_api": nearest.source_api,
            "last_seen": nearest.last_seen,
        }


class HighestFlightSensor(FlightTrackerBaseSensor):
    """Highest altitude flight sensor."""

    _attr_icon = "mdi:altimeter"
    _attr_native_unit_of_measurement = UnitOfLength.FEET
    _attr_device_class = SensorDeviceClass.DISTANCE

    def __init__(self, coordinator: FlightTrackerCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "highest_flight")

    @property
    def native_value(self) -> int | None:
        """Return highest altitude in feet."""
        flights = self.coordinator.data.flights
        if not flights:
            return None

        highest = max(flights.values(), key=lambda f: f.altitude if f.altitude is not None else -1)
        return highest.altitude if highest.altitude else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attributes of highest flight."""
        flights = self.coordinator.data.flights
        if not flights:
            return None

        highest = max(flights.values(), key=lambda f: f.altitude if f.altitude is not None else -1)

        return {
            "callsign": highest.callsign,
            "registration": highest.registration,
            "icao24": highest.icao24,
            "altitude": highest.altitude,
            "speed": highest.speed,
            "aircraft_type": highest.aircraft_type,
            "operator": highest.operator,
            "image_url": highest.image_url,
            "source_api": highest.source_api,
        }


class FastestFlightSensor(FlightTrackerBaseSensor):
    """Fastest flight sensor."""

    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = UnitOfSpeed.KNOTS

    def __init__(self, coordinator: FlightTrackerCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "fastest_flight")

    @property
    def native_value(self) -> float | None:
        """Return fastest speed in knots."""
        flights = self.coordinator.data.flights
        if not flights:
            return None

        fastest = max(flights.values(), key=lambda f: f.speed if f.speed is not None else -1)
        return fastest.speed if fastest.speed else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attributes of fastest flight."""
        flights = self.coordinator.data.flights
        if not flights:
            return None

        fastest = max(flights.values(), key=lambda f: f.speed if f.speed is not None else -1)

        return {
            "callsign": fastest.callsign,
            "registration": fastest.registration,
            "icao24": fastest.icao24,
            "altitude": fastest.altitude,
            "speed": fastest.speed,
            "heading": fastest.heading,
            "aircraft_type": fastest.aircraft_type,
            "operator": fastest.operator,
            "image_url": fastest.image_url,
            "source_api": fastest.source_api,
        }


class ImagesCachedSensor(FlightTrackerBaseSensor):
    """Images cached count sensor."""

    _attr_icon = "mdi:image"
    _attr_native_unit_of_measurement = "images"

    def __init__(self, coordinator: FlightTrackerCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "images_cached")

    @property
    def native_value(self) -> int | None:
        """Return number of cached images."""
        if self.coordinator.planespotters:
            stats = self.coordinator.planespotters.get_stats()
            return stats.get("entries_with_images", 0)
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return cache statistics."""
        if self.coordinator.planespotters:
            stats = self.coordinator.planespotters.get_stats()
            return dict(stats) if stats else {"total_entries": 0, "entries_with_images": 0, "negative_entries": 0}
        return {"total_entries": 0, "entries_with_images": 0, "negative_entries": 0}


class CategoryBreakdownSensor(FlightTrackerBaseSensor):
    """Flight category breakdown sensor."""

    _attr_icon = "mdi:chart-pie"
    _attr_native_unit_of_measurement = "flights"

    def __init__(self, coordinator: FlightTrackerCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "category_breakdown")

    @property
    def native_value(self) -> int:
        """Return total flights."""
        return len(self.coordinator.data.flights)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return category breakdown."""
        stats = self.coordinator.data.stats
        by_cat = stats.get("by_category", {})
        return dict(by_cat) if by_cat else {}


class SourceBreakdownSensor(FlightTrackerBaseSensor):
    """Data source breakdown sensor."""

    _attr_icon = "mdi:database"
    _attr_native_unit_of_measurement = "flights"

    def __init__(self, coordinator: FlightTrackerCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator, "source_breakdown")

    @property
    def native_value(self) -> int:
        """Return total flights."""
        return len(self.coordinator.data.flights)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return source breakdown."""
        stats = self.coordinator.data.stats
        by_src = stats.get("by_source", {})
        return dict(by_src) if by_src else {}
