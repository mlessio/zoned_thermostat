"""WebSocket API endpoints for the Zoned Heating Thermostat dedicated frontend panel."""

import logging
from typing import Any, Dict

try:
    import voluptuous as vol
    from homeassistant.components import websocket_api
    from homeassistant.core import HomeAssistant, callback
except ImportError:
    import unittest.mock as mock

    vol = mock.MagicMock()  # type: ignore
    websocket_api = mock.MagicMock()  # type: ignore
    HomeAssistant = object  # type: ignore

    def callback(fn):  # type: ignore
        return fn

from .const import DOMAIN
from .coordinator import ZonedThermostatCoordinator
from .core.enums import GlobalMode, OverrideMode

_LOGGER = logging.getLogger(__name__)


def _get_coordinator(hass: HomeAssistant, entry_id: str) -> ZonedThermostatCoordinator:
    """Helper to retrieve coordinator from entry_id or default."""
    domain_data = hass.data.get(DOMAIN, {})
    if entry_id and entry_id in domain_data:
        return domain_data[entry_id]["coordinator"]
    if domain_data:
        # Return first available coordinator
        first_entry = next(iter(domain_data.values()))
        return first_entry["coordinator"]
    raise websocket_api.HomeAssistantError("Zoned Heating Thermostat is not loaded.")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/get_overview",
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_get_overview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle getting full system state overview."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        connection.send_result(msg["id"], coordinator.system.to_dict())
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/set_room_override",
        vol.Optional("entry_id"): str,
        vol.Required("room_id"): str,
        vol.Required("target"): vol.Coerce(float),
        vol.Optional("mode", default="until_next_change"): str,
        vol.Optional("duration_minutes"): vol.Coerce(int),
    }
)
@websocket_api.async_response
async def ws_set_room_override(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Set manual temperature override on a room."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        mode = OverrideMode(msg["mode"])
        await coordinator.async_set_room_temperature(
            room_id=msg["room_id"],
            target_temp=msg["target"],
            mode=mode,
            duration_minutes=msg.get("duration_minutes"),
        )
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/clear_room_override",
        vol.Optional("entry_id"): str,
        vol.Required("room_id"): str,
    }
)
@websocket_api.async_response
async def ws_clear_room_override(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Clear manual temperature override from a room."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        await coordinator.async_clear_room_override(msg["room_id"])
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/set_room_hvac_mode",
        vol.Optional("entry_id"): str,
        vol.Required("room_id"): str,
        vol.Required("hvac_mode"): str,
    }
)
@websocket_api.async_response
async def ws_set_room_hvac_mode(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Set HVAC mode ('heat' or 'off') on a room."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        await coordinator.async_set_room_hvac_mode(
            msg["room_id"], msg["hvac_mode"]
        )
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/set_global_mode",
        vol.Optional("entry_id"): str,
        vol.Required("mode"): str,
    }
)
@websocket_api.async_response
async def ws_set_global_mode(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Set global system mode ('home', 'away', 'frost', 'off', etc.)."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        mode = GlobalMode(msg["mode"])
        await coordinator.async_set_global_mode(mode)
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/set_preset",
        vol.Optional("entry_id"): str,
        vol.Required("preset_name"): str,
        vol.Required("value"): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def ws_set_preset(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Set global preset temperature value."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        coordinator.system.set_preset(msg["preset_name"], msg["value"])
        await coordinator.async_evaluate()
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/update_schedule",
        vol.Optional("entry_id"): str,
        vol.Required("room_id"): str,
        vol.Required("schedule"): dict,
    }
)
@websocket_api.async_response
async def ws_update_schedule(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Update weekly schedule of a room."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        await coordinator.async_update_room_schedule(
            msg["room_id"], msg["schedule"]
        )
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/copy_schedule",
        vol.Optional("entry_id"): str,
        vol.Required("source_room_id"): str,
        vol.Required("target_room_id"): str,
    }
)
@websocket_api.async_response
async def ws_copy_schedule(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Copy weekly schedule between rooms."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        coordinator.system.copy_room_schedule(
            msg["source_room_id"], msg["target_room_id"]
        )
        await coordinator.async_evaluate()
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/copy_zone_schedule",
        vol.Optional("entry_id"): str,
        vol.Required("source_zone_id"): str,
        vol.Required("target_zone_id"): str,
    }
)
@websocket_api.async_response
async def ws_copy_zone_schedule(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Copy schedule from one zone to another."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        coordinator.system.copy_zone_schedule(
            msg["source_zone_id"], msg["target_zone_id"]
        )
        await coordinator.async_evaluate()
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/get_diagnostic_events",
        vol.Optional("entry_id"): str,
        vol.Optional("limit", default=50): vol.Coerce(int),
    }
)
@websocket_api.async_response
async def ws_get_diagnostic_events(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Retrieve recent diagnostic events."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        events = coordinator.system.event_log.get_events(limit=msg.get("limit", 50))
        connection.send_result(msg["id"], events)
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all websocket endpoints with Home Assistant."""
    websocket_api.async_register_command(hass, ws_get_overview)
    websocket_api.async_register_command(hass, ws_set_room_override)
    websocket_api.async_register_command(hass, ws_clear_room_override)
    websocket_api.async_register_command(hass, ws_set_room_hvac_mode)
    websocket_api.async_register_command(hass, ws_set_global_mode)
    websocket_api.async_register_command(hass, ws_set_preset)
    websocket_api.async_register_command(hass, ws_update_schedule)
    websocket_api.async_register_command(hass, ws_copy_schedule)
    websocket_api.async_register_command(hass, ws_copy_zone_schedule)
    websocket_api.async_register_command(hass, ws_get_diagnostic_events)
