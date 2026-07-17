"""Flight Tracker - Home Assistant Custom Integration

Aggregates live flight data from ADSB.fi, ADSB.lol, ADSB.com and Planespotters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN as DOMAIN
from .const import PLATFORMS
from .coordinator import FlightTrackerCoordinator

if TYPE_CHECKING:
    from .coordinator import FlightTrackerCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Flight Tracker from a config entry."""
    coordinator = FlightTrackerCoordinator(hass, entry)
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return bool(await hass.config_entries.async_unload_platforms(entry, PLATFORMS))


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    coordinator: FlightTrackerCoordinator = entry.runtime_data
    await coordinator.async_shutdown()
