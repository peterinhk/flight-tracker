"""Data coordinator for Flight Tracker integration."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import ADSBComClient, ADSBFiClient, ADSBLolClient, PlanespottersClient
from .const import (
    CONF_APIS_ENABLED,
    CONF_ENABLE_WEBSOCKET,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MAX_ALTITUDE,
    CONF_MAX_ENTITIES,
    CONF_MIN_ALTITUDE,
    CONF_PLANESPOTTERS_EMAIL,
    CONF_RADIUS_KM,
    CONF_SCAN_INTERVAL,
    CONF_TRACK_GA,
    CONF_TRACK_MILITARY,
    DEFAULT_ENABLE_WEBSOCKET,
    DEFAULT_MAX_ALTITUDE,
    DEFAULT_MAX_ENTITIES,
    DEFAULT_MIN_ALTITUDE,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACK_GA,
    DEFAULT_TRACK_MILITARY,
    DOMAIN,
)
from .models import CoordinatorData, Flight

_LOGGER = logging.getLogger(__name__)


class FlightTrackerCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinates data from multiple flight tracking APIs."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self.entry = entry
        self.session = async_get_clientsession(hass)

        # Config
        self.latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
        self.longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)
        self.radius_km = entry.data.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)
        self.scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self.enable_websocket = entry.data.get(CONF_ENABLE_WEBSOCKET, DEFAULT_ENABLE_WEBSOCKET)
        self.apis_enabled = entry.data.get(CONF_APIS_ENABLED, ["adsb_fi", "adsb_lol"])
        self.planespotters_email = entry.data.get(CONF_PLANESPOTTERS_EMAIL, "")
        self.min_altitude = entry.data.get(CONF_MIN_ALTITUDE, DEFAULT_MIN_ALTITUDE)
        self.max_altitude = entry.data.get(CONF_MAX_ALTITUDE, DEFAULT_MAX_ALTITUDE)
        self.track_military = entry.data.get(CONF_TRACK_MILITARY, DEFAULT_TRACK_MILITARY)
        self.track_ga = entry.data.get(CONF_TRACK_GA, DEFAULT_TRACK_GA)
        self.max_entities = entry.data.get(CONF_MAX_ENTITIES, DEFAULT_MAX_ENTITIES)

        # State
        self.data = CoordinatorData()
        self._adsb_fi: ADSBFiClient | None = None
        self._adsb_lol: ADSBLolClient | None = None
        self._adsb_com: ADSBComClient | None = None
        self.planespotters: PlanespottersClient | None = None
        self._entity_manager = None
        self._shutdown = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=self.scan_interval,
        )

    async def _async_setup(self) -> None:
        """Set up API clients."""
        if self.planespotters_email:
            user_agent = f"FlightTracker/1.0 ({self.planespotters_email})"
        else:
            user_agent = "FlightTracker/1.0"

        if "adsb_fi" in self.apis_enabled:
            self._adsb_fi = ADSBFiClient(
                self.session,
                self.latitude,
                self.longitude,
                self.radius_km,
                user_agent,
            )
            if self.enable_websocket:
                await self._adsb_fi.start_websocket(self._handle_ws_flights)

        if "adsb_lol" in self.apis_enabled:
            self._adsb_lol = ADSBLolClient(
                self.session,
                self.latitude,
                self.longitude,
                self.radius_km,
                user_agent,
            )
            if self.enable_websocket:
                await self._adsb_lol.start_websocket(self._handle_ws_flights)

        if "adsb_com" in self.apis_enabled:
            self._adsb_com = ADSBComClient(
                self.session,
                self.latitude,
                self.longitude,
                self.radius_km,
                user_agent,
            )

        if self.planespotters_email:
            from pathlib import Path

            cache_dir = Path(self.hass.config.path("storage", "flight_tracker"))
            self.planespotters = PlanespottersClient(
                self.session,
                self.planespotters_email,
                cache_dir,
            )

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch data from REST APIs."""
        if self._shutdown:
            return self.data

        # Fetch from all enabled APIs in parallel
        tasks = []
        if self._adsb_fi:
            tasks.append(self._fetch_adsb_fi())
        if self._adsb_lol:
            tasks.append(self._fetch_adsb_lol())
        if self._adsb_com:
            tasks.append(self._fetch_adsb_com())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge results
        new_flights: dict[str, Flight] = {}
        for result in results:
            if isinstance(result, Exception):
                _LOGGER.error("API fetch error: %s", result)
                continue
            if isinstance(result, list):
                for flight in result:
                    self._merge_flight(new_flights, flight)

        # Filter flights
        filtered_flights = self._filter_flights(new_flights)

        # Update data
        self.data.flights = filtered_flights
        self.data.last_update = time.time()
        self.data.websocket_connected = {
            "adsb_fi": self._adsb_fi.is_connected if self._adsb_fi else False,
            "adsb_lol": self._adsb_lol.is_connected if self._adsb_lol else False,
        }

        # Update stats
        self._update_stats()

        # Fetch images for new/updated flights
        if self.planespotters and filtered_flights:
            await self.planespotters.preload_images(
                [
                    {
                        "hex": f.hex,
                        "registration": f.registration,
                    }
                    for f in filtered_flights.values()
                ]
            )
            # Update image URLs
            for flight in filtered_flights.values():
                if flight.hex:
                    image_url = await self.planespotters.get_image_url(flight.hex, flight.registration)
                    if image_url:
                        flight.image_url = image_url

        # Clean up stale entities
        if self._entity_manager:
            await self._entity_manager.cleanup_stale_entities(list(filtered_flights.keys()))

        return self.data

    async def _fetch_adsb_fi(self) -> list[Flight]:
        """Fetch from ADSB.fi REST."""
        if not self._adsb_fi:
            return []
        raw_flights = await self._adsb_fi.fetch_rest()
        return [self._normalize_flight(f, "adsb_fi") for f in raw_flights]

    async def _fetch_adsb_lol(self) -> list[Flight]:
        """Fetch from ADSB.lol REST."""
        if not self._adsb_lol:
            return []
        raw_flights = await self._adsb_lol.fetch_rest()
        return [self._normalize_flight(f, "adsb_lol") for f in raw_flights]

    async def _fetch_adsb_com(self) -> list[Flight]:
        """Fetch from ADSB.com REST."""
        if not self._adsb_com:
            return []
        raw_flights = await self._adsb_com.fetch_rest()
        return [self._normalize_flight(f, "adsb_com") for f in raw_flights]

    def _normalize_flight(self, raw: Any, source: str) -> Flight:
        """Normalize raw flight data to Flight object."""
        return Flight(
            hex=raw.hex,
            callsign=raw.flight,
            registration=raw.r,
            icao24=raw.hex,
            latitude=raw.lat,
            longitude=raw.lon,
            altitude=raw.alt_baro,
            altitude_geometric=raw.alt_geom if hasattr(raw, "alt_geom") else None,
            speed=raw.gs,
            heading=raw.track,
            vertical_rate=raw.baro_rate if hasattr(raw, "baro_rate") else None,
            squawk=raw.squawk,
            category=raw.category,
            aircraft_type=raw.t,
            operator=None,
            source_api=source,
            rssi=raw.rssi if hasattr(raw, "rssi") else None,
            last_seen=raw.seen,
            last_seen_pos=raw.seen_pos if hasattr(raw, "seen_pos") else None,
        )

    def _merge_flight(self, flights: dict[str, Flight], new_flight: Flight) -> None:
        """Merge flight data, preferring newer/more complete data."""
        hex_code = new_flight.hex
        if hex_code not in flights:
            flights[hex_code] = new_flight
        else:
            existing = flights[hex_code]
            # Prefer WebSocket data (more recent) or more complete data
            if new_flight.last_seen and existing.last_seen:
                if new_flight.last_seen > existing.last_seen:
                    self._merge_fields(existing, new_flight)
            elif new_flight.source_api != existing.source_api:
                # Merge fields from both sources
                self._merge_fields(existing, new_flight)

    def _merge_fields(self, existing: Flight, new: Flight) -> None:
        """Merge fields from new flight into existing."""
        for field_name in [
            "callsign",
            "registration",
            "latitude",
            "longitude",
            "altitude",
            "altitude_geometric",
            "speed",
            "heading",
            "vertical_rate",
            "squawk",
            "category",
            "aircraft_type",
            "operator",
            "image_url",
            "last_seen",
            "last_seen_pos",
            "source_api",
            "rssi",
        ]:
            new_val = getattr(new, field_name)
            if new_val is not None:
                setattr(existing, field_name, new_val)

    def _filter_flights(self, flights: dict[str, Flight]) -> dict[str, Flight]:
        """Filter flights by configured criteria."""
        filtered = {}

        for hex_code, flight in flights.items():
            # Must have position
            if flight.latitude is None or flight.longitude is None:
                continue

            # Distance check
            distance = self._calculate_distance(self.latitude, self.longitude, flight.latitude, flight.longitude)
            flight.distance_km = distance
            if distance > self.radius_km:
                continue

            # Altitude filter
            alt = flight.altitude or flight.altitude_geometric or 0
            if alt < self.min_altitude or alt > self.max_altitude:
                continue

            # Category filter
            if flight.category is not None:
                if not self.track_military and flight.category in {3, 4, 5}:  # Heavy/military
                    continue
                if not self.track_ga and flight.category in {1, 2}:  # Light/Small
                    continue

            filtered[hex_code] = flight

        # Limit entities
        if len(filtered) > self.max_entities:
            # Sort by distance (closest first)
            sorted_flights = sorted(filtered.items(), key=lambda x: x[1].distance_km or float("inf"))
            filtered = dict(sorted_flights[: self.max_entities])

        return filtered

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in km using Haversine formula."""
        R = 6371  # Earth radius in km
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _update_stats(self) -> None:
        """Update statistics."""
        flights = self.data.flights
        categories = {}
        by_source = {}

        for flight in flights.values():
            cat = flight.category_label or "Unknown"
            categories[cat] = categories.get(cat, 0) + 1
            by_source[flight.source_api] = by_source.get(flight.source_api, 0) + 1

        self.data.stats = {
            "total": len(flights),
            "in_radius": len(flights),
            "by_category": categories,
            "by_source": by_source,
            "last_update": self.data.last_update,
        }

    async def _handle_ws_flights(self, flights: list[Any]) -> None:
        """Handle WebSocket flight updates."""
        if self._shutdown:
            return

        new_flights: dict[str, Flight] = {}
        for raw in flights:
            # Determine source from raw data - ADSB.fi has rssi, ADSB.lol doesn't
            source = "adsb_fi" if hasattr(raw, "rssi") and raw.rssi is not None else "adsb_lol"
            flight = self._normalize_flight(raw, source)
            self._merge_flight(new_flights, flight)

        # Filter and merge
        filtered = self._filter_flights(new_flights)
        for _hex_code, flight in filtered.items():
            self._merge_flight(self.data.flights, flight)

        # Update stats
        self._update_stats()

        # Trigger entity updates
        self.async_set_updated_data(self.data)

    def set_entity_manager(self, manager) -> None:
        """Set entity manager for cleanup."""
        self._entity_manager = manager

    async def async_shutdown(self) -> None:
        """Shutdown coordinator and WebSocket connections."""
        self._shutdown = True
        if self._adsb_fi:
            await self._adsb_fi.stop_websocket()
        if self._adsb_lol:
            await self._adsb_lol.stop_websocket()
        if self._adsb_com:
            await self._adsb_com.stop_websocket()
