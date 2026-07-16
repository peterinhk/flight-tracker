"""Data models for Flight Tracker integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import CATEGORY_LABELS


@dataclass
class Flight:
    """Normalized flight data from all sources."""

    hex: str
    callsign: str | None = None
    registration: str | None = None
    icao24: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None  # barometric, feet
    altitude_geometric: float | None = None
    speed: float | None = None  # knots
    heading: float | None = None  # degrees
    vertical_rate: float | None = None  # fpm
    squawk: str | None = None
    category: int | None = None
    category_label: str | None = None
    aircraft_type: str | None = None
    operator: str | None = None
    origin: str | None = None
    destination: str | None = None
    image_url: str | None = None
    last_seen: float | None = None
    last_seen_pos: float | None = None
    source_api: str = "unknown"
    rssi: float | None = None
    distance_km: float | None = None

    def __post_init__(self):
        """Set defaults."""
        if self.icao24 is None:
            self.icao24 = self.hex
        if self.category_label is None and self.category is not None:
            self.category_label = CATEGORY_LABELS.get(self.category, "Unknown")


@dataclass
class CoordinatorData:
    """Data held by coordinator."""

    flights: dict[str, Flight] = field(default_factory=dict)  # hex -> Flight
    stats: dict[str, Any] = field(default_factory=dict)
    last_update: float = 0
    websocket_connected: dict[str, bool] = field(default_factory=dict)