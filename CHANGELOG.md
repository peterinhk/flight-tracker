# Changelog

All notable changes to this project will be documented in this format.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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