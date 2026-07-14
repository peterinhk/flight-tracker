"""Services for Flight Tracker integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CALLSIGN,
    ATTR_ICAO24,
    ATTR_REGISTRATION,
    DOMAIN,
    SERVICE_CENTER_MAP,
    SERVICE_GET_FLIGHT_IMAGE,
    SERVICE_REFRESH,
)
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


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Flight Tracker."""

    async def handle_refresh(call: ServiceCall) -> None:
        """Handle refresh service call."""
        source = call.data.get("source")
        for entry_id in hass.data.get(DOMAIN, {}):
            coordinator: FlightTrackerCoordinator = hass.data[DOMAIN][entry_id].runtime_data
            if source is None or source in coordinator.enabled_sources:
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
        for entry_id in hass.data.get(DOMAIN, {}):
            coordinator: FlightTrackerCoordinator = hass.data[DOMAIN][entry_id].runtime_data
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
                    image_url = await coordinator.planespotters.get_image_url(
                        flight.icao24, flight.registration
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

    # Register services
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, handle_refresh, schema=REFRESH_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_CENTER_MAP, handle_center_map, schema=CENTER_MAP_SCHEMA
    )

    hass.services.async_register(
        DOMAIN, SERVICE_GET_FLIGHT_IMAGE, handle_get_flight_image,
        schema=GET_FLIGHT_IMAGE_SCHEMA, supports_response=SupportsResponse.ONLY
    )

    _LOGGER.info("Flight Tracker services registered")


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services."""
    hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    hass.services.async_remove(DOMAIN, SERVICE_CENTER_MAP)
    hass.services.async_remove(DOMAIN, SERVICE_GET_FLIGHT_IMAGE)
