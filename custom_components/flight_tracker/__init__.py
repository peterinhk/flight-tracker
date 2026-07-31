"""Flight Tracker - Home Assistant Custom Integration

Aggregates live flight data from ADSB.fi, ADSB.lol, ADSB.com and Planespotters.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import DOMAIN as DOMAIN
from .const import FRONTEND_CARD_FILENAME, FRONTEND_STATIC_PATH, PLATFORMS
from .coordinator import FlightTrackerCoordinator
from .services import async_setup_services

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Flight Tracker integration (services and Lovelace card)."""
    await async_setup_services(hass)
    await _async_register_frontend_card(hass)
    return True


async def _async_register_frontend_card(hass: HomeAssistant) -> None:
    """Serve the bundled Lovelace card and register it as a frontend resource."""
    # hass.http/hass.data buckets used below only exist once these components'
    # own async_setup has run; frontend depends on http, so setting up frontend
    # first guarantees both are ready.
    await async_setup_component(hass, "frontend", {})

    www_path = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_STATIC_PATH, str(www_path), cache_headers=False)]
    )

    add_extra_js_url(hass, f"{FRONTEND_STATIC_PATH}/{FRONTEND_CARD_FILENAME}")


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
