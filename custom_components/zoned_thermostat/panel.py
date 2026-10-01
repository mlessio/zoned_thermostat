"""Custom Sidebar Panel registration for Zoned Heating Thermostat."""

import logging
from pathlib import Path

try:
    from homeassistant.components import frontend, panel_custom
    from homeassistant.core import HomeAssistant
except ImportError:
    frontend = None  # type: ignore
    panel_custom = None  # type: ignore
    HomeAssistant = object  # type: ignore

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_URL = "zoned-thermostat"
PANEL_TITLE = "Riscaldamento"
PANEL_ICON = "mdi:home-thermometer-outline"
PANEL_STATIC_PATH = "/zoned_thermostat_static"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the static resource and sidebar panel in Home Assistant."""
    frontend_dir = Path(__file__).parent / "frontend"

    # 1. Register static directory for frontend JavaScript
    try:
        if hasattr(hass.http, "async_register_static_paths"):
            from homeassistant.components.http import StaticPath
            await hass.http.async_register_static_paths([
                StaticPath(
                    PANEL_STATIC_PATH,
                    str(frontend_dir),
                    cache_headers=False,
                )
            ])
        elif hasattr(hass.http, "register_static_path"):
            hass.http.register_static_path(
                PANEL_STATIC_PATH, str(frontend_dir), cache_headers=False
            )
    except Exception as err:
        _LOGGER.debug("Static path registration notice: %s", err)

    # 2. Prevent duplicate panel registration error if already present
    if hasattr(hass, "data") and PANEL_URL in hass.data.get("frontend_panels", {}):
        _LOGGER.debug("Panel %s already registered.", PANEL_URL)
        return

    # 3. Register panel in sidebar via panel_custom
    try:
        if panel_custom and hasattr(panel_custom, "async_register_panel"):
            await panel_custom.async_register_panel(
                hass,
                frontend_url_path=PANEL_URL,
                webcomponent_name="zoned-thermostat-panel",
                sidebar_title=PANEL_TITLE,
                sidebar_icon=PANEL_ICON,
                module_url=f"{PANEL_STATIC_PATH}/zoned-thermostat-panel.js",
                require_admin=False,
                embed_iframe=False,
            )
            _LOGGER.info("Registered Zoned Thermostat sidebar panel via panel_custom at /%s", PANEL_URL)
        elif frontend and hasattr(frontend, "async_register_built_in_panel"):
            frontend.async_register_built_in_panel(
                hass,
                component_name="custom",
                sidebar_title=PANEL_TITLE,
                sidebar_icon=PANEL_ICON,
                frontend_url_path=PANEL_URL,
                config={
                    "_panel_type": "zoned-thermostat-panel",
                    "name": "zoned-thermostat-panel",
                    "module_url": f"{PANEL_STATIC_PATH}/zoned-thermostat-panel.js",
                },
                require_admin=False,
            )
            _LOGGER.info("Registered Zoned Thermostat sidebar panel via frontend at /%s", PANEL_URL)
    except Exception as err:
        _LOGGER.warning("Could not register sidebar panel: %s", err)


def async_unregister_panel(hass: HomeAssistant) -> None:
    """Unregister panel from Home Assistant."""
    try:
        frontend.async_remove_panel(hass, PANEL_URL)
    except Exception as err:
        _LOGGER.debug("Error unregistering panel: %s", err)
