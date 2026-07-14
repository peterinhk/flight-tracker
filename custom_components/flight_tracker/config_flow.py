"""Config flow for Flight Tracker integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    API_SOURCES,
    CONF_API_SOURCES,
    CONF_APIS_ENABLED,
    CONF_FILTER_EMERGENCY,
    CONF_FILTER_MILITARY,
    CONF_MAX_ALTITUDE,
    CONF_MIN_ALTITUDE,
    CONF_PLANESPOTTERS_EMAIL,
    CONF_RADIUS_KM,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_ON_MAP,
    DEFAULT_API_SOURCES,
    DEFAULT_MAX_ALTITUDE,
    DEFAULT_MIN_ALTITUDE,
    DEFAULT_RADIUS_KM,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class FlightTrackerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flight Tracker."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate coordinates
            lat = user_input.get(CONF_LATITUDE)
            lon = user_input.get(CONF_LONGITUDE)
            if lat is None or lon is None:
                errors["base"] = "invalid_coordinates"
            else:
                # Check if already configured
                await self.async_set_unique_id(f"{lat}_{lon}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Flight Tracker ({lat:.4f}, {lon:.4f})",
                    data={**user_input, CONF_APIS_ENABLED: user_input.get(CONF_API_SOURCES, DEFAULT_API_SOURCES)},
                )

        # Default to HA location
        lat = self.hass.config.latitude
        lon = self.hass.config.longitude

        schema = vol.Schema(
            {
                vol.Required(CONF_LATITUDE, default=lat): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-90,
                        max=90,
                        step=0.0001,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_LONGITUDE, default=lon): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=-180,
                        max=180,
                        step=0.0001,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(CONF_RADIUS_KM, default=DEFAULT_RADIUS_KM): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=500,
                        step=1,
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="km",
                    )
                ),
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10,
                        max=300,
                        step=5,
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="seconds",
                    )
                ),
                vol.Required(CONF_APIS_ENABLED, default=DEFAULT_API_SOURCES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(API_SOURCES.keys()),
                        translation_key="api_sources",
                        multiple=True,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_PLANESPOTTERS_EMAIL): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.EMAIL,
                    )
                ),
                vol.Required(CONF_MIN_ALTITUDE, default=DEFAULT_MIN_ALTITUDE): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=60000,
                        step=100,
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="ft",
                    )
                ),
                vol.Required(CONF_MAX_ALTITUDE, default=DEFAULT_MAX_ALTITUDE): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=60000,
                        step=100,
                        mode=selector.NumberSelectorMode.SLIDER,
                        unit_of_measurement="ft",
                    )
                ),
                vol.Optional(CONF_FILTER_MILITARY, default=False): selector.BooleanSelector(),
                vol.Optional(CONF_FILTER_EMERGENCY, default=False): selector.BooleanSelector(),
                vol.Optional(CONF_SHOW_ON_MAP, default=True): selector.BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "api_sources_desc": ", ".join(API_SOURCES.values()),
            },
        )

    async def async_step_reconfigure(self, user_input: dict | None = None) -> FlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user(user_input)
