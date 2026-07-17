"""API clients for flight tracking data sources."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import aiofiles
import aiohttp

_LOGGER = logging.getLogger(__name__)


@dataclass
class FlightData:
    """Raw flight data from API."""

    hex: str
    flight: str | None = None
    r: str | None = None  # registration
    t: str | None = None  # aircraft type
    lat: float | None = None
    lon: float | None = None
    alt_baro: float | None = None
    alt_geom: float | None = None
    gs: float | None = None  # ground speed
    track: float | None = None  # heading
    baro_rate: float | None = None  # vertical rate
    squawk: str | None = None
    category: int | None = None
    nav_qnh: float | None = None
    nav_altitude_mcp: float | None = None
    nav_heading: float | None = None
    nav_modes: list[str] | None = None
    seen: float | None = None
    seen_pos: float | None = None
    rssi: float | None = None
    source: str = "unknown"


class BaseAPIClient:
    """Base class for API clients."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        latitude: float,
        longitude: float,
        radius_km: int,
        user_agent: str,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._latitude = latitude
        self._longitude = longitude
        self._radius_km = radius_km
        self._user_agent = user_agent
        self._ws_task: asyncio.Task | None = None
        self._ws_callback: Callable | None = None
        self._ws_connected = False
        self._ws_reconnect_delay = 1
        self._shutdown = False

    @property
    def is_connected(self) -> bool:
        """Return WebSocket connection status."""
        return self._ws_connected

    async def fetch_rest(self) -> list[FlightData]:
        """Fetch flights via REST API. Must be implemented by subclass."""
        raise NotImplementedError

    async def start_websocket(self, callback: Callable) -> None:
        """Start WebSocket connection. Must be implemented by subclass."""
        self._ws_callback = callback
        raise NotImplementedError

    async def stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        self._shutdown = True
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ws_task

    def _parse_flights(self, data: dict[str, Any]) -> list[FlightData]:
        """Parse flights from API response."""
        flights = []
        aircraft = data.get("ac", [])
        for ac in aircraft:
            try:
                flight = FlightData(
                    hex=ac.get("hex", ""),
                    flight=ac.get("flight", "").strip() or None,
                    r=ac.get("r", "").strip() or None,
                    t=ac.get("t", "").strip() or None,
                    lat=ac.get("lat"),
                    lon=ac.get("lon"),
                    alt_baro=ac.get("alt_baro"),
                    alt_geom=ac.get("alt_geom"),
                    gs=ac.get("gs"),
                    track=ac.get("track"),
                    baro_rate=ac.get("baro_rate"),
                    squawk=ac.get("squawk"),
                    category=ac.get("category"),
                    nav_qnh=ac.get("nav_qnh"),
                    nav_altitude_mcp=ac.get("nav_altitude_mcp"),
                    nav_heading=ac.get("nav_heading"),
                    nav_modes=ac.get("nav_modes"),
                    seen=ac.get("seen"),
                    seen_pos=ac.get("seen_pos"),
                    rssi=ac.get("rssi"),
                )
                if flight.hex and flight.lat is not None and flight.lon is not None:
                    flights.append(flight)
            except Exception as err:
                _LOGGER.debug("Failed to parse flight: %s", err)
        return flights


class ADSBFiClient(BaseAPIClient):
    """Client for ADSB.fi API."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ws_url = f"wss://api.adsb.fi/v2/ws/lat/{self._latitude}/lon/{self._longitude}/dist/{self._radius_km}"

    async def fetch_rest(self) -> list[FlightData]:
        """Fetch flights via REST API."""
        url = f"https://api.adsb.fi/v2/lat/{self._latitude}/lon/{self._longitude}/dist/{self._radius_km}"
        headers = {"User-Agent": self._user_agent}

        try:
            async with self._session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return self._parse_flights(data)
                else:
                    _LOGGER.warning("ADSB.fi REST error: %s", resp.status)
                    return []
        except TimeoutError:
            _LOGGER.warning("ADSB.fi REST timeout")
            return []
        except Exception as err:
            _LOGGER.error("ADSB.fi REST error: %s", err)
            return []

    async def start_websocket(self, callback: Callable) -> None:
        """Start WebSocket connection."""
        self._ws_callback = callback
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = asyncio.create_task(self._websocket_loop())

    async def _websocket_loop(self) -> None:
        """WebSocket connection loop with auto-reconnect."""
        while not self._shutdown:
            try:
                _LOGGER.debug("Connecting to ADSB.fi WebSocket...")
                async with self._session.ws_connect(self._ws_url) as ws:
                    self._ws_connected = True
                    self._ws_reconnect_delay = 1
                    _LOGGER.info("ADSB.fi WebSocket connected")

                    async for msg in ws:
                        if self._shutdown:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                if data.get("type") == "flights":
                                    flights = self._parse_flights({"ac": data.get("flights", [])})
                                    if self._ws_callback:
                                        await self._ws_callback(flights)
                            except json.JSONDecodeError:
                                pass
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            _LOGGER.error("ADSB.fi WebSocket error: %s", ws.exception())
                            break

            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.warning("ADSB.fi WebSocket error: %s", err)

            self._ws_connected = False
            if not self._shutdown:
                _LOGGER.info("ADSB.fi WebSocket reconnecting in %ds...", self._ws_reconnect_delay)
                await asyncio.sleep(self._ws_reconnect_delay)
                self._ws_reconnect_delay = min(self._ws_reconnect_delay * 2, 60)


class ADSBLolClient(BaseAPIClient):
    """Client for ADSB.lol API."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._ws_url = f"wss://api.adsb.lol/v2/ws/lat/{self._latitude}/lon/{self._longitude}/dist/{self._radius_km}"

    async def fetch_rest(self) -> list[FlightData]:
        """Fetch flights via REST API."""
        url = f"https://api.adsb.lol/v2/lat/{self._latitude}/lon/{self._longitude}/dist/{self._radius_km}"
        headers = {"User-Agent": self._user_agent}

        try:
            async with self._session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return self._parse_flights(data)
                else:
                    _LOGGER.warning("ADSB.lol REST error: %s", resp.status)
                    return []
        except TimeoutError:
            _LOGGER.warning("ADSB.lol REST timeout")
            return []
        except Exception as err:
            _LOGGER.error("ADSB.lol REST error: %s", err)
            return []

    async def start_websocket(self, callback: Callable) -> None:
        """Start WebSocket connection."""
        self._ws_callback = callback
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = asyncio.create_task(self._websocket_loop())

    async def _websocket_loop(self) -> None:
        """WebSocket connection loop with auto-reconnect."""
        while not self._shutdown:
            try:
                _LOGGER.debug("Connecting to ADSB.lol WebSocket...")
                async with self._session.ws_connect(self._ws_url) as ws:
                    self._ws_connected = True
                    self._ws_reconnect_delay = 1
                    _LOGGER.info("ADSB.lol WebSocket connected")

                    async for msg in ws:
                        if self._shutdown:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                                if data.get("type") == "flights":
                                    flights = self._parse_flights({"ac": data.get("flights", [])})
                                    if self._ws_callback:
                                        await self._ws_callback(flights)
                            except json.JSONDecodeError:
                                pass
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            _LOGGER.error("ADSB.lol WebSocket error: %s", ws.exception())
                            break

            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.warning("ADSB.lol WebSocket error: %s", err)

            self._ws_connected = False
            if not self._shutdown:
                _LOGGER.info("ADSB.lol WebSocket reconnecting in %ds...", self._ws_reconnect_delay)
                await asyncio.sleep(self._ws_reconnect_delay)
                self._ws_reconnect_delay = min(self._ws_reconnect_delay * 2, 60)


class PlanespottersClient:
    """Client for Planespotters.net API to fetch aircraft images."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        cache_dir: Path,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._email = email
        self._cache_dir = cache_dir
        self._cache_file = cache_dir / "images.json"
        self._cache: dict[str, dict] = {}
        self._negative_cache: dict[str, float] = {}  # hex -> timestamp
        self._load_cache()

    def _load_cache(self) -> None:
        """Load image cache from disk."""
        try:
            if self._cache_file.exists():
                import json

                content = self._cache_file.read_text()
                self._cache = json.loads(content)
                _LOGGER.debug("Loaded %d cached images", len(self._cache))
        except Exception as err:
            _LOGGER.warning("Failed to load image cache: %s", err)
            self._cache = {}

    async def _save_cache(self) -> None:
        """Save image cache to disk."""
        try:
            import json

            self._cache_dir.mkdir(parents=True, exist_ok=True)
            content = json.dumps(self._cache)
            await aiofiles.open(self._cache_file, "w").write(content)
        except Exception as err:
            _LOGGER.warning("Failed to save image cache: %s", err)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        time.time()
        entries_with_images = sum(1 for v in self._cache.values() if v.get("url"))
        return {
            "total_entries": len(self._cache),
            "entries_with_images": entries_with_images,
            "negative_entries": len(self._negative_cache),
        }

    async def get_image_url(self, hex_code: str, registration: str | None = None) -> str | None:
        """Get image URL for aircraft by hex or registration."""
        hex_code = hex_code.lower()

        # Check positive cache
        if hex_code in self._cache:
            entry = self._cache[hex_code]
            if entry.get("url") and time.time() - entry.get("timestamp", 0) < 86400:  # 24h
                return entry["url"]

        # Check negative cache
        if hex_code in self._negative_cache and time.time() - self._negative_cache[hex_code] < 3600:  # 1h
            return None

        # Try registration first if available
        if registration:
            url = await self._fetch_by_registration(registration)
            if url:
                self._cache[hex_code] = {"url": url, "reg": registration, "timestamp": time.time()}
                await self._save_cache()
                return url

        # Try by hex
        url = await self._fetch_by_hex(hex_code)
        if url:
            self._cache[hex_code] = {"url": url, "reg": registration, "timestamp": time.time()}
            await self._save_cache()
            return url

        # Cache negative result
        self._negative_cache[hex_code] = time.time()
        return None

    async def _fetch_by_hex(self, hex_code: str) -> str | None:
        """Fetch image by hex code."""
        url = f"https://api.planespotters.net/pub/photos/hex/{hex_code}"
        headers = {"User-Agent": f"FlightTracker/1.0 ({self._email})"}

        try:
            async with self._session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    photos = data.get("photos", [])
                    if photos:
                        # Get highest resolution photo
                        best = max(photos, key=lambda p: p.get("thumbnail_width", 0) * p.get("thumbnail_height", 0))
                        return best.get("thumbnail_large") or best.get("thumbnail") or best.get("image_url")
                elif resp.status == 404:
                    return None
        except Exception as err:
            _LOGGER.debug("Planespotters fetch by hex failed: %s", err)
        return None

    async def _fetch_by_registration(self, registration: str) -> str | None:
        """Fetch image by registration."""
        url = f"https://api.planespotters.net/pub/photos/reg/{registration}"
        headers = {"User-Agent": f"FlightTracker/1.0 ({self._email})"}

        try:
            async with self._session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    photos = data.get("photos", [])
                    if photos:
                        best = max(photos, key=lambda p: p.get("thumbnail_width", 0) * p.get("thumbnail_height", 0))
                        return best.get("thumbnail_large") or best.get("thumbnail") or best.get("image_url")
                elif resp.status == 404:
                    return None
        except Exception as err:
            _LOGGER.debug("Planespotters fetch by reg failed: %s", err)
        return None

    async def preload_images(self, flights: list[dict]) -> None:
        """Preload images for multiple flights (fire and forget)."""
        # Deduplicate by hex
        seen = set()
        for flight in flights:
            hex_code = flight.get("hex", "").lower()
            if hex_code and hex_code not in seen:
                seen.add(hex_code)
                # Check if we need to fetch
                if hex_code not in self._cache or time.time() - self._cache[hex_code].get("timestamp", 0) > 86400:
                    # Fire and forget - don't wait
                    asyncio.create_task(self.get_image_url(hex_code, flight.get("registration")))


class ADSBComClient(BaseAPIClient):
    """Client for ADSB.com API (placeholder - may require API key)."""

    async def fetch_rest(self) -> list[FlightData]:
        """Fetch flights via REST API."""
        # ADSB.com may require API key - placeholder for future
        _LOGGER.debug("ADSB.com client not yet implemented")
        return []

    async def start_websocket(self, callback: Callable) -> None:
        """Start WebSocket connection."""
        _LOGGER.debug("ADSB.com WebSocket not yet implemented")