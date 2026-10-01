"""Coordinator and runtime manager for Zoned Heating Thermostat."""

from datetime import datetime
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set

try:
    from homeassistant.const import (
        ATTR_ENTITY_ID,
        ATTR_TEMPERATURE,
        EVENT_HOMEASSISTANT_STARTED,
        STATE_OFF,
        STATE_ON,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    )
    from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
    from homeassistant.helpers.event import (
        async_track_state_change_event,
        async_track_time_interval,
    )
except ImportError:
    ATTR_ENTITY_ID = "entity_id"
    ATTR_TEMPERATURE = "temperature"
    EVENT_HOMEASSISTANT_STARTED = "homeassistant_started"
    STATE_OFF = "off"
    STATE_ON = "on"
    STATE_UNAVAILABLE = "unavailable"
    STATE_UNKNOWN = "unknown"
    CALLBACK_TYPE = Any  # type: ignore
    Event = Any  # type: ignore
    HomeAssistant = Any  # type: ignore

    def callback(fn):  # type: ignore
        return fn

    async_track_state_change_event = None  # type: ignore
    async_track_time_interval = None  # type: ignore

from .const import (
    DEFAULT_BUFFER_OVERHEAT_HYSTERESIS,
    DEFAULT_BUFFER_OVERHEAT_TEMP,
    DOMAIN,
)
from .core.enums import GlobalMode, OverrideMode, RoomState
from .core.pump import PumpAction
from .core.storage import ZonedThermostatStorage
from .core.system import HeatingSystem

_LOGGER = logging.getLogger(__name__)


class ZonedThermostatCoordinator:
    """Manages Home Assistant state listeners, timer ticks, service calls, and storage."""

    def __init__(
        self,
        hass: HomeAssistant,
        system: HeatingSystem,
        storage: ZonedThermostatStorage,
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.system = system
        self.storage = storage

        self._unsub_listeners: List[CALLBACK_TYPE] = []
        self._entity_listeners: List[Callable[[], None]] = []
        self._tracked_entities: Set[str] = set()

    def register_entity_listener(self, update_callback: Callable[[], None]) -> CALLBACK_TYPE:
        """Register a callback for entities to trigger UI/state update."""
        self._entity_listeners.append(update_callback)

        @callback
        def _remove() -> None:
            if update_callback in self._entity_listeners:
                self._entity_listeners.remove(update_callback)

        return _remove

    def notify_entity_listeners(self) -> None:
        """Notify all registered Home Assistant entities to write state changes."""
        for update_cb in self._entity_listeners:
            try:
                update_cb()
            except Exception as err:
                _LOGGER.error("Error updating entity listener: %s", err)

    async def async_setup(self) -> None:
        """Start listening to state changes and periodic timer."""
        # 1. Gather all entity IDs to observe
        self._rebuild_tracked_entities()

        # 2. Track entity state changes
        if self._tracked_entities:
            unsub_states = async_track_state_change_event(
                self.hass, list(self._tracked_entities), self._handle_state_changed
            )
            self._unsub_listeners.append(unsub_states)

        # 3. Track 30-second interval for schedule evaluation and pump delays
        from datetime import timedelta

        unsub_time = async_track_time_interval(
            self.hass, self._handle_timer_tick, timedelta(seconds=15)
        )
        self._unsub_listeners.append(unsub_time)

        # 4. Immediate state scan across HA states
        self._read_initial_states()

        # 5. Run initial deterministic evaluation
        await self.async_evaluate()

    async def async_unload(self) -> None:
        """Cancel all registered listeners."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        self._entity_listeners.clear()

    def _rebuild_tracked_entities(self) -> None:
        """Populate the set of entity IDs to track."""
        self._tracked_entities.clear()
        if self.system.buffer_temp_sensor:
            self._tracked_entities.add(self.system.buffer_temp_sensor)
        for zone in self.system.zones.values():
            if zone.pump_controller.pump_switch_id:
                self._tracked_entities.add(zone.pump_controller.pump_switch_id)
            for room in zone.rooms.values():
                for s_id in room.temp_sensor_ids:
                    self._tracked_entities.add(s_id)
                for trv in room.trv_ids:
                    self._tracked_entities.add(trv)
                if room.window_sensor_id:
                    self._tracked_entities.add(room.window_sensor_id)
                if room.presence_sensor_id:
                    self._tracked_entities.add(room.presence_sensor_id)

    def _read_initial_states(self) -> None:
        """Inspect current states from HA state machine."""
        for entity_id in self._tracked_entities:
            state = self.hass.states.get(entity_id)
            if state:
                self._process_state(entity_id, state.state, state.attributes)

    @callback
    def _handle_state_changed(self, event: Event) -> None:
        """Handle state change event from Home Assistant."""
        data = event.data
        entity_id = data.get("entity_id")
        new_state = data.get("new_state")
        if not new_state:
            return

        self._process_state(entity_id, new_state.state, new_state.attributes)
        self.hass.async_create_task(self.async_evaluate())

    @callback
    def _handle_timer_tick(self, _now: datetime) -> None:
        """Periodic timer tick for scheduling, min on/off, and delays."""
        self.hass.async_create_task(self.async_evaluate())

    def _process_state(
        self, entity_id: str, state_val: str, attributes: Dict[str, Any]
    ) -> None:
        """Route state update to appropriate domain component."""
        # 0. Check Buffer Storage Sensor
        if self.system.buffer_temp_sensor == entity_id:
            if state_val in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                self.system.update_buffer_temperature(None)
            else:
                try:
                    temp = float(state_val)
                    self.system.update_buffer_temperature(temp)
                except (ValueError, TypeError):
                    self.system.update_buffer_temperature(None)

        # 1. Check Pump Switches
        for zone in self.system.zones.values():
            if zone.pump_controller.pump_switch_id == entity_id:
                if state_val in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    zone.pump_controller.set_unavailable(True)
                else:
                    zone.pump_controller.set_unavailable(False)
                    is_on = state_val.lower() == STATE_ON
                    zone.pump_controller.update_physical_state(is_on)

        # 2. Check Rooms
        for room in self.system.all_rooms():
            # Temperature sensors
            if entity_id in room.temp_sensor_ids:
                if state_val in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    room.update_sensor_temperature(entity_id, None)
                else:
                    try:
                        temp = float(state_val)
                        room.update_sensor_temperature(entity_id, temp)
                    except (ValueError, TypeError):
                        room.update_sensor_temperature(entity_id, None)

            # Window sensor
            if room.window_sensor_id == entity_id:
                is_open = state_val.lower() == STATE_ON
                room.update_window_state(is_open)

            # Presence sensor
            if room.presence_sensor_id == entity_id:
                is_detected = state_val.lower() == STATE_ON
                room.update_presence_state(is_detected)

            # TRVs
            if entity_id in room.trv_ids:
                curr = attributes.get("current_temperature")
                targ = attributes.get("temperature")
                valve = (
                    attributes.get("valve_position")
                    or attributes.get("position")
                    or attributes.get("valve_level")
                )
                hvac_mode = state_val
                room.update_trv_state(
                    trv_id=entity_id,
                    current_temp=curr,
                    target_temp=targ,
                    valve_position=valve,
                    hvac_mode=hvac_mode,
                )

    async def async_evaluate(self) -> None:
        """Run full deterministic evaluation, command hardware, and push entity states."""
        now_dt = datetime.now()
        day_str = now_dt.strftime("%a").lower()[:3]
        time_str = now_dt.strftime("%H:%M")
        now_ts = time.time()

        # Track previous room targets to detect when TRVs must be synchronized
        prev_targets = {r.room_id: r.target_temp for r in self.system.all_rooms()}

        # Core evaluation tick
        pump_actions = self.system.evaluate_tick(
            day=day_str, time_str=time_str, now=now_ts
        )

        # Execute Pump commands
        for zone, action, reason in pump_actions:
            pump_switch = zone.pump_controller.pump_switch_id
            if action == PumpAction.TURN_ON:
                _LOGGER.info(
                    "Activating pump %s for zone %s (%s)",
                    pump_switch,
                    zone.name,
                    reason,
                )
                await self.hass.services.async_call(
                    "homeassistant",
                    "turn_on",
                    {ATTR_ENTITY_ID: pump_switch},
                    blocking=False,
                )
            elif action == PumpAction.TURN_OFF:
                _LOGGER.info(
                    "Deactivating pump %s for zone %s (%s)",
                    pump_switch,
                    zone.name,
                    reason,
                )
                await self.hass.services.async_call(
                    "homeassistant",
                    "turn_off",
                    {ATTR_ENTITY_ID: pump_switch},
                    blocking=False,
                )

        # Dispatch TRV targets if room target changed, TRVs not synchronized, or overheat dissipation active
        for room in self.system.all_rooms():
            target = room.target_temp
            if self.system.is_buffer_overheat:
                await self.async_sync_room_trvs(room, force_max=True)
            elif prev_targets.get(room.room_id) != target or room.hvac_mode == "off":
                await self.async_sync_room_trvs(room)

        # Notify Home Assistant entity listeners
        self.notify_entity_listeners()

        # Save state immediately to storage
        await self.storage.async_save(self.system)

    async def async_sync_room_trvs(self, room, force_max: bool = False) -> None:
        """Synchronize target temperature and mode to all TRVs configured for the room."""
        for trv_id in room.trv_ids:
            try:
                if force_max:
                    await self.hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {
                            ATTR_ENTITY_ID: trv_id,
                            ATTR_TEMPERATURE: room.max_temp,
                        },
                        blocking=False,
                    )
                    await self.hass.services.async_call(
                        "climate",
                        "set_hvac_mode",
                        {
                            ATTR_ENTITY_ID: trv_id,
                            "hvac_mode": "heat",
                        },
                        blocking=False,
                    )
                elif room.hvac_mode == "off":
                    # Try setting off or minimum frost protection temperature
                    await self.hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {
                            ATTR_ENTITY_ID: trv_id,
                            ATTR_TEMPERATURE: room.min_temp,
                        },
                        blocking=False,
                    )
                else:
                    await self.hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {
                            ATTR_ENTITY_ID: trv_id,
                            ATTR_TEMPERATURE: room.target_temp,
                        },
                        blocking=False,
                    )
            except Exception as err:
                _LOGGER.warning("Failed to synchronize TRV %s: %s", trv_id, err)

    async def async_set_room_temperature(
        self,
        room_id: str,
        target_temp: float,
        mode: OverrideMode = OverrideMode.UNTIL_NEXT_CHANGE,
        duration_minutes: Optional[int] = None,
        preset_name: Optional[str] = None,
    ) -> None:
        """Public API: set room temperature override and trigger evaluation."""
        room = self.system.get_room(room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")

        now_dt = datetime.now()
        day_str = now_dt.strftime("%a").lower()[:3]
        time_str = now_dt.strftime("%H:%M")
        now_ts = time.time()

        room.set_manual_override(
            target=target_temp,
            mode=mode,
            duration_minutes=duration_minutes,
            now=now_ts,
            current_day=day_str,
            current_time=time_str,
            preset_name=preset_name,
        )

        preset_info = f" (preset {preset_name.upper()})" if preset_name else ""
        self.system.event_log.record(
            entity_type="room",
            entity_id=room.room_id,
            entity_name=room.name,
            event_type="manual_override_set",
            message=f"{room.name}: Override manuale a {target_temp}°C{preset_info} (modo: {mode.value})",
            metadata={"target": target_temp, "mode": mode.value, "preset": preset_name},
        )

        await self.async_evaluate()

    async def async_apply_room_preset(
        self, room_id: str, preset_name: str
    ) -> None:
        """Public API: apply room-specific or global preset temperature to room."""
        room = self.system.get_room(room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")

        effective = room.get_effective_presets(self.system.presets)
        preset_clean = preset_name.lower().strip()
        target_temp = effective.get(preset_clean)
        if target_temp is None:
            raise ValueError(
                f"Preset '{preset_name}' non valido per la stanza {room.name}"
            )

        await self.async_set_room_temperature(
            room_id=room_id,
            target_temp=target_temp,
            mode=OverrideMode.UNTIL_NEXT_CHANGE,
            preset_name=preset_clean,
        )

    async def async_boost_room(
        self,
        room_id: str,
        duration_minutes: int = 180,
    ) -> None:
        """Public API: boost room temperature to its maximum setpoint for a given duration (default 3 hours)."""
        room = self.system.get_room(room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")

        await self.async_set_room_temperature(
            room_id=room_id,
            target_temp=room.max_temp,
            mode=OverrideMode.DURATION,
            duration_minutes=duration_minutes,
            preset_name="boost",
        )

    async def async_set_room_presets(
        self, room_id: str, presets: Dict[str, float]
    ) -> None:
        """Public API: update independent preset temperatures for a specific room."""
        room = self.system.get_room(room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")

        for p_name, p_val in presets.items():
            room.set_room_preset(p_name, float(p_val))

        self.system.event_log.record(
            entity_type="room",
            entity_id=room.room_id,
            entity_name=room.name,
            event_type="room_presets_updated",
            message=f"{room.name}: Preset indipendenti salvati ({', '.join(f'{k}={v}°C' for k, v in presets.items())})",
            metadata={"room_id": room_id, "presets": presets},
        )

        await self.async_evaluate()

    async def async_set_zone_pump_manual(
        self, zone_id: str, manual_on: bool
    ) -> None:
        """Public API: toggle circulation pump manual override for a zone."""
        zone = self.system.get_zone(zone_id)
        if not zone:
            raise ValueError(f"Zone {zone_id} not found")

        zone.set_manual_pump_mode(manual_on)
        self.system.event_log.record(
            entity_type="zone",
            entity_id=zone.zone_id,
            entity_name=zone.name,
            event_type="zone_manual_pump_toggled",
            message=f"Zona {zone.name}: Pompa impostata in modalità {'MANUALE ON' if manual_on else 'AUTOMATICA'}",
            metadata={"zone_id": zone_id, "manual_pump_mode": manual_on},
        )

        await self.async_evaluate()

    async def async_set_buffer_settings(
        self,
        sensor_id: Optional[str],
        min_temp: float,
        hysteresis: float,
        overheat_temp: float = DEFAULT_BUFFER_OVERHEAT_TEMP,
        overheat_hysteresis: float = DEFAULT_BUFFER_OVERHEAT_HYSTERESIS,
    ) -> None:
        """Public API: configure thermal storage / puffer temperature settings."""
        self.system.configure_buffer(
            sensor_id=sensor_id,
            min_temp=min_temp,
            hysteresis=hysteresis,
            overheat_temp=overheat_temp,
            overheat_hysteresis=overheat_hysteresis,
        )
        self._rebuild_tracked_entities()
        self._read_initial_states()
        self.system.event_log.record(
            entity_type="system",
            entity_id=self.system.system_id,
            entity_name=self.system.name,
            event_type="buffer_settings_updated",
            message=f"Impostazioni accumulo termico aggiornate: sensore={sensor_id or 'nessuno'}, min={min_temp}°C, isteresi={hysteresis}°C, sovratemp_sicurezza={overheat_temp}°C",
            metadata={
                "sensor": sensor_id,
                "min_temp": min_temp,
                "hysteresis": hysteresis,
                "overheat_temp": overheat_temp,
                "overheat_hysteresis": overheat_hysteresis,
            },
        )
        await self.storage.async_save(self.system)
        if hasattr(self.hass, "config_entries") and hasattr(self.storage, "entry_id"):
            entry = self.hass.config_entries.async_get_entry(self.storage.entry_id)
            if entry:
                self.hass.config_entries.async_update_entry(
                    entry, data=self.system.to_dict()
                )
        await self.async_evaluate()

    async def async_clear_room_override(self, room_id: str) -> None:
        """Public API: clear room manual override and revert to schedule."""
        room = self.system.get_room(room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")

        room.clear_manual_override()
        self.system.event_log.record(
            entity_type="room",
            entity_id=room.room_id,
            entity_name=room.name,
            event_type="manual_override_cleared",
            message=f"{room.name}: Override manuale rimosso, ritorno al programma",
        )
        await self.async_evaluate()

    async def async_set_room_hvac_mode(self, room_id: str, hvac_mode: str) -> None:
        """Public API: set room HVAC mode ('heat' or 'off')."""
        room = self.system.get_room(room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")

        room.hvac_mode = hvac_mode.lower()
        self.system.event_log.record(
            entity_type="room",
            entity_id=room.room_id,
            entity_name=room.name,
            event_type="hvac_mode_changed",
            message=f"{room.name}: Modalità HVAC impostata a {hvac_mode.upper()}",
        )
        await self.async_evaluate()

    async def async_set_global_mode(self, mode: GlobalMode) -> None:
        """Public API: change system-wide heating mode."""
        self.system.set_global_mode(mode)
        await self.async_evaluate()

    async def async_update_room_schedule(
        self, room_id: str, schedule_data: Dict[str, Any]
    ) -> None:
        """Public API: update weekly schedule for a specific room."""
        from .schedule import WeeklySchedule

        room = self.system.get_room(room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")

        room.schedule = WeeklySchedule.from_dict(schedule_data)
        self.system.event_log.record(
            entity_type="room",
            entity_id=room.room_id,
            entity_name=room.name,
            event_type="schedule_updated",
            message=f"{room.name}: Programma orario aggiornato",
        )
        await self.async_evaluate()
