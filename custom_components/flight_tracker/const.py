"""Constants for Flight Tracker integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "flight_tracker"
NAME = "Flight Tracker"
VERSION = "1.0.0"

PLATFORMS: list[Platform] = [
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

# Configuration keys
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_RADIUS_KM = "radius_km"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_WEBSOCKET = "enable_websocket"
CONF_APIS_ENABLED = "apis_enabled"
CONF_API_SOURCES = "api_sources"  # alias for config flow
CONF_PLANESPOTTERS_EMAIL = "planespotters_email"
CONF_MIN_ALTITUDE = "min_altitude"
CONF_MAX_ALTITUDE = "max_altitude"
CONF_TRACK_MILITARY = "track_military"
CONF_FILTER_MILITARY = "filter_military"  # alias for config flow
CONF_FILTER_EMERGENCY = "filter_emergency"
CONF_TRACK_GA = "track_ga"
CONF_SHOW_ON_MAP = "show_on_map"
CONF_MAX_ENTITIES = "max_entities"

# Defaults
DEFAULT_RADIUS_KM = 50
DEFAULT_SCAN_INTERVAL = 60  # seconds
DEFAULT_ENABLE_WEBSOCKET = True
DEFAULT_MIN_ALTITUDE = 0  # feet
DEFAULT_MAX_ALTITUDE = 60000  # feet
DEFAULT_TRACK_MILITARY = False
DEFAULT_FILTER_MILITARY = False
DEFAULT_FILTER_EMERGENCY = False
DEFAULT_TRACK_GA = True
DEFAULT_SHOW_ON_MAP = True
DEFAULT_MAX_ENTITIES = 100
DEFAULT_API_SOURCES = ["adsb_fi", "adsb_lol"]
DEFAULT_APIS_ENABLED = ["adsb_fi", "adsb_lol"]

# API endpoints
ADSB_FI_REST = "https://api.adsb.fi/v2"
ADSB_FI_WS = "wss://api.adsb.fi/v2/ws"

ADSB_LOL_REST = "https://api.adsb.lol/v2"
ADSB_LOL_WS = "wss://api.adsb.lol/v2/ws"

# ADSB.com - investigate availability
ADSB_COM_REST = "https://api.adsb.com/v1"  # May require API key
ADSB_COM_WS = "wss://api.adsb.com/v1/ws"

PLANESPOTTERS_API = "https://api.planespotters.net/pub"

# API Sources for config flow
API_SOURCES = {
    "adsb_fi": "ADSB.fi",
    "adsb_lol": "ADSB.lol",
    "adsb_com": "ADSB.com",
}
API_SOURCE_ADSB_FI = "adsb_fi"
API_SOURCE_ADSB_LOL = "adsb_lol"
API_SOURCE_ADSB_COM = "adsb_com"

# Aircraft categories (from ADSB spec)
CATEGORY_NONE = 0
CATEGORY_LIGHT = 1
CATEGORY_SMALL = 2
CATEGORY_LARGE = 3
CATEGORY_HIGH_VORTEX = 4
CATEGORY_HEAVY = 5
CATEGORY_HIGH_PERF = 6
CATEGORY_ROTORCRAFT = 7
CATEGORY_GLIDER = 9
CATEGORY_LIGHTER_THAN_AIR = 10
CATEGORY_PARACHUTE = 11
CATEGORY_ULTRALIGHT = 12
CATEGORY_UAV = 14
CATEGORY_SPACE = 15
CATEGORY_SURFACE_EMERGENCY = 17
CATEGORY_SURFACE_SERVICE = 18
CATEGORY_POINT_OBSTACLE = 19
CATEGORY_LINE_OBSTACLE = 20
CATEGORY_MILITARY = 3  # Some sources use 3/4 for military

# Category labels
CATEGORY_LABELS = {
    CATEGORY_NONE: "Unknown",
    CATEGORY_LIGHT: "Light",
    CATEGORY_SMALL: "Small",
    CATEGORY_LARGE: "Large",
    CATEGORY_HIGH_VORTEX: "High Vortex",
    CATEGORY_HEAVY: "Heavy",
    CATEGORY_HIGH_PERF: "High Performance",
    CATEGORY_ROTORCRAFT: "Rotorcraft",
    CATEGORY_GLIDER: "Glider",
    CATEGORY_LIGHTER_THAN_AIR: "Lighter than Air",
    CATEGORY_PARACHUTE: "Parachute",
    CATEGORY_ULTRALIGHT: "Ultralight",
    CATEGORY_UAV: "UAV/Drone",
    CATEGORY_SPACE: "Space",
    CATEGORY_SURFACE_EMERGENCY: "Surface Emergency",
    CATEGORY_SURFACE_SERVICE: "Surface Service",
    CATEGORY_POINT_OBSTACLE: "Point Obstacle",
    CATEGORY_LINE_OBSTACLE: "Line Obstacle",
}

# Military categories (some sources)
MILITARY_CATEGORIES = {3, 4, 5}  # Heavy, High Vortex, etc.

# WebSocket message types
WS_HEARTBEAT = "heartbeat"
WS_STATS = "stats"
WS_FLIGHTS = "flights"
WS_UPDATE_INTERVAL = "update_interval"

# Attributes for device tracker entities
ATTR_CALLSIGN = "callsign"
ATTR_REGISTRATION = "registration"
ATTR_ICAO24 = "icao24"
ATTR_ALTITUDE = "altitude"
ATTR_ALTITUDE_GEOMETRIC = "altitude_geometric"
ATTR_SPEED = "speed"
ATTR_HEADING = "heading"
ATTR_VERTICAL_RATE = "vertical_rate"
ATTR_SQUAWK = "squawk"
ATTR_CATEGORY = "category"
ATTR_CATEGORY_LABEL = "category_label"
ATTR_AIRCRAFT_TYPE = "aircraft_type"
ATTR_OPERATOR = "operator"
ATTR_ORIGIN = "origin"
ATTR_DESTINATION = "destination"
ATTR_IMAGE_URL = "image_url"
ATTR_LAST_SEEN = "last_seen"
ATTR_SOURCE_API = "source_api"
ATTR_RSSI = "rssi"
ATTR_DISTANCE_KM = "distance_km"

# Sensor names
SENSOR_FLIGHTS_TOTAL = "flights_total"
SENSOR_FLIGHTS_NEAREST = "flight_nearest"
SENSOR_FLIGHTS_HIGHEST = "flight_highest"
SENSOR_FLIGHTS_FASTEST = "flight_fastest"
SENSOR_IMAGES_CACHED = "images_cached"

# Services
SERVICE_REFRESH = "refresh"
SERVICE_CENTER_MAP = "center_map"
SERVICE_SET_RADIUS = "set_radius"

# Update intervals
MIN_SCAN_INTERVAL = 30  # seconds
MAX_SCAN_INTERVAL = 300
WEBSOCKET_RECONNECT_BASE = 1
WEBSOCKET_RECONNECT_MAX = 60

# Image cache
IMAGE_CACHE_TTL_HOURS = 24
NEGATIVE_CACHE_TTL_HOURS = 1

# Entity cleanup
ENTITY_STALE_THRESHOLD_SECONDS = 300  # 5 minutes
