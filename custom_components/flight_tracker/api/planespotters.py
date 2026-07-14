"""API client for Planespotters image service."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiohttp

from ..const import PLANESPOTTERS_API

_LOGGER = logging.getLogger(__name__)


@dataclass
class AircraftImage:
    """Aircraft image from Planespotters."""
    url: str
    thumbnail: str
    registration: str
    hex: str
    photographer: str | None = None
    date_taken: str | None = None


class PlanespottersClient:
    """Client for Planespotters image API."""

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
        self._cache_file = cache_dir / "planespotters_cache.json"
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_lock = asyncio.Lock()
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk."""
        try:
            if self._cache_file.exists():
                with open(self._cache_file, "r") as f:
                    self._cache = json.load(f)
                _LOGGER.debug("Loaded Planespotters cache: %d entries", len(self._cache))
        except Exception as err:
            _LOGGER.warning("Failed to load Planespotters cache: %s", err)
            self._cache = {}

    async def _save_cache(self) -> None:
        """Save cache to disk."""
        async with self._cache_lock:
            try:
                self._cache_dir.mkdir(parents=True, exist_ok=True)
                with open(self._cache_file, "w") as f:
                    json.dump(self._cache, f)
            except Exception as err:
                _LOGGER.warning("Failed to save Planespotters cache: %s", err)

    def _is_cached_valid(self, entry: dict[str, Any], max_age_hours: int = 24) -> bool:
        """Check if cache entry is still valid."""
        fetched = entry.get("fetched", 0)
        return (time.time() - fetched) < (max_age_hours * 3600)

    async def get_image_url(self, hex_code: str, registration: str | None = None) -> str | None:
        """Get image URL for aircraft by hex code or registration."""
        cache_key = hex_code.lower()

        # Check cache first
        if cache_key in self._cache and self._is_cached_valid(self._cache[cache_key]):
            return self._cache[cache_key].get("url")

        # Try registration if hex failed
        if registration:
            reg_key = registration.upper().replace("-", "").replace(" ", "")
            if reg_key in self._cache and self._is_cached_valid(self._cache[reg_key]):
                return self._cache[reg_key].get("url")

        # Fetch from API
        return await self._fetch_image(hex_code, registration)

    async def _fetch_image(self, hex_code: str, registration: str | None) -> str | None:
        """Fetch image from Planespotters API."""
        # Try hex first
        url = f"{PLANESPOTTERS_API}/photos/hex/{hex_code.upper()}"
        image_url = await self._call_api(url)

        # Try registration if hex failed
        if not image_url and registration:
            reg_clean = registration.upper().replace("-", "").replace(" ", "")
            url = f"{PLANESPOTTERS_API}/photos/reg/{reg_clean}"
            image_url = await self._call_api(url)

        if image_url:
            # Cache the result
            cache_key = hex_code.lower()
            self._cache[cache_key] = {
                "url": image_url,
                "fetched": time.time(),
                "registration": registration,
            }
            await self._save_cache()
            return image_url

        # Cache negative result for 1 hour to avoid repeated 404s
        cache_key = hex_code.lower()
        self._cache[cache_key] = {
            "url": None,
            "fetched": time.time(),
            "registration": registration,
        }
        await self._save_cache()
        return None

    async def _call_api(self, url: str) -> str | None:
        """Call Planespotters API."""
        headers = {"User-Agent": f"FlightTracker/1.0 ({self._email})"}

        try:
            async with self._session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    photos = data.get("photos", [])
                    if photos:
                        # Get the first (usually highest quality) photo
                        photo = photos[0]
                        return photo.get("thumbnail_large") or photo.get("thumbnail") or photo.get("image_url")
                elif resp.status == 404:
                    _LOGGER.debug("No images found for %s", url)
                else:
                    _LOGGER.warning("Planespotters API error: %s", resp.status)
        except asyncio.TimeoutError:
            _LOGGER.warning("Planespotters API timeout")
        except Exception as err:
            _LOGGER.error("Planespotters API error: %s", err)
        return None

    async def preload_images(self, flights: list[dict[str, Any]]) -> None:
        """Preload images for multiple flights."""
        tasks = []
        for flight in flights:
            hex_code = flight.get("hex", "")
            registration = flight.get("r", "") or flight.get("registration", "")
            if hex_code:
                tasks.append(self.get_image_url(hex_code, registration))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = len(self._cache)
        valid = sum(1 for v in self._cache.values() if self._is_cached_valid(v))
        with_url = sum(1 for v in self._cache.values() if v.get("url"))
        return {
            "total_entries": total,
            "valid_entries": valid,
            "entries_with_images": with_url,
            "hit_rate": f"{(with_url / total * 100):.1f}%" if total > 0 else "0%",
        }