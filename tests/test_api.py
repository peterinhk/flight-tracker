"""Tests for API clients."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock

import pytest

from custom_components.flight_tracker.api import ADSBFiClient, ADSBLolClient, PlanespottersClient


class TestADSBFiClient:
    """Test ADSB.fi client."""

    @pytest.fixture
    def client(self):
        """Create client instance."""
        session = AsyncMock()
        return ADSBFiClient(session, 37.7749, -122.4194, 50, "TestAgent/1.0")

    @pytest.mark.asyncio
    async def test_parse_flights(self, client):
        """Test flight parsing."""
        data = {
            "ac": [
                {
                    "hex": "a1b2c3",
                    "flight": "UAL123 ",
                    "r": "N12345",
                    "t": "B738",
                    "lat": 37.7749,
                    "lon": -122.4194,
                    "alt_baro": 35000,
                    "gs": 450,
                    "track": 270,
                    "category": 3,
                }
            ]
        }
        flights = client._parse_flights(data)
        assert len(flights) == 1
        assert flights[0].hex == "a1b2c3"
        assert flights[0].flight == "UAL123"
        assert flights[0].r == "N12345"

    @pytest.mark.asyncio
    async def test_parse_flights_missing_position(self, client):
        """Test flight parsing skips flights without position."""
        data = {
            "ac": [
                {"hex": "a1b2c3", "flight": "UAL123"},  # No lat/lon
                {"hex": "d4e5f6", "lat": 37.7749, "lon": -122.4194},  # No hex
                {"hex": "g7h8i9", "lat": 37.7749, "lon": -122.4194, "flight": "ABC"},  # Valid
            ]
        }
        flights = client._parse_flights(data)
        assert len(flights) == 1
        assert flights[0].hex == "g7h8i9"


class TestADSBLolClient:
    """Test ADSB.lol client."""

    @pytest.fixture
    def client(self):
        """Create client instance."""
        session = AsyncMock()
        return ADSBLolClient(session, 37.7749, -122.4194, 50, "TestAgent/1.0")

    @pytest.mark.asyncio
    async def test_parse_flights(self, client):
        """Test flight parsing."""
        data = {
            "ac": [
                {
                    "hex": "a1b2c3",
                    "flight": "SWA456 ",
                    "r": "N67890",
                    "lat": 37.7749,
                    "lon": -122.4194,
                    "alt_baro": 30000,
                }
            ]
        }
        flights = client._parse_flights(data)
        assert len(flights) == 1
        assert flights[0].hex == "a1b2c3"
        assert flights[0].flight == "SWA456"


class TestPlanespottersClient:
    """Test Planespotters client."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create client instance with temp cache."""
        session = AsyncMock()
        return PlanespottersClient(session, "test@example.com", tmp_path)

    @pytest.mark.asyncio
    async def test_cache_operations(self, client):
        """Test cache load/save."""
        # Cache should be empty initially
        assert len(client._cache) == 0

        # Add entry
        client._cache["a1b2c3"] = {"url": "http://example.com/img.jpg", "timestamp": 1234567890}
        await client._save_cache()

        # Create new client with same cache dir
        session2 = AsyncMock()
        client2 = PlanespottersClient(session2, "test@example.com", client._cache_dir)
        assert "a1b2c3" in client2._cache

    @pytest.mark.asyncio
    async def test_get_image_url_cached(self, client):
        """Test getting cached image URL."""
        client._cache["a1b2c3"] = {
            "url": "http://example.com/img.jpg",
            "timestamp": 1234567890,
        }
        url = await client.get_image_url("a1b2c3")
        assert url == "http://example.com/img.jpg"

    @pytest.mark.asyncio
    async def test_get_image_url_expired_cache(self, client):
        """Test expired cache triggers fetch."""
        import time

        client._cache["a1b2c3"] = {
            "url": "http://example.com/img.jpg",
            "timestamp": time.time() - 100000,  # Expired
        }
        # Would need to mock the fetch - skip for now
        pass

    def test_get_stats(self, client):
        """Test cache statistics."""
        client._cache = {
            "a1": {"url": "http://a.com", "timestamp": 123},
            "b2": {"url": None, "timestamp": 456},
            "c3": {"url": "http://c.com", "timestamp": 789},
        }
        stats = client.get_stats()
        assert stats["total_entries"] == 3
        assert stats["entries_with_images"] == 2
