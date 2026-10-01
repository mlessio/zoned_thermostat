"""Binary sensor platform for Zoned Heating Thermostat."""

from typing import Any, Dict

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZonedThermostatCoordinator
from .core.room import HeatingRoom
from .core.zone import HeatingZone


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ZonedThermostatCoordinator = data["coordinator"]

    entities: list[BinarySensorEntity] = []

    # 1. System Total Heat Demand
    entities.append(ZonedSystemDemandBinarySensor(coordinator))

    # 2. Zone Heat Demands
    for zone in coordinator.system.zones.values():
        entities.append(ZonedZoneDemandBinarySensor(coordinator, zone))

        # 3. Room Heat Demands
        for room in zone.rooms.values():
            entities.append(ZonedRoomDemandBinarySensor(coordinator, room))

    async_add_entities(entities)


class ZonedSystemDemandBinarySensor(BinarySensorEntity):
    """Binary sensor indicating if any zone in the heating system demands heat."""

    _attr_has_entity_name = True
    _attr_translation_key = "system_heat_demand"
    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(self, coordinator: ZonedThermostatCoordinator) -> None:
        """Initialize the system demand binary sensor."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.system.system_id}_total_heat_demand"
        self._unsub_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to System root device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"system_{self.coordinator.system.system_id}")},
            name=self.coordinator.system.name,
            manufacturer="Zoned Thermostat",
            model="Central Heating Controller",
        )

    async def async_added_to_hass(self) -> None:
        """Register callback."""
        self._unsub_listener = self.coordinator.register_entity_listener(
            self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callback."""
        if self._unsub_listener:
            self._unsub_listener()

    @callback
    def _handle_update(self) -> None:
        """Update state."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if at least one zone demands heat."""
        return self.coordinator.system.total_heat_demand

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return active zones count and names."""
        return {
            "active_zones_count": self.coordinator.system.total_active_zones_count,
            "active_rooms_count": self.coordinator.system.total_active_rooms_count,
        }


class ZonedZoneDemandBinarySensor(BinarySensorEntity):
    """Binary sensor indicating if a specific zone demands heat."""

    _attr_has_entity_name = True
    _attr_translation_key = "zone_heat_demand"
    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(
        self, coordinator: ZonedThermostatCoordinator, zone: HeatingZone
    ) -> None:
        """Initialize the zone heat demand sensor."""
        self.coordinator = coordinator
        self.zone = zone
        self._attr_unique_id = (
            f"{coordinator.system.system_id}_{zone.zone_id}_heat_demand"
        )
        self._unsub_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to Zone device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"zone_{self.zone.zone_id}")},
            name=self.zone.name,
            manufacturer="Zoned Thermostat",
            model="Zone Aggregator",
        )

    async def async_added_to_hass(self) -> None:
        """Register callback."""
        self._unsub_listener = self.coordinator.register_entity_listener(
            self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callback."""
        if self._unsub_listener:
            self._unsub_listener()

    @callback
    def _handle_update(self) -> None:
        """Update state."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if zone demands heat."""
        return self.zone.heat_demand

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return active demanding rooms in this zone."""
        return {
            "active_rooms": self.zone.active_rooms,
            "pump_state": self.zone.pump_controller.state.value,
            "status_reason": self.zone.status_reason,
        }


class ZonedRoomDemandBinarySensor(BinarySensorEntity):
    """Binary sensor indicating if a specific room demands heat."""

    _attr_has_entity_name = True
    _attr_translation_key = "room_heat_demand"
    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(
        self, coordinator: ZonedThermostatCoordinator, room: HeatingRoom
    ) -> None:
        """Initialize room heat demand sensor."""
        self.coordinator = coordinator
        self.room = room
        self._attr_unique_id = (
            f"{coordinator.system.system_id}_{room.room_id}_heat_demand"
        )
        self._unsub_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to Room device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"room_{self.room.room_id}")},
            name=self.room.name,
            manufacturer="Zoned Thermostat",
            model="Logical Room Thermostat",
        )

    async def async_added_to_hass(self) -> None:
        """Register callback."""
        self._unsub_listener = self.coordinator.register_entity_listener(
            self._handle_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callback."""
        if self._unsub_listener:
            self._unsub_listener()

    @callback
    def _handle_update(self) -> None:
        """Update state."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if room demands heat."""
        return self.room.heat_demand

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return diagnostic explanation."""
        return {
            "status_reason": self.room.status_reason,
            "current_temp": self.room.current_temp,
            "target_temp": self.room.target_temp,
        }
