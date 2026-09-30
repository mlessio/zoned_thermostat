"""Climate platform for Zoned Heating Thermostat."""

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZonedThermostatCoordinator
from .core.enums import OverrideMode, RoomState
from .core.room import HeatingRoom

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ZonedThermostatCoordinator = data["coordinator"]

    entities = [
        ZonedRoomClimate(coordinator, room)
        for room in coordinator.system.all_rooms()
    ]
    async_add_entities(entities)


class ZonedRoomClimate(ClimateEntity):
    """Climate entity representing a logical room thermostat."""

    _attr_has_entity_name = True
    _attr_name = None  # Uses device name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: ZonedThermostatCoordinator,
        room: HeatingRoom,
    ) -> None:
        """Initialize the climate entity."""
        self.coordinator = coordinator
        self.room = room
        self._attr_unique_id = (
            f"{coordinator.system.system_id}_{room.room_id}_climate"
        )
        self._unsub_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        """Link this room entity to its device in Home Assistant Device Registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"room_{self.room.room_id}")},
            name=self.room.name,
            manufacturer="Zoned Thermostat",
            model="Logical Room Thermostat",
            via_device=(DOMAIN, f"zone_{self.room.zone_id}"),
        )

    async def async_added_to_hass(self) -> None:
        """Register entity update callback with coordinator."""
        self._unsub_listener = self.coordinator.register_entity_listener(
            self._handle_coordinator_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callback when entity is removed."""
        if self._unsub_listener:
            self._unsub_listener()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current aggregated room temperature."""
        return self.room.current_temp

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self.room.target_temp

    @property
    def target_temperature_step(self) -> float:
        """Return precision step for target temperature."""
        return self.room.temp_step

    @property
    def min_temp(self) -> float:
        """Return minimum allowed temperature."""
        return self.room.min_temp

    @property
    def max_temp(self) -> float:
        """Return maximum allowed temperature."""
        return self.room.max_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if self.room.hvac_mode == "off":
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        """Return current physical HVAC action."""
        if self.room.hvac_mode == "off":
            return HVACAction.OFF
        if self.room.heat_demand:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the active preset mode if any."""
        return self.room.active_preset

    @property
    def preset_modes(self) -> List[str]:
        """Return available presets."""
        presets = list(self.coordinator.system.presets.keys())
        return ["none"] + presets

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return additional diagnostic attributes."""
        return {
            "heat_demand": self.room.heat_demand,
            "status_reason": self.room.status_reason,
            "room_state": self.room.state.value,
            "is_window_open": self.room.is_window_open,
            "hysteresis": self.room.hysteresis,
            "active_override": (
                self.room.manual_override.to_dict()
                if self.room.manual_override
                else None
            ),
            "trv_states": self.room.trv_states,
            "zone_id": self.room.zone_id,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature (creates a manual override)."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return

        await self.coordinator.async_set_room_temperature(
            room_id=self.room.room_id,
            target_temp=float(temp),
            mode=OverrideMode.UNTIL_NEXT_CHANGE,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode ('heat' or 'off')."""
        mode_str = "off" if hvac_mode == HVACMode.OFF else "heat"
        await self.coordinator.async_set_room_hvac_mode(
            room_id=self.room.room_id, hvac_mode=mode_str
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        if preset_mode == "none":
            await self.coordinator.async_clear_room_override(self.room.room_id)
            return

        preset_clean = preset_mode.lower().strip()
        presets = {
            **self.coordinator.system.presets,
            **self.room.presets_override,
        }
        if preset_clean in presets:
            target_val = presets[preset_clean]
            await self.coordinator.async_set_room_temperature(
                room_id=self.room.room_id,
                target_temp=target_val,
                mode=OverrideMode.UNTIL_NEXT_CHANGE,
            )
            self.room.active_preset = preset_clean
            self.coordinator.notify_entity_listeners()
