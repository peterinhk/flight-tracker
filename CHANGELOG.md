# Changelog

All notable changes to this project will be documented in this format.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-07-31

### Fixed
- `Error adding entity None for domain device_tracker with platform flight_tracker`: the Planespotters API returns `thumbnail`/`thumbnail_large` as objects (`{"src": "...", "size": {"width": .., "height": ..}}`), not bare URL strings — confirmed against the live API. `PlanespottersClient` was returning that raw object as `Flight.image_url`, which then got passed as a device's `configuration_url`. Home Assistant's device registry validates `configuration_url` and raises an uncaught `ValueError` for anything that isn't a real http(s) URL (only `DeviceInfoError` is caught by the platform helper, not `ValueError`) — since this happens before the entity's `entity_id` is assigned, it surfaced as "entity None" in the log, and that flight's device_tracker entity silently failed to add. Fixed `PlanespottersClient` to correctly extract `photo["thumbnail_large"]["src"]` (with a `thumbnail`/`image_url` fallback chain) and to sort by the real nested `size.width`/`size.height` fields instead of nonexistent `thumbnail_width`/`thumbnail_height` keys.
- Added a defensive `configuration_url` validator in `device_tracker.py` so any future malformed URL degrades to "no configuration URL" instead of crashing that flight's entity addition.
- Device tracker entities had a doubled name/entity_id bug (e.g. `device_tracker.ual123_ual123`, friendly name "UAL123 UAL123"): with `has_entity_name = True`, overriding the `name` property to return the callsign duplicated it against the device's own name (which is also the callsign). Removed the redundant `name` property; `_attr_name = None` already means "use the device name as-is".

Reproduced and verified all three fixes end-to-end with `pytest-homeassistant-custom-component`, including checking the actual `DeviceEntry.configuration_url` and entity_id/friendly_name in the registry — not just that setup didn't raise.

## [1.1.0] - 2026-07-31

### Added
- New `flight_tracker.set_search_params` service to live-update latitude, longitude, radius, min/max altitude, and the military/GA filters without reloading the config entry. Position/radius changes rebuild the REST/WebSocket API clients (whose request URLs are otherwise fixed at construction); altitude/filter changes apply on the next fetch. Runtime-only by design (not persisted to the config entry), so it's fast enough for interactive controls.
- `sensor.total_flights` now exposes the live search parameters (`latitude`, `longitude`, `radius_km`, `min_altitude`, `max_altitude`, `track_military`, `track_ga`) as attributes, so a UI can read current values without a separate API call.
- New custom Lovelace card (`custom_components/flight_tracker/www/flight-tracker-card.js`), auto-registered as a frontend resource on startup (via `hass.http.async_register_static_paths` + `frontend.add_extra_js_url` — no manual "Add Resource" step). It provides an embedded map, a multi-select list of nearby flights to choose what's plotted on the map, sliders for radius/altitude, latitude/longitude fields, Yes/No selects for the military/GA filters (all live via `set_search_params`), and an expandable details view per flight.

Verified end-to-end with `pytest-homeassistant-custom-component` against a real Home Assistant + frontend install: config flow → entry setup → static file actually served over HTTP → `add_extra_js_url` registration → `set_search_params` service call actually mutating the live coordinator, rebuilding API clients, and updating sensor attributes → the service's entry_id validation error path.

## [1.0.9] - 2026-07-31

### Fixed
- Config flow raised `voluptuous.MultipleInvalid` while building the form: the latitude/longitude `NumberSelectorConfig` used `step=0.0001`, but Home Assistant's selector schema requires `step >= 0.001`. This crashed form generation and surfaced to the frontend as the generic, unhelpful "Config flow could not be loaded: 400: Bad Request" (an uncaught internal error, unlike the JSON-formatted "Invalid handler specified" from 1.0.8). Changed both selectors to `step=0.001`.
- `FlightTrackerCoordinator.__init__` set `self.data = CoordinatorData()` *before* calling `super().__init__()`, but `DataUpdateCoordinator.__init__` unconditionally sets `self.data = None`, silently discarding it. The first refresh then crashed with `AttributeError: 'NoneType' object has no attribute 'flights'`, permanently stuck the entry in `SETUP_RETRY`. Moved the assignment to after the `super().__init__()` call.

Both bugs were only caught by standing up a real Home Assistant instance via `pytest-homeassistant-custom-component` and running the config flow and entry setup end-to-end (init → submit form → `async_setup_entry` → first coordinator refresh), rather than relying on static analysis or mocked unit tests. The entry now reaches `ConfigEntryState.LOADED` and all sensor/device_tracker entities register successfully.

## [1.0.8] - 2026-07-31

### Fixed
- Config flow handler was never actually registered with Home Assistant: `domain = DOMAIN` was set as a plain class attribute instead of passed as the `domain=` class-definition keyword that `ConfigFlow.__init_subclass__` requires to call `HANDLERS.register()`. This caused "Config flow could not be loaded: Invalid handler specified" and made the integration impossible to add. Verified the fix by importing the module and checking `flight_tracker` is present in Home Assistant's `HANDLERS` registry.

## [1.0.7] - 2026-07-31

### Fixed
- Removed `Platform.BINARY_SENSOR` from `PLATFORMS`; no `binary_sensor.py` platform exists, so forwarding setup to it crashed integration load
- Fixed circular import between `device_tracker.py` and `entity_manager.py`
- Fixed `NameError` from using `CoordinatorEntity[FlightTrackerCoordinator]` as a base class while only importing `FlightTrackerCoordinator` under `TYPE_CHECKING` (in `sensor.py` and `device_tracker.py`)
- Fixed `DataUpdateCoordinator` being passed a raw `int` for `update_interval` instead of a `timedelta`
- Device tracker entities are now actually created/removed: `FlightTrackerEntityManager.update_entities()` was never invoked, so no per-flight map entities were ever added
- Fixed `services.py` importing `FlightTrackerCoordinator` from the wrong module, looking up config entries via unused `hass.data`, and referencing a nonexistent `coordinator.enabled_sources` attribute
- Services (`refresh`, `center_map`, `get_flight_image`) are now actually registered on startup; added missing `services.yaml`
- Config flow: use `ConfigFlowResult` instead of the deprecated `FlowResult` return type
- Removed incorrect "military" filter that matched ADS-B categories 3/4/5 (ordinary Large/High-Vortex/Heavy weight classes covering most commercial airliners), which hid nearly all real flights by default since `track_military` defaults to off
- `TotalFlightsSensor` no longer declares an invalid `SensorDeviceClass.ENUM` alongside a numeric unit
- Fixed falsy-zero bugs in `HighestFlightSensor`, `FastestFlightSensor`, and `NearestFlightSensor` that reported no data when altitude/speed/distance was exactly `0`
- Config flow: aligned schema keys with const.py constants (CONF_TRACK_MILITARY, CONF_TRACK_GA) and translation keys
- Added missing CONF_TRACK_GA field to config flow schema with proper default

### Removed
- Deleted unused duplicate API client implementations (`api/adsb_fi.py`, `api/adsb_lol.py`, `api/planespotters.py`) that diverged from and were never imported in favor of the ones in `api/__init__.py`
- Removed stray compiled `.pyc` files that were still tracked in git despite `.gitignore`

## [1.0.6] - 2026-07-17

### Fixed
- All mypy type checking passes (no issues found in 13 source files)
- Ruff linting passes with zero errors
- PlanespottersClient cache type annotations fixed (dict[str, dict[str, Any]])
- GitHub Actions Validate workflow runs before Release workflow
- Release workflow only triggers on successful Validate completion for tagged pushes

## [1.0.4] - 2026-07-16

### Fixed
- Fixed mypy configuration: changed `tool.mypy.overrides` to array format `[[tool.mypy.overrides]]` for valid pyproject.toml
- Updated all manifests to version 1.0.4 (hacs.json, manifest.json, pyproject.toml, const.py)

## [1.0.3] - 2026-07-16

### Fixed
- Config flow schema validation: use CONF_APIS_ENABLED key consistently across const.py and config_flow.py
- Config flow default values: use DEFAULT_APIS_ENABLED for both schema default and entry creation
- Updated version to 1.0.3 in all manifests (hacs.json, manifest.json, pyproject.toml, const.py)

## [1.0.2] - 2026-07-16

### Fixed
- Fixed circular import between coordinator.py and entity_manager.py by extracting shared data models to models.py

## [1.0.0] - 2026-07-13

### Added
- Initial release