"""HeatingSystem domain model orchestrator."""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Tuple

from ..const import DEFAULT_PRESETS
from .enums import GlobalMode, OverrideMode, RoomState
from .events import EventLogBuffer
from .pump import PumpAction
from .room import HeatingRoom
from .zone import HeatingZone


class HeatingSystem:
    """Central orchestrator for the zoned heating system."""

    def __init__(
        self,
        system_id: str,
        name: str,
        global_mode: GlobalMode = GlobalMode.HOME,
        presets: Optional[Dict[str, float]] = None,
        event_log_size: int = 100,
    ) -> None:
        """Initialize the heating system."""
        self.system_id = system_id
        self.name = name
        self.global_mode = global_mode
        self.presets = presets or dict(DEFAULT_PRESETS)
        self.zones: Dict[str, HeatingZone] = {}
        self.event_log = EventLogBuffer(max_size=event_log_size)

    def add_zone(self, zone: HeatingZone) -> None:
        """Add a heating zone to the system."""
        self.zones[zone.zone_id] = zone

    def get_zone(self, zone_id: str) -> Optional[HeatingZone]:
        """Retrieve zone by ID."""
        return self.zones.get(zone_id)

    def get_room(self, room_id: str) -> Optional[HeatingRoom]:
        """Retrieve room by ID across all zones."""
        for zone in self.zones.values():
            if room_id in zone.rooms:
                return zone.rooms[room_id]
        return None

    def all_rooms(self) -> List[HeatingRoom]:
        """Return a flat list of all rooms."""
        rooms = []
        for zone in self.zones.values():
            rooms.extend(zone.rooms.values())
        return rooms

    @property
    def total_heat_demand(self) -> bool:
        """True if at least one zone demands heat."""
        return any(zone.heat_demand for zone in self.zones.values())

    @property
    def total_active_zones_count(self) -> int:
        """Count of zones currently requesting heat."""
        return sum(1 for zone in self.zones.values() if zone.heat_demand)

    @property
    def total_active_rooms_count(self) -> int:
        """Count of rooms currently requesting heat."""
        return sum(1 for room in self.all_rooms() if room.heat_demand)

    def set_global_mode(self, mode: GlobalMode) -> None:
        """Change the global heating mode and log event."""
        if self.global_mode != mode:
            old_mode = self.global_mode
            self.global_mode = mode
            self.event_log.record(
                entity_type="system",
                entity_id=self.system_id,
                entity_name=self.name,
                event_type="global_mode_changed",
                message=f"Modalità globale cambiata da {old_mode.value.upper()} a {mode.value.upper()}",
                metadata={"old_mode": old_mode.value, "new_mode": mode.value},
            )

    def set_preset(self, preset_name: str, value: float) -> None:
        """Update a global preset temperature value."""
        preset_clean = preset_name.lower().strip()
        val_rounded = round(value, 1)
        old_val = self.presets.get(preset_clean)
        self.presets[preset_clean] = val_rounded
        self.event_log.record(
            entity_type="system",
            entity_id=self.system_id,
            entity_name=self.name,
            event_type="preset_updated",
            message=f"Preset {preset_clean.upper()} aggiornato a {val_rounded}°C (precedente: {old_val}°C)",
            metadata={"preset": preset_clean, "old": old_val, "new": val_rounded},
        )

    def evaluate_tick(
        self,
        day: str,
        time_str: str,
        now: Optional[float] = None,
    ) -> List[Tuple[HeatingZone, PumpAction, str]]:
        """Run a full deterministic evaluation cycle across the entire heating system.

        Steps:
        1. For each room:
           a. Evaluate target (considering global mode, overrides, schedule)
           b. Evaluate heat demand (considering hysteresis, sensor availability, window)
        2. For each zone:
           a. Aggregate room demands
           b. Evaluate pump state machine and required physical action
        3. Record diagnostic events for any state transitions.

        Returns:
            List of (zone, pump_action, reason) for any zone requiring actuator commands.
        """
        t = now if now is not None else time.time()
        pump_instructions: List[Tuple[HeatingZone, PumpAction, str]] = []

        # 1. Rooms evaluation
        for zone in self.zones.values():
            for room in zone.rooms.values():
                prev_demand = room.heat_demand
                prev_state = room.state
                prev_target = room.target_temp

                # Evaluate target
                room.evaluate_target(
                    day=day,
                    time_str=time_str,
                    global_presets=self.presets,
                    global_mode=self.global_mode,
                    now=t,
                )

                # Evaluate demand
                demand, reason, details = room.evaluate_demand(now=t)

                # Log significant room state transitions
                if demand != prev_demand or room.state != prev_state:
                    event_type = (
                        "room_demand_on" if demand else "room_demand_off"
                    )
                    self.event_log.record(
                        entity_type="room",
                        entity_id=room.room_id,
                        entity_name=room.name,
                        event_type=event_type,
                        message=f"{room.name}: {room.status_reason}",
                        metadata={
                            "room_id": room.room_id,
                            "current_temp": room.current_temp,
                            "target_temp": room.target_temp,
                            "state": room.state.value,
                            "heat_demand": room.heat_demand,
                        },
                    )

        # 2. Zones and Pumps evaluation
        for zone in self.zones.values():
            prev_zone_demand = zone.heat_demand
            prev_pump_state = zone.pump_controller.state

            action, pump_reason = zone.evaluate(now=t)

            if zone.heat_demand != prev_zone_demand:
                event_type = (
                    "zone_demand_on" if zone.heat_demand else "zone_demand_off"
                )
                self.event_log.record(
                    entity_type="zone",
                    entity_id=zone.zone_id,
                    entity_name=zone.name,
                    event_type=event_type,
                    message=f"{zone.name}: {zone.status_reason}",
                    metadata={
                        "zone_id": zone.zone_id,
                        "heat_demand": zone.heat_demand,
                        "active_rooms": zone.active_rooms,
                    },
                )

            if zone.pump_controller.state != prev_pump_state or action != PumpAction.NONE:
                self.event_log.record(
                    entity_type="pump",
                    entity_id=zone.pump_controller.pump_switch_id,
                    entity_name=f"Pompa {zone.name}",
                    event_type=f"pump_{action.value}",
                    message=f"Pompa {zone.name}: {pump_reason}",
                    metadata={
                        "action": action.value,
                        "state": zone.pump_controller.state.value,
                        "pump_switch_id": zone.pump_controller.pump_switch_id,
                    },
                )

            if action != PumpAction.NONE:
                pump_instructions.append((zone, action, pump_reason))

        return pump_instructions

    def copy_room_schedule(
        self, source_room_id: str, target_room_id: str
    ) -> None:
        """Copy weekly schedule from one room to another."""
        source = self.get_room(source_room_id)
        target = self.get_room(target_room_id)
        if not source or not target:
            raise ValueError("Stanza sorgente o destinazione non trovata")

        target.schedule = WeeklySchedule.from_dict(source.schedule.to_dict())
        self.event_log.record(
            entity_type="system",
            entity_id=self.system_id,
            entity_name=self.name,
            event_type="schedule_copied",
            message=f"Programma copiato da {source.name} a {target.name}",
            metadata={"source": source_room_id, "target": target_room_id},
        )

    def copy_zone_schedule(
        self, source_zone_id: str, target_zone_id: str
    ) -> None:
        """Apply all room schedules from source zone to matching rooms in target zone or first room."""
        s_zone = self.get_zone(source_zone_id)
        t_zone = self.get_zone(target_zone_id)
        if not s_zone or not t_zone:
            raise ValueError("Zona sorgente o destinazione non trovata")

        s_rooms = list(s_zone.rooms.values())
        if not s_rooms:
            raise ValueError("La zona sorgente non contiene stanze")

        master_schedule = s_rooms[0].schedule
        for t_room in t_zone.rooms.values():
            t_room.schedule = WeeklySchedule.from_dict(master_schedule.to_dict())

        self.event_log.record(
            entity_type="system",
            entity_id=self.system_id,
            entity_name=self.name,
            event_type="zone_schedule_copied",
            message=f"Programma zona applicato da {s_zone.name} a tutte le stanze di {t_zone.name}",
            metadata={"source": source_zone_id, "target": target_zone_id},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize complete heating system state."""
        return {
            "system_id": self.system_id,
            "name": self.name,
            "global_mode": self.global_mode.value,
            "presets": self.presets,
            "total_heat_demand": self.total_heat_demand,
            "total_active_zones_count": self.total_active_zones_count,
            "total_active_rooms_count": self.total_active_rooms_count,
            "zones": {z_id: z.to_dict() for z_id, z in self.zones.items()},
            "recent_events": self.event_log.get_events(limit=20),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HeatingSystem":
        """Reconstruct complete HeatingSystem from dictionary."""
        sys = cls(
            system_id=data["system_id"],
            name=data["name"],
            global_mode=GlobalMode(data.get("global_mode", GlobalMode.HOME.value)),
            presets=data.get("presets", dict(DEFAULT_PRESETS)),
        )

        for z_id, z_data in data.get("zones", {}).items():
            zone = HeatingZone.from_dict(z_data)
            for r_id, r_data in z_data.get("rooms", {}).items():
                room = HeatingRoom.from_dict(r_data)
                zone.add_room(room)
            sys.add_zone(zone)

        return sys
