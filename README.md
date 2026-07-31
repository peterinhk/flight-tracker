# Flight Tracker for Home Assistant

Track live flights from **ADSB.fi**, **ADSB.lol**, **ADSB.com** with **Planespotters aircraft images** on your Home Assistant map.

![Flight Tracker Demo](docs/demo.gif)

## Features

- 🛩️ **Live flight tracking** — Real-time aircraft positions via WebSocket (ADSB.fi, ADSB.lol)
- 🌍 **Multiple data sources** — Aggregates ADSB.fi, ADSB.lol, ADSB.com for best coverage
- 📸 **Aircraft images** — Fetches photos from Planespotters by hex/registration
- 🗺️ **Native map integration** — Device tracker entities appear automatically on HA Map card
- 🗂️ **Custom Lovelace card** — Map, live search filters, and per-flight details in one card (see below)
- 📊 **Rich sensors** — Total flights, nearest, highest, fastest, category breakdown, source stats
- ⚙️ **Fully configurable** — Radius, altitude filters, scan interval, API selection via UI
- 🎚️ **Live search tuning** — Change radius/position/altitude filters at runtime without reloading
- 🔌 **HACS compatible** — One-click install and updates
- 🏠 **Native HA integration** — Config flow, device registry, entity registry, translations

## Installation

### HACS (Recommended)

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/peterjurgens/flight-tracker` (Category: Integration)
3. Search for "Flight Tracker" and install
4. Restart Home Assistant
5. Go to Settings → Devices & Services → Add Integration → Flight Tracker

### Manual

1. Download latest `flight_tracker-<version>.zip` from [Releases](https://github.com/peterjurgens/flight-tracker/releases)
2. Extract to `<config>/custom_components/flight_tracker/`
3. Restart Home Assistant
4. Add integration via Settings → Devices & Services

## Configuration

After installation, configure via Settings → Devices & Services → Flight Tracker → Configure:

| Setting | Description | Default |
|---------|-------------|---------|
| **Latitude/Longitude** | Center point for tracking | Your HA location |
| **Radius (km)** | Tracking radius | 50 km |
| **Scan Interval** | REST API poll frequency | 60 seconds |
| **Enabled APIs** | Data sources to use | ADSB.fi, ADSB.lol |
| **Planespotters Email** | Required for aircraft images | — |
| **Min/Max Altitude** | Filter flights by altitude | 0 / 60000 ft |
| **Track Military** | Include military/heavy aircraft | Off |
| **Track General Aviation** | Include light/small aircraft | On |
| **Show on Map** | Display flights on HA map | On |

## Entities Created

### Device Trackers (appear on Map card)
- `device_tracker.flight_<hex>` — One per tracked flight
  - Attributes: callsign, registration, altitude, speed, heading, aircraft type, operator, image URL, distance

### Sensors
| Entity | Description |
|--------|-------------|
| `sensor.flight_tracker_total_flights` | Total flights in radius |
| `sensor.flight_tracker_nearest_flight` | Distance to nearest flight |
| `sensor.flight_tracker_highest_flight` | Highest altitude flight |
| `sensor.flight_tracker_fastest_flight` | Fastest ground speed |
| `sensor.flight_tracker_images_cached` | Planespotters cache stats |
| `sensor.flight_tracker_category_breakdown` | Flights by aircraft category |
| `sensor.flight_tracker_source_breakdown` | Flights by data source |

## Services

| Service | Description |
|---------|-------------|
| `flight_tracker.refresh` | Manually refresh flight data |
| `flight_tracker.center_map` | Center map on coordinates |
| `flight_tracker.get_flight_image` | Get aircraft image by callsign/reg/hex |
| `flight_tracker.set_search_params` | Live-update latitude/longitude/radius/altitude/military/GA filters without reloading the integration |

`set_search_params` only changes runtime state (it does not persist to the config entry), so it's meant for interactive controls — like the sliders in the custom card below — rather than one-off permanent changes. To change a setting permanently, use Settings → Devices & Services → Flight Tracker → Configure instead.

## Flight Tracker Card

The integration ships a custom Lovelace card (`custom_components/flight_tracker/www/flight-tracker-card.js`) that is registered automatically as a frontend resource on startup — no manual "Add Resource" step needed (if it doesn't show up, restart Home Assistant once after installing/upgrading).

It includes:
- An embedded map (Home Assistant's built-in map card) showing the flights you've selected
- A multi-select checklist of every currently tracked nearby flight, to choose which ones appear on the map
- Sliders for radius, minimum altitude, and maximum altitude
- Latitude/longitude fields (with a "Use Home Assistant location" shortcut) and Yes/No selects for military and general-aviation filtering — all of which call `flight_tracker.set_search_params` live as you adjust them
- An expandable details row per flight (registration, ICAO24, speed, heading, vertical rate, squawk, category, operator, origin/destination, distance, source, signal strength, photo)

Add it to a dashboard in YAML mode:

```yaml
type: custom:flight-tracker-card
entity: sensor.total_flights
title: Flight Tracker
show_map: true
map_default_zoom: 9
```

| Option | Description | Default |
|--------|-------------|---------|
| `entity` | The integration's "Total Flights" sensor (required) | — |
| `entry_id` | Config entry to target if you have more than one Flight Tracker instance | first/only entry |
| `title` | Card title | `Flight Tracker` |
| `show_map` | Embed the map | `true` |
| `map_default_zoom` | Initial map zoom | `9` |
| `map_height` | Map height in pixels | `300` |

## Example Plain Map Card

```yaml
type: map
entities:
  - entity_id: device_tracker.flight_*
    name: Flights
default_zoom: 8
```

## API Sources

| Source | Type | Images | Rate Limit |
|--------|------|--------|------------|
| [ADSB.fi](https://adsb.fi) | REST + WebSocket | No | Generous |
| [ADSB.lol](https://adsb.lol) | REST + WebSocket | No | Generous |
| [ADSB.com](https://adsb.com) | REST (planned) | No | TBD |
| [Planespotters](https://planespotters.net) | REST | **Yes** | 1000/day |

## Requirements

- Home Assistant 2024.1+
- Python 3.11+
- Planespotters account (free) for images — add email in config

## Development

```bash
# Clone and setup
git clone https://github.com/peterjurgens/flight-tracker
cd flight-tracker
pip install -e .[dev]

# Run tests
pytest

# Lint & type check
ruff check .
ruff format --check .
mypy custom_components/flight_tracker
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a PR

## License

MIT License — see [LICENSE](LICENSE)

## Credits

- [ADSB.fi](https://adsb.fi) — Live flight data
- [ADSB.lol](https://adsb.lol) — Live flight data
- [Planespotters](https://planespotters.net) — Aircraft images
- [Home Assistant](https://home-assistant.io) — Platform