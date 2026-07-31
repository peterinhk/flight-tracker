from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol  # type: ignore[import-untyped]
from homeassistant.config_entries import ConfigEntryState  # type: ignore[import-untyped]
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse  # type: ignore[import-untyped]
from homeassistant.exceptions import ServiceValidationError  # type: ignore[import-untyped]
from homeassistant.helpers import config_validation as cv  # type: ignore[import-untyped]

from .const import (
    ATTR_CALLSIGN,
    ATTR_ICAO24,
    ATTR_REGISTRATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MAX_ALTITUDE,
    CONF_MIN_ALTITUDE,
    CONF_RADIUS_KM,
    CONF_TRACK_GA,
    CONF_TRACK_MILITARY,
    DOMAIN,
    SERVICE_CENTER_MAP,
    SERVICE_GET_FLIGHT_IMAGE,
    SERVICE_REFRESH,
    SERVICE_SET_SEARCH_PARAMS,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from .coordinator import FlightTrackerCoordinator

_LOGGER = logging.getLogger(__name__)

# Service schemas
REFRESH_SCHEMA = vol.Schema(
    {
        vol.Optional("source"): cv.string,
    }
)

CENTER_MAP_SCHEMA = vol.Schema(
    {
        vol.Required("latitude"): cv.latitude,
        vol.Required("longitude"): cv.longitude,
        vol.Optional("zoom"): vol.All(vol.Coerce(int), vol.Range(min=1, max=18)),
    }
)

GET_FLIGHT_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CALLSIGN): cv.string,
        vol.Optional(ATTR_REGISTRATION): cv.string,
        vol.Optional(ATTR_ICAO24): cv.string,
    }
)

SET_SEARCH_PARAMS_SCHEMA = vol.Schema(
    {
        vol.Optional("entry_id"): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_RADIUS_KM): vol.All(vol.Coerce(float), vol.Range(min=1, max=500)),
        vol.Optional(CONF_MIN_ALTITUDE): vol.All(vol.Coerce(float), vol.Range(min=0, max=60000)),
        vol.Optional(CONF_MAX_ALTITUDE): vol.All(vol.Coerce(float), vol.Range(min=0, max=60000)),
        vol.Optional(CONF_TRACK_MILITARY): cv.boolean,
        vol.Optional(CONF_TRACK_GA): cv.boolean,
    }
)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Flight Tracker."""

    async def handle_refresh(call: ServiceCall) -> None:
        """Handle refresh service call."""
        source = call.data.get("source")
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator: FlightTrackerCoordinator = entry.runtime_data
            if source is None or source in coordinator.apis_enabled:
                await coordinator.async_request_refresh()

    async def handle_center_map(call: ServiceCall) -> None:
        """Handle center map service call."""
        latitude = call.data["latitude"]
        longitude = call.data["longitude"]
        zoom = call.data.get("zoom", 10)

        # Fire event for frontend to center map
        hass.bus.async_fire(
            f"{DOMAIN}_center_map",
            {
                "latitude": latitude,
                "longitude": longitude,
                "zoom": zoom,
            },
        )

    async def handle_get_flight_image(call: ServiceCall) -> dict[str, Any]:
        """Handle get flight image service call."""
        callsign = call.data.get(ATTR_CALLSIGN)
        registration = call.data.get(ATTR_REGISTRATION)
        icao24 = call.data.get(ATTR_ICAO24)

        if not any([callsign, registration, icao24]):
            return {"success": False, "error": "At least one identifier required"}

        # Find flight in any coordinator
        for entry in hass.config_entries.async_entries(DOMAIN):
            coordinator: FlightTrackerCoordinator = entry.runtime_data
            flights = coordinator.data.flights

            flight = None
            if icao24:
                flight = flights.get(icao24.lower())
            elif callsign:
                flight = next((f for f in flights.values() if f.callsign == callsign), None)
            elif registration:
                flight = next((f for f in flights.values() if f.registration == registration), None)

            if flight:
                if flight.image_url:
                    return {
                        "success": True,
                        "image_url": flight.image_url,
                        "callsign": flight.callsign,
                        "registration": flight.registration,
                        "icao24": flight.icao24,
                    }
                else:
                    # Try to fetch
                    if coordinator.planespotters is not None:
                        image_url = await coordinator.planespotters.get_image_url(
                            flight.icao24 or flight.hex, flight.registration or ""
                        )
                        if image_url:
                            flight.image_url = image_url
                            return {
                                "success": True,
                                "image_url": image_url,
                                "callsign": flight.callsign,
                                "registration": flight.registration,
                                "icao24": flight.icao24,
                            }
                    return {"success": False, "error": "No image available"}

        return {"success": False, "error": "Flight not found"}

    def _target_entries(entry_id: str | None) -> list[ConfigEntry]:
        entries = [
            entry for entry in hass.config_entries.async_entries(DOMAIN) if entry.state is ConfigEntryState.LOADED
        ]
        if entry_id is not None:
            entries = [entry for entry in entries if entry.entry_id == entry_id]
            if not entries:
                raise ServiceValidationError(f"Unknown or unloaded Flight Tracker entry_id: {entry_id}")
        elif len(entries) > 1:
            raise ServiceValidationError(
                "Multiple Flight Tracker entries are configured; specify entry_id to target one"
            )
        return entries

    async def handle_set_search_params(call: ServiceCall) -> None:
        """Handle live search parameter updates (radius, position, altitude, filters)."""
        for entry in _target_entries(call.data.get("entry_id")):
            coordinator: FlightTrackerCoordinator = entry.runtime_data
            await coordinator.async_update_search_params(
                latitude=call.data.get(CONF_LATITUDE),
                longitude=call.data.get(CONF_LONGITUDE),
                radius_km=call.data.get(CONF_RADIUS_KM),
                min_altitude=call.data.get(CONF_MIN_ALTITUDE),
                max_altitude=call.data.get(CONF_MAX_ALTITUDE),
                track_military=call.data.get(CONF_TRACK_MILITARY),
                track_ga=call.data.get(CONF_TRACK_GA),
            )
            await coordinator.async_request_refresh()

    # Register services
    hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh, schema=REFRESH_SCHEMA)

    hass.services.async_register(DOMAIN, SERVICE_CENTER_MAP, handle_center_map, schema=CENTER_MAP_SCHEMA)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_FLIGHT_IMAGE,
        handle_get_flight_image,
        schema=GET_FLIGHT_IMAGE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SEARCH_PARAMS,
        handle_set_search_params,
        schema=SET_SEARCH_PARAMS_SCHEMA,
    )

    _LOGGER.info("Flight Tracker services registered")


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services."""
    hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    hass.services.async_remove(DOMAIN, SERVICE_CENTER_MAP)
    hass.services.async_remove(DOMAIN, SERVICE_GET_FLIGHT_IMAGE)
    hass.services.async_remove(DOMAIN, SERVICE_SET_SEARCH_PARAMS)
