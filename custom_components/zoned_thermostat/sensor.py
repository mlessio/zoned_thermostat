"""Sensor platform for Zoned Heating Thermostat."""

from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
    """Set up sensor entities from config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ZonedThermostatCoordinator = data["coordinator"]

    entities: list[SensorEntity] = []

    # 1. System sensors
    entities.append(ZonedSystemModeSensor(coordinator))
    entities.append(ZonedActiveZonesCountSensor(coordinator))

    # 2. Zone sensors
    for zone in coordinator.system.zones.values():
        entities.append(ZonedZoneStatusSensor(coordinator, zone))
        entities.append(ZonedPumpStatusSensor(coordinator, zone))

        # 3. Room sensors
        for room in zone.rooms.values():
            entities.append(ZonedRoomStatusSensor(coordinator, room))
            entities.append(ZonedRoomCurrentTempSensor(coordinator, room))
            entities.append(ZonedRoomTargetTempSensor(coordinator, room))

    async_add_entities(entities)


class ZonedSystemModeSensor(SensorEntity):
    """Sensor reporting the global system heating mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "system_mode"
    _attr_icon = "mdi:home-thermometer"

    def __init__(self, coordinator: ZonedThermostatCoordinator) -> None:
        """Initialize the system mode sensor."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.system.system_id}_global_mode"
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
    def native_value(self) -> str:
        """Return system global mode."""
        return self.coordinator.system.global_mode.value


class ZonedActiveZonesCountSensor(SensorEntity):
    """Sensor reporting count of zones currently requiring heat."""

    _attr_has_entity_name = True
    _attr_translation_key = "active_zones_count"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:radiator"

    def __init__(self, coordinator: ZonedThermostatCoordinator) -> None:
        """Initialize the active zones count sensor."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.system.system_id}_active_zones_count"
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
    def native_value(self) -> int:
        """Return count of active zones."""
        return self.coordinator.system.total_active_zones_count


class ZonedZoneStatusSensor(SensorEntity):
    """Sensor reporting operating status of a zone."""

    _attr_has_entity_name = True
    _attr_translation_key = "zone_status"
    _attr_icon = "mdi:floor-plan"

    def __init__(
        self, coordinator: ZonedThermostatCoordinator, zone: HeatingZone
    ) -> None:
        """Initialize the zone status sensor."""
        self.coordinator = coordinator
        self.zone = zone
        self._attr_unique_id = f"{coordinator.system.system_id}_{zone.zone_id}_status"
        self._unsub_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to Zone device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"zone_{self.zone.zone_id}")},
            name=self.zone.name,
            manufacturer="Zoned Thermostat",
            model="Zone Aggregator",
            via_device=(DOMAIN, f"system_{self.coordinator.system.system_id}"),
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
    def native_value(self) -> str:
        """Return zone state."""
        return self.zone.state.value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return diagnostic attributes."""
        return {
            "status_reason": self.zone.status_reason,
            "active_rooms": self.zone.active_rooms,
        }


class ZonedPumpStatusSensor(SensorEntity):
    """Sensor reporting pump status and anti-short-cycle reason."""

    _attr_has_entity_name = True
    _attr_translation_key = "pump_status"
    _attr_icon = "mdi:pump"

    def __init__(
        self, coordinator: ZonedThermostatCoordinator, zone: HeatingZone
    ) -> None:
        """Initialize pump status sensor."""
        self.coordinator = coordinator
        self.zone = zone
        self._attr_unique_id = (
            f"{coordinator.system.system_id}_{zone.zone_id}_pump_status"
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
            via_device=(DOMAIN, f"system_{self.coordinator.system.system_id}"),
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
    def native_value(self) -> str:
        """Return pump logical state."""
        return self.zone.pump_controller.state.value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return pump controller internal details and timing reason."""
        return {
            "pump_switch_id": self.zone.pump_controller.pump_switch_id,
            "is_physically_on": self.zone.pump_controller.is_physically_on,
            "status_reason": self.zone.pump_controller.status_reason,
            "min_on_time": self.zone.pump_controller.min_on_time,
            "min_off_time": self.zone.pump_controller.min_off_time,
            "startup_delay": self.zone.pump_controller.startup_delay,
            "shutdown_delay": self.zone.pump_controller.shutdown_delay,
        }


class ZonedRoomStatusSensor(SensorEntity):
    """Sensor reporting operating status of a room."""

    _attr_has_entity_name = True
    _attr_translation_key = "room_status"
    _attr_icon = "mdi:thermostat"

    def __init__(
        self, coordinator: ZonedThermostatCoordinator, room: HeatingRoom
    ) -> None:
        """Initialize the room status sensor."""
        self.coordinator = coordinator
        self.room = room
        self._attr_unique_id = f"{coordinator.system.system_id}_{room.room_id}_status"
        self._unsub_listener = None

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to Room device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"room_{self.room.room_id}")},
            name=self.room.name,
            manufacturer="Zoned Thermostat",
            model="Logical Room Thermostat",
            via_device=(DOMAIN, f"zone_{self.room.zone_id}"),
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
    def native_value(self) -> str:
        """Return room state."""
        return self.room.state.value

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return status reason."""
        return {
            "status_reason": self.room.status_reason,
            "hvac_mode": self.room.hvac_mode,
            "heat_demand": self.room.heat_demand,
        }


class ZonedRoomCurrentTempSensor(SensorEntity):
    """Sensor reporting current aggregated room temperature."""

    _attr_has_entity_name = True
    _attr_translation_key = "current_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self, coordinator: ZonedThermostatCoordinator, room: HeatingRoom
    ) -> None:
        """Initialize current temperature sensor."""
        self.coordinator = coordinator
        self.room = room
        self._attr_unique_id = (
            f"{coordinator.system.system_id}_{room.room_id}_current_temperature"
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
            via_device=(DOMAIN, f"zone_{self.room.zone_id}"),
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
    def native_value(self) -> Optional[float]:
        """Return room current temperature."""
        return self.room.current_temp


class ZonedRoomTargetTempSensor(SensorEntity):
    """Sensor reporting target room temperature."""

    _attr_has_entity_name = True
    _attr_translation_key = "target_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self, coordinator: ZonedThermostatCoordinator, room: HeatingRoom
    ) -> None:
        """Initialize target temperature sensor."""
        self.coordinator = coordinator
        self.room = room
        self._attr_unique_id = (
            f"{coordinator.system.system_id}_{room.room_id}_target_temperature"
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
            via_device=(DOMAIN, f"zone_{self.room.zone_id}"),
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
    def native_value(self) -> float:
        """Return room target temperature."""
        return self.room.target_temp
