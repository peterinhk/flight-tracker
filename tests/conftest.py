"""Test configuration for pytest."""
import sys
from pathlib import Path

# Add custom_components to path
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components"))

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_hass():
    """Mock Home Assistant instance."""
    from unittest.mock import MagicMock
    hass = MagicMock()
    hass.config.latitude = 37.7749
    hass.config.longitude = -122.4194
    hass.config.path = MagicMock(return_value="/config")
    return hass


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    from unittest.mock import MagicMock

    from homeassistant.config_entries import ConfigEntry
    entry = MagicMock(spec=ConfigEntry)
    entry.data = {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "radius_km": 50,
        "scan_interval": 60,
        "apis_enabled": ["adsb_fi", "adsb_lol"],
        "planespotters_email": "test@example.com",
        "min_altitude": 0,
        "max_altitude": 60000,
        "track_military": False,
        "track_ga": True,
        "show_on_map": True,
    }
    entry.options = {}
    entry.entry_id = "test_entry"
    return entry
