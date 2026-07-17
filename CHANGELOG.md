# Changelog

All notable changes to this project will be documented in this format.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of Flight Tracker integration
- Support for ADSB.fi REST API and WebSocket
- Support for ADSB.lol REST API and WebSocket
- Planespotters integration for aircraft images
- Device tracker entities for live map display
- Sensor entities for flight statistics
- Full config flow with options
- HACS support
- Multi-API data aggregation with deduplication
- Configurable radius, altitude filters, scan interval
- WebSocket live updates with auto-reconnect
- Image caching with 24-hour TTL

### Changed
- N/A

### Fixed
- N/A

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