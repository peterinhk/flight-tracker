# Flight Tracker Home Assistant Add-on — Project Plan

## Overview
Create a Home Assistant **add-on** (not a custom integration) that aggregates live flight data from multiple free APIs (ADSB.fi, ADSB.lol, ADSB.com, Planespotters) and exposes it to Home Assistant via **device trackers** and **sensors** for a live map view with plane images.

> **Key Decision:** Add-on vs Custom Integration
> - **Add-on** = separate container/service running alongside HA, communicates via MQTT/REST/WebSocket
> - **Custom Integration** = Python code running *inside* HA process (preferred for device_tracker/sensor entities)
> - **Recommendation:** Build as a **custom integration** (HACS-installable) for native entity support. Add-on only if you need a standalone service (e.g., separate machine, heavy processing). This plan assumes **custom integration** with HACS distribution.

---

## 1. Project Structure

```
flight-tracker/
├── .github/
│   └── workflows/
│       ├── validate.yml          # Lint, type-check, test
│       ├── release.yml           # Build HACS release on tag
│       └── hacs.yml              # HACS validation
├── custom_components/
│   └── flight_tracker/
│       ├── __init__.py
│       ├── config_flow.py        # UI config flow
│       ├── const.py              # Constants, defaults
│       ├── coordinator.py        # DataUpdateCoordinator (polling + WS)
│       ├── api/
│       │   ├── __init__.py
│       │   ├── adsb_fi.py        # ADSB.fi REST + WS
│       │   ├── adsb_lol.py       # ADSB.lol REST + WS
│       │   ├── adsb_com.py       # ADSB.com (if API exists)
│       │   └── planespotters.py  # Planespotters images
│       ├── sensor.py             # Sensor entities
│       ├── device_tracker.py     # Device tracker entities (for map)
│       ├── services.py           # Custom services (e.g., refresh, center_map)
│       ├── websocket.py          # HA WebSocket API for frontend cards
│       └── translations/
│           └── en.json
├── hacs.json                     # HACS manifest
├── info.md                       # HACS info page
├── README.md
├── LICENSE
├── requirements.txt              # Python deps
├── pyproject.toml                # Build config (hatch/poetry)
├── .pre-commit-config.yaml
├── pytest.ini
└── tests/
    ├── conftest.py
    ├── test_api/
    ├── test_coordinator.py
    └── test_entities.py
```

---

## 2. Architecture & Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  ADSB.fi    │     │  ADSB.lol   │     │  ADSB.com   │
│  (REST/WS)  │     │  (REST/WS)  │     │  (REST)     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           ▼
                  ┌─────────────────┐
                  │  Coordinator    │  ← DataUpdateCoordinator
                  │  (merge, dedup, │     - Polls REST every 30-60s
                  │   filter by     │     - WebSocket for live updates
                  │   radius)       │     - Rate-limit aware
                  └────────┬────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  Sensors    │ │ Device Trk  │ │  Services   │
    │  (count,    │ │  (lat/lon,  │ │  (refresh,  │
    │   nearest,  │ │   altitude, │ │   center)   │
    │   stats)    │ │   callsign) │ │             │
    └─────────────┘ └─────────────┘ └─────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │  Planespotters  │  ← Async image fetch by hex/reg
                  │  Image Cache    │     (separate coordinator, 24h TTL)
                  └─────────────────┘
```

---

## 3. API Specifications

### 3.1 ADSB.fi (Primary — WebSocket + REST)
- **REST:** `https://api.adsb.fi/v2/lat/{lat}/lon/{lon}/dist/{km}`
- **WebSocket:** `wss://api.adsb.fi/v2/ws/lat/{lat}/lon/{lon}/dist/{km}`
- **Auth:** None (User-Agent with email)
- **Rate Limit:** Reasonable; include email in UA
- **Fields:** hex, flight, r, t, lat, lon, alt_baro, gs, track, category, reg, type, operator

### 3.2 ADSB.lol (Backup/Supplement)
- **REST:** `https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{km}`
- **WebSocket:** `wss://api.adsb.lol/v2/ws/...`
- **Similar schema to ADSB.fi**

### 3.3 ADSB.com (Check availability)
- May require API key; investigate `https://api.adsb.com` or tar1090 feed
- If no free tier, skip

### 3.4 Planespotters (Images)
- **Endpoint:** `https://api.planespotters.net/pub/photos/hex/{hex}` or `/reg/{reg}`
- **Auth:** User-Agent with email (required)
- **Rate Limit:** ~1000/day free
- **Response:** JSON with photo URLs (thumbnail, large)
- **Cache:** 24h TTL, store in HA `config/storage/flight_tracker_images.json`

---

## 4. Configuration (config_flow)

```python
# User-configurable options
CONFIG_SCHEMA = {
    "latitude": float,           # Default: HA location
    "longitude": float,
    "radius_km": int,            # Default: 50, max: 200
    "scan_interval": int,        # Default: 60s (REST poll)
    "enable_websocket": bool,    # Default: True
    "apis_enabled": list[str],   # ["adsb_fi", "adsb_lol", "adsb_com"]
    "planespotters_email": str,  # Required for images
    "min_altitude": int,         # Filter ground noise
    "max_altitude": int,         # Optional ceiling
    "track_military": bool,      # Include category=3/4
    "track_ga": bool,            # General aviation
}
```

**Config Flow Steps:**
1. **API Selection** — multi-select APIs to enable
2. **Location/Radius** — lat/lon/radius (prefill from HA)
3. **Planespotters Email** — required for images
4. **Filters** — altitude, categories, scan interval
5. **Review & Create**

---

## 5. Entities

### 5.1 Device Trackers (for Map Card)
| Entity ID Pattern | Purpose |
|-------------------|---------|
| `device_tracker.flight_{hex}` | Each active flight — lat/lon, altitude, heading, speed, callsign, registration, type, operator, image_url |
| **Attributes:** `callsign`, `registration`, `icao24`, `altitude`, `speed`, `heading`, `aircraft_type`, `operator`, `origin`, `destination`, `image_url`, `last_seen`, `source_api` |

> **Note:** Device trackers with only `lat`/`lon` attributes appear on HA Map card automatically.

### 5.2 Sensors
| Entity ID | State | Attributes |
|-----------|-------|------------|
| `sensor.flights_total` | Count | `in_radius`, `by_category`, `by_api` |
| `sensor.flight_nearest` | Nearest callsign | `distance_km`, `altitude`, `callsign`, `registration`, `image_url` |
| `sensor.flight_highest` | Highest altitude | `callsign`, `altitude_ft` |
| `sensor.flight_fastest` | Fastest ground speed | `callsign`, `speed_kts` |
| `sensor.flight_images_cached` | Count | `cache_size_mb`, `hit_rate` |

### 5.3 Binary Sensors (Optional)
- `binary_sensor.flight_alert_{callsign}` — triggers when specific flight enters radius

---

## 6. Coordinator Design

```python
class FlightTrackerCoordinator(DataUpdateCoordinator):
    """Aggregates multiple API sources, deduplicates by ICAO24."""

    def __init__(self, hass, config):
        self.apis = {
            "adsb_fi": ADSBFiClient(...),
            "adsb_lol": ADSBLolClient(...),
            # "adsb_com": ADSBComClient(...),
        }
        self.planespotters = PlanespottersClient(email)
        self.image_cache = ImageCache(hass)
        self.seen_flights: dict[str, FlightData] = {}

    async def _async_update_data(self):
        # 1. Fetch from all enabled APIs (parallel)
        # 2. Merge by ICAO24 (hex), preferring WebSocket > REST > newer timestamp
        # 3. Filter by radius, altitude, category
        # 4. Update device tracker entities (add/update/remove)
        # 5. Fetch missing images from Planespotters (async, batched)
        # 6. Return aggregated data for sensors
```

**Deduplication Strategy:**
- Primary key: `hex` (ICAO24)
- Merge rule: Most recent `last_seen` wins; combine fields from all sources
- WebSocket updates take priority over REST poll

**WebSocket Handling:**
- Persistent connection per API
- Auto-reconnect with exponential backoff
- Parse messages → update `seen_flights` → trigger coordinator refresh (throttled 5s)

---

## 7. Planespotters Image Fetching

```python
class PlanespottersClient:
    async def get_image_url(self, hex: str, reg: str | None) -> str | None:
        # 1. Check cache (memory + persistent JSON)
        # 2. If miss, call API: GET /pub/photos/hex/{hex} or /reg/{reg}
        # 3. Select best image: largest resolution, proper aspect ratio
        # 4. Cache with 24h TTL
        # 5. Return CDN URL (planespotters.net/img/...)
```

**Cache Storage:** `config/storage/flight_tracker_images.json`
```json
{
  "a1b2c3": {"url": "https://...", "fetched": 1700000000, "reg": "N12345"},
  "d4e5f6": {"url": "https://...", "fetched": 1700000000, "reg": "G-ABCD"}
}
```

---

## 8. HACS Packaging

### 8.1 `hacs.json`
```json
{
  "name": "Flight Tracker",
  "content_in_root": false,
  "filename": "custom_components/flight_tracker",
  "domains": ["flight_tracker"],
  "version": "1.0.0",
  "minimum_ha_version": "2024.1",
  "requirements": ["aiohttp>=3.9", "python-socketio>=5.8"],
  "hass_dependencies": ["device_tracker", "sensor", "websocket_api"],
  "translations": ["en"],
  "config_flow": true,
  "documentation": "https://github.com/youruser/flight-tracker/blob/main/README.md",
  "issue_tracker": "https://github.com/youruser/flight-tracker/issues"
}
```

### 8.2 `info.md` (HACS store page)
- Description, screenshots, config guide, API credits, donation links

### 8.3 Release Workflow (`.github/workflows/release.yml`)
- Trigger: Git tag `v*`
- Build: Validate, create zip of `custom_components/flight_tracker`
- Release: GitHub Release with asset
- HACS: Auto-indexed on tag push (if repo added to HACS default store)

---

## 9. GitHub Repository Setup

1. **Create repo:** `github.com/youruser/flight-tracker`
2. **Branch protection:** `main` requires PR + CI pass
3. **Labels:** `bug`, `enhancement`, `api`, `hacs`, `docs`
4. **Environments:** `hacs` (for release workflow)
5. **Secrets:** None needed (all public APIs)
6. **Dependabot:** Enable for Python deps

---

## 10. Development Phases

### Phase 1: Foundation (Week 1)
- [ ] Repo init, CI pipeline (ruff, mypy, pytest)
- [ ] `config_flow.py` with all options
- [ ] `const.py`, `coordinator.py` skeleton
- [ ] Basic `sensor.py` (flight count)

### Phase 2: ADSB.fi Integration (Week 1-2)
- [ ] `api/adsb_fi.py` — REST client with rate limiting
- [ ] WebSocket client with auto-reconnect
- [ ] Coordinator merges WS + REST data
- [ ] Device tracker entities appear on map

### Phase 3: Multi-API & Planespotters (Week 2)
- [ ] `api/adsb_lol.py` (same interface)
- [ ] `api/planespotters.py` with caching
- [ ] Image URLs attached to device trackers
- [ ] Sensor entities for stats

### Phase 4: Polish & HACS (Week 3)
- [ ] Translations (`en.json`)
- [ ] Services (`refresh`, `center_map`)
- [ ] WebSocket API for custom frontend cards
- [ ] `hacs.json`, `info.md`, `README.md`
- [ ] Test on clean HA instance

### Phase 5: Release (Week 3-4)
- [ ] Tag `v1.0.0`, verify HACS install
- [ ] Submit to HACS default store (PR to `hacs/default`)
- [ ] Document known limitations

---

## 11. Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Integration vs Add-on** | Custom Integration | Native entities, no container overhead, HACS-native |
| **Coordination** | DataUpdateCoordinator | HA standard, handles polling, throttling, errors |
| **WebSocket** | `aiohttp` + `asyncio` | Native async, no extra deps |
| **Deduplication** | ICAO24 (hex) primary key | Globally unique per aircraft |
| **Image Cache** | JSON in `config/storage/` | Survives restart, no DB needed |
| **Config** | Config Flow (UI) | User-friendly, no YAML |
| **Map Display** | Device Tracker entities | Works with built-in Map card, no custom card needed |

---

## 12. Testing Strategy

```python
# tests/test_coordinator.py
async def test_deduplication_merges_sources():
    # Mock ADSB.fi + ADSB.lol returning same hex
    # Verify single device_tracker created with merged data

async def test_websocket_reconnect():
    # Simulate WS disconnect → reconnect → data flows

async def test_planespotters_cache():
    # First call hits API, second returns cached URL
    # Expired cache refetches

async def test_radius_filter():
    # Flights outside radius excluded from entities
```

**Integration Tests:** Run against HA test instance (pytest-homeassistant-custom-component)

---

## 13. Known Challenges & Mitigations

| Challenge | Mitigation |
|-----------|------------|
| API rate limits | Configurable scan interval (min 30s), User-Agent with email |
| WebSocket instability | Exponential backoff, fallback to REST-only mode |
| Duplicate flights across APIs | ICAO24 deduplication with timestamp priority |
| Planespotters 404s | Graceful fallback (no image), cache negative results 1h |
| Entity churn (flights entering/leaving) | `device_tracker` entities persist 5min after last_seen |
| High entity count (busy airspace) | Configurable max_entities, filter by altitude/category |

---

## 14. Future Enhancements (Post-v1)

- **History/Playback:** Store flight paths in SQLite for replay
- **Alerts:** Notify when specific reg/callsign enters radius
- **MLAT Support:** Integrate with local RTL-SDR feeder (read tar1090/readsb JSON)
- **Custom Map Card:** Enhanced card with trails, labels, filters
- **Home Assistant Map Integration:** Native `map` entity (HA 2024.12+)
- **Voice Assistant:** "Show me flights near me" → Assist intent

---

## 15. Resource Links

- **ADSB.fi API Docs:** https://adsb.fi/api
- **ADSB.lol API Docs:** https://github.com/adsb-lol/api
- **Planespotters API:** https://planespotters.net/api
- **HA Custom Integration Dev:** https://developers.home-assistant.io/docs/creating_integration
- **HACS Integration Requirements:** https://hacs.xyz/docs/publish/include
- **DataUpdateCoordinator:** https://developers.home-assistant.io/docs/integration_fetching_data
- **Device Tracker Entities:** https://developers.home-assistant.io/docs/core/entity/device-tracker

---

## 16. Next Steps for You

1. **Create GitHub repo** `flight-tracker` (public)
2. **Clone locally** and scaffold structure (use `cookiecutter-homeassistant-custom-component` or manual)
3. **Set up CI** (ruff, mypy, pytest) — copy from existing HA custom component
4. **Implement Phase 1** — config flow + coordinator skeleton
5. **Test ADSB.fi REST** manually with your lat/lon to confirm data shape
6. **Iterate** — push to GitHub, enable HACS test install on your HA

---

*Plan created: 2026-07-13 | Target: HACS-ready v1.0.0 in 3-4 weeks*