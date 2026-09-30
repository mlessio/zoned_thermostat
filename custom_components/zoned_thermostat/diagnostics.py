"""Diagnostics support for Zoned Heating Thermostat."""

from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ZonedThermostatCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator: ZonedThermostatCoordinator = data.get("coordinator")
    if not coordinator:
        return {"error": "Coordinator not loaded"}

    return {
        "system": coordinator.system.to_dict(),
        "entry_options": dict(entry.options),
        "recent_event_log": coordinator.system.event_log.get_events(limit=100),
    }
