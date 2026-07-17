"""API client for ADSB.fi."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from ..const import (
    ADSB_FI_REST,
    ADSB_FI_WS,
    WS_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class FlightData:
    """Flight data from ADSB.fi."""

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
    source: str = "adsb_fi"


class ADSBFiClient:
    """Client for ADSB.fi API."""

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
        self._reconnect_delay = 1

    @property
    def is_connected(self) -> bool:
        """Return WebSocket connection status."""
        return self._ws_connected

    async def fetch_rest(self) -> list[FlightData]:
        """Fetch flights via REST API."""
        url = f"{ADSB_FI_REST}/lat/{self._latitude}/lon/{self._longitude}/dist/{self._radius_km}"
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

    async def start_websocket(self, callback: Callable) -> None:
        """Start WebSocket connection for live updates."""
        self._ws_callback = callback
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = asyncio.create_task(self._websocket_loop())

    async def stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ws_task

    async def _websocket_loop(self) -> None:
        """WebSocket connection loop with auto-reconnect."""
        url = f"{ADSB_FI_WS}/lat/{self._latitude}/lon/{self._longitude}/dist/{self._radius_km}"
        headers = {"User-Agent": self._user_agent}

        while True:
            try:
                async with self._session.ws_connect(url, headers=headers, heartbeat=30) as ws:
                    _LOGGER.info("ADSB.fi WebSocket connected")
                    self._ws_connected = True
                    self._reconnect_delay = 1

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await self._handle_ws_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            _LOGGER.warning("ADSB.fi WS error: %s", ws.exception())
                            break
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            break

            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.warning("ADSB.fi WebSocket error: %s, reconnecting in %ss", err, self._reconnect_delay)

            self._ws_connected = False
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def _handle_ws_message(self, data: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            msg = json.loads(data)
            if msg.get("type") == WS_UPDATE_INTERVAL:
                return  # Skip stats messages

            if "ac" in msg:
                flights = self._parse_flights(msg)
                if self._ws_callback:
                    await self._ws_callback(flights)

        except json.JSONDecodeError:
            pass
        except Exception as err:
            _LOGGER.debug("WS message handling error: %s", err)
