"""HeatingZone domain aggregator and pump manager."""

import time
from typing import Any, Dict, List, Optional, Tuple

from .enums import RoomState, ZoneState
from .pump import PumpAction, PumpController
from .room import HeatingRoom


class HeatingZone:
    """Aggregates heat demand across rooms in a zone and commands the zone circulation pump."""

    def __init__(
        self,
        zone_id: str,
        name: str,
        pump_switch_id: str,
        min_pump_on: int = 120,
        min_pump_off: int = 120,
        startup_delay: int = 15,
        shutdown_delay: int = 30,
    ) -> None:
        """Initialize the heating zone."""
        self.zone_id = zone_id
        self.name = name
        self.rooms: Dict[str, HeatingRoom] = {}
        self.pump_controller = PumpController(
            pump_switch_id=pump_switch_id,
            min_on_time=min_pump_on,
            min_off_time=min_pump_off,
            startup_delay=startup_delay,
            shutdown_delay=shutdown_delay,
        )

        self.heat_demand: bool = False
        self.state: ZoneState = ZoneState.IDLE
        self.active_rooms: List[str] = []
        self.status_reason: str = "Inizializzazione"

    def add_room(self, room: HeatingRoom) -> None:
        """Add a room to this zone."""
        self.rooms[room.room_id] = room

    def remove_room(self, room_id: str) -> Optional[HeatingRoom]:
        """Remove a room from this zone."""
        return self.rooms.pop(room_id, None)

    def evaluate(self, now: Optional[float] = None) -> Tuple[PumpAction, str]:
        """Aggregate room demands, update zone state, and evaluate pump controller.

        Returns:
            Tuple[PumpAction, explanation_reason]
        """
        t = now if now is not None else time.time()

        # 1. Aggregate demand from rooms
        active_room_names = []
        demanding_room_ids = []
        all_rooms_unavailable = bool(self.rooms)

        for room_id, room in self.rooms.items():
            if room.state != RoomState.UNAVAILABLE:
                all_rooms_unavailable = False

            if room.heat_demand:
                demanding_room_ids.append(room_id)
                active_room_names.append(
                    f"{room.name} ({room.current_temp}°C / {room.target_temp}°C)"
                )

        self.active_rooms = demanding_room_ids
        self.heat_demand = len(demanding_room_ids) > 0

        # 2. Update Zone State
        if all_rooms_unavailable:
            self.state = ZoneState.UNAVAILABLE
            self.status_reason = "Tutte le stanze della zona sono non disponibili"
        elif self.heat_demand:
            self.state = ZoneState.HEATING
            self.status_reason = (
                f"Richiesta calore attiva da: {', '.join(active_room_names)}"
            )
        else:
            self.state = ZoneState.IDLE
            self.status_reason = "Nessuna stanza richiede calore"

        # 3. Evaluate Pump
        action, pump_reason = self.pump_controller.evaluate(
            self.heat_demand, now=t
        )
        return (action, pump_reason)

    def get_diagnostic_summary(self) -> Dict[str, Any]:
        """Return clear diagnostic explanation of why zone/pump are in current state."""
        return {
            "zone_id": self.zone_id,
            "zone_name": self.name,
            "zone_state": self.state.value,
            "heat_demand": self.heat_demand,
            "status_reason": self.status_reason,
            "active_rooms": self.active_rooms,
            "active_rooms_count": len(self.active_rooms),
            "total_rooms_count": len(self.rooms),
            "pump": self.pump_controller.to_dict(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize zone configuration and live status."""
        return {
            "zone_id": self.zone_id,
            "name": self.name,
            "pump_switch_id": self.pump_controller.pump_switch_id,
            "min_pump_on": self.pump_controller.min_on_time,
            "min_pump_off": self.pump_controller.min_off_time,
            "startup_delay": self.pump_controller.startup_delay,
            "shutdown_delay": self.pump_controller.shutdown_delay,
            "heat_demand": self.heat_demand,
            "state": self.state.value,
            "active_rooms": self.active_rooms,
            "status_reason": self.status_reason,
            "pump": self.pump_controller.to_dict(),
            "rooms": {r_id: r.to_dict() for r_id, r in self.rooms.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HeatingZone":
        """Instantiate zone from dict (rooms must be attached separately)."""
        return cls(
            zone_id=data["zone_id"],
            name=data["name"],
            pump_switch_id=data["pump_switch_id"],
            min_pump_on=data.get("min_pump_on", 120),
            min_pump_off=data.get("min_pump_off", 120),
            startup_delay=data.get("startup_delay", 15),
            shutdown_delay=data.get("shutdown_delay", 30),
        )
