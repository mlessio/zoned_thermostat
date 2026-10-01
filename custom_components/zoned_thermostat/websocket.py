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

    class _MockWsApi:
        @staticmethod
        def websocket_command(*args, **kwargs):
            def decorator(fn):
                return fn
            return decorator

        @staticmethod
        def async_response(fn):
            return fn

        class HomeAssistantError(Exception):
            pass

    websocket_api = _MockWsApi()  # type: ignore
    HomeAssistant = object  # type: ignore

    def callback(fn):  # type: ignore
        return fn

from .const import (
    DEFAULT_BUFFER_OVERHEAT_HYSTERESIS,
    DEFAULT_BUFFER_OVERHEAT_TEMP,
    DOMAIN,
)
from .coordinator import ZonedThermostatCoordinator
from .core.enums import GlobalMode, OverrideMode

_LOGGER = logging.getLogger(__name__)


def _get_coordinator(hass: HomeAssistant, entry_id: str) -> ZonedThermostatCoordinator:
    """Helper to retrieve coordinator from entry_id or default."""
    domain_data = hass.data.get(DOMAIN, {})
    if entry_id and entry_id in domain_data and isinstance(domain_data[entry_id], dict):
        return domain_data[entry_id]["coordinator"]
    for val in domain_data.values():
        if isinstance(val, dict) and "coordinator" in val:
            return val["coordinator"]
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


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/apply_room_preset",
        vol.Optional("entry_id"): str,
        vol.Required("room_id"): str,
        vol.Required("preset"): str,
    }
)
@websocket_api.async_response
async def ws_apply_room_preset(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Apply room preset (Comfort, Eco, etc.) to a specific room."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        await coordinator.async_apply_room_preset(
            room_id=msg["room_id"], preset_name=msg["preset"]
        )
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/set_room_presets",
        vol.Optional("entry_id"): str,
        vol.Required("room_id"): str,
        vol.Required("presets"): dict,
    }
)
@websocket_api.async_response
async def ws_set_room_presets(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Configure independent preset values (comfort, eco, etc.) for a specific room."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        await coordinator.async_set_room_presets(
            room_id=msg["room_id"], presets=msg["presets"]
        )
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/set_zone_pump_manual",
        vol.Optional("entry_id"): str,
        vol.Required("zone_id"): str,
        vol.Required("manual_on"): bool,
    }
)
@websocket_api.async_response
async def ws_set_zone_pump_manual(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Toggle manual ON override for a zone circulation pump."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        await coordinator.async_set_zone_pump_manual(
            zone_id=msg["zone_id"], manual_on=msg["manual_on"]
        )
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        connection.send_error(msg["id"], "error", str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "zoned_thermostat/set_buffer_settings",
        vol.Optional("entry_id"): str,
        vol.Optional("sensor_id"): vol.Any(str, None),
        vol.Required("min_temp"): vol.Coerce(float),
        vol.Required("hysteresis"): vol.Coerce(float),
        vol.Optional("overheat_temp", default=DEFAULT_BUFFER_OVERHEAT_TEMP): vol.Coerce(float),
        vol.Optional("overheat_hysteresis", default=DEFAULT_BUFFER_OVERHEAT_HYSTERESIS): vol.Coerce(float),
    }
)
@websocket_api.async_response
async def ws_set_buffer_settings(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Configure thermal storage / puffer temperature sensor, interlock, and safety dissipation."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id", ""))
        await coordinator.async_set_buffer_settings(
            sensor_id=msg.get("sensor_id"),
            min_temp=msg["min_temp"],
            hysteresis=msg["hysteresis"],
            overheat_temp=msg.get("overheat_temp", DEFAULT_BUFFER_OVERHEAT_TEMP),
            overheat_hysteresis=msg.get("overheat_hysteresis", DEFAULT_BUFFER_OVERHEAT_HYSTERESIS),
        )
        connection.send_result(msg["id"], {"success": True})
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
    websocket_api.async_register_command(hass, ws_apply_room_preset)
    websocket_api.async_register_command(hass, ws_set_room_presets)
    websocket_api.async_register_command(hass, ws_set_zone_pump_manual)
    websocket_api.async_register_command(hass, ws_set_buffer_settings)
    websocket_api.async_register_command(hass, ws_update_schedule)
    websocket_api.async_register_command(hass, ws_copy_schedule)
    websocket_api.async_register_command(hass, ws_copy_zone_schedule)
    websocket_api.async_register_command(hass, ws_get_diagnostic_events)
