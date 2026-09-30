"""Zoned Heating Thermostat custom integration."""

import logging
from typing import Any

try:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
except ImportError:
    ConfigEntry = object  # type: ignore
    HomeAssistant = object  # type: ignore

from .const import DOMAIN, PLATFORMS
from .coordinator import ZonedThermostatCoordinator
from .core.storage import ZonedThermostatStorage
from .core.system import HeatingSystem
from .panel import async_register_panel, async_unregister_panel
from .websocket import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Zoned Heating Thermostat integration via YAML (unused, Zero-YAML)."""
    hass.data.setdefault(DOMAIN, {})
    # Register WebSocket API endpoints once
    async_register_websocket_commands(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zoned Heating Thermostat from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    storage = ZonedThermostatStorage(hass, entry.entry_id)

    # 1. Load persisted system or construct from entry config
    system = await storage.async_load()
    if system is None:
        _LOGGER.info("No existing storage found. Initializing system from config entry data.")
        system = HeatingSystem.from_dict(entry.data)
        await storage.async_save(system)

    # 2. Instantiate coordinator
    coordinator = ZonedThermostatCoordinator(hass, system, storage)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "system": system,
        "storage": storage,
    }

    # 3. Register custom dedicated panel in sidebar
    await async_register_panel(hass)

    # 4. Set up entity platforms (climate, binary_sensor, sensor)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 5. Initialize coordinator listeners and deterministic cold-boot evaluation
    await coordinator.async_setup()

    # 6. Listen for option updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info(
        "Zoned Heating Thermostat '%s' initialized with %d zones and %d rooms.",
        system.name,
        len(system.zones),
        len(system.all_rooms()),
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data:
        coordinator: ZonedThermostatCoordinator = data["coordinator"]
        await coordinator.async_unload()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    if not hass.data[DOMAIN]:
        async_unregister_panel(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Reload config entry after options update."""
    return await hass.config_entries.async_reload(entry.entry_id)
