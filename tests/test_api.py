"""Tests for API clients."""

import asyncio
import contextlib
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import AsyncMock

import pytest

from custom_components.flight_tracker.api import ADSBFiClient, ADSBLolClient, PlanespottersClient, _photo_credit


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
                {"hex": "d4e5f6", "lat": 37.7749, "lon": -122.4194},  # No flight
                {"hex": "g7h8i9", "lat": 37.7749, "lon": -122.4194, "flight": "ABC"},  # Valid
            ]
        }
        flights = client._parse_flights(data)
        # Two flights have valid hex + lat/lon (d4e5f6 and g7h8i9)
        assert len(flights) == 2
        assert flights[0].hex == "d4e5f6"
        assert flights[1].hex == "g7h8i9"


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

    def test_user_agent_format(self, client):
        """User-Agent must follow Planespotters' documented convention
        ('AppName/Version (+contact-uri)') - the previous bare-email format
        got a 403 directly naming this requirement."""
        assert client._user_agent.startswith("flight-tracker/")
        assert "(+mailto:test@example.com)" in client._user_agent

    @pytest.mark.asyncio
    async def test_fetch_by_hex_logs_unexpected_status(self, tmp_path, caplog):
        """A non-200/404 response (e.g. a 403 block) must be logged - it
        previously fell through completely silently, making a systemic block
        indistinguishable from 'this aircraft has no photo.'"""

        class _FakeResponse:
            status = 403

            async def text(self):
                return '{"error": "403 Forbidden"}'

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

        class _FakeSession:
            def get(self, *args, **kwargs):
                return _FakeResponse()

        client = PlanespottersClient(_FakeSession(), "test@example.com", tmp_path)
        with caplog.at_level(logging.WARNING):
            result = await client._fetch_by_hex("a1b2c3")
        assert result is None
        assert any("403" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_cache_operations(self, client):
        """Test cache load/save."""
        # Cache should be empty initially
        assert len(client._cache) == 0

        # Add entry with current timestamp
        import time

        client._cache["a1b2c3"] = {"url": "http://example.com/img.jpg", "timestamp": time.time()}
        await client._save_cache()

        # Create new client with same cache dir
        session2 = AsyncMock()
        client2 = PlanespottersClient(session2, "test@example.com", client._cache_dir)
        assert "a1b2c3" in client2._cache

    @pytest.mark.asyncio
    async def test_get_image_url_cached(self, client):
        """Test getting cached image URL."""
        import time

        client._cache["a1b2c3"] = {
            "url": "http://example.com/img.jpg",
            "timestamp": time.time(),  # Current time - valid cache
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

    def test_get_cached_image_hit(self, client):
        """Test the synchronous, no-network cache accessor returns a fresh entry."""
        import time

        client._cache["a1b2c3"] = {
            "url": "http://example.com/img.jpg",
            "photographer": "Jane Doe",
            "link": "http://example.com/photo/1",
            "timestamp": time.time(),
        }
        entry = client.get_cached_image("A1B2C3")
        assert entry is not None
        assert entry["url"] == "http://example.com/img.jpg"
        assert entry["photographer"] == "Jane Doe"

    def test_get_cached_image_miss(self, client):
        """Test the cache accessor returns None for an uncached hex."""
        assert client.get_cached_image("deadbe") is None

    def test_get_cached_image_expired(self, client):
        """Test the cache accessor treats an expired entry as a miss."""
        import time

        client._cache["a1b2c3"] = {
            "url": "http://example.com/img.jpg",
            "timestamp": time.time() - 100000,
        }
        assert client.get_cached_image("a1b2c3") is None

    @pytest.mark.asyncio
    async def test_preload_images_queues_new_hex(self, client):
        """A new, uncached hex gets marked pending so it isn't double-queued."""
        await client.preload_images([{"hex": "aa1111", "registration": None}])
        assert "aa1111" in client._pending
        # Let the background task run to completion so pytest doesn't warn
        # about a destroyed pending task at teardown.
        for task in list(client._background_tasks):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    @pytest.mark.asyncio
    async def test_preload_images_does_not_requeue_pending_hex(self, client):
        """A hex already marked pending (an in-flight/queued fetch) isn't
        queued again by a later call - this is the fix for the bug where
        firing one concurrent task per flight burst-triggered Planespotters'
        rate limiting and left every flight but the first without a photo."""
        client._pending.add("aa1111")
        await client.preload_images([{"hex": "aa1111", "registration": None}])
        assert client._background_tasks == set()

    @pytest.mark.asyncio
    async def test_preload_images_skips_fresh_cache_entry(self, client):
        """A hex with a fresh cache entry isn't queued at all."""
        import time

        client._cache["aa1111"] = {"url": "http://example.com/img.jpg", "timestamp": time.time()}
        await client.preload_images([{"hex": "aa1111", "registration": None}])
        assert "aa1111" not in client._pending
        assert client._background_tasks == set()


class TestPhotoCredit:
    """Test the photographer/link extraction helper."""

    def test_extracts_photographer_and_link(self):
        photographer, link = _photo_credit(
            {"photographer": "Jane Doe", "link": "https://www.planespotters.net/photo/123"}
        )
        assert photographer == "Jane Doe"
        assert link == "https://www.planespotters.net/photo/123"

    def test_missing_fields_return_none(self):
        photographer, link = _photo_credit({})
        assert photographer is None
        assert link is None

    def test_blank_fields_return_none(self):
        photographer, link = _photo_credit({"photographer": "  ", "link": ""})
        assert photographer is None
        assert link is None
