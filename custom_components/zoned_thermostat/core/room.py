"""HeatingRoom domain controller."""

from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional, Tuple

from .enums import GlobalMode, OverrideMode, PresetMode, RoomState, SensorAggregation
from .hysteresis import calculate_heat_demand
from .schedule import (
    DAYS_OF_WEEK,
    ManualOverride,
    WeeklySchedule,
    parse_time_to_minutes,
)


class HeatingRoom:
    """Manages an individual heating room with temperature sensing, scheduling, and heat demand calculation."""

    def __init__(
        self,
        room_id: str,
        name: str,
        zone_id: str,
        temp_sensor_ids: Optional[List[str]] = None,
        trv_ids: Optional[List[str]] = None,
        sensor_aggregation: SensorAggregation = SensorAggregation.PRIMARY_ONLY,
        window_sensor_id: Optional[str] = None,
        window_delay: int = 15,
        presence_sensor_id: Optional[str] = None,
        min_temp: float = 10.0,
        max_temp: float = 28.0,
        temp_step: float = 0.5,
        hysteresis: float = 0.2,
        schedule: Optional[WeeklySchedule] = None,
        presets_override: Optional[Dict[str, float]] = None,
    ) -> None:
        """Initialize the heating room."""
        self.room_id = room_id
        self.name = name
        self.zone_id = zone_id
        self.temp_sensor_ids: List[str] = temp_sensor_ids or []
        self.trv_ids: List[str] = trv_ids or []
        self.sensor_aggregation = sensor_aggregation
        self.window_sensor_id = window_sensor_id
        self.window_delay = window_delay
        self.presence_sensor_id = presence_sensor_id
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.temp_step = temp_step
        self.hysteresis = hysteresis
        self.schedule: WeeklySchedule = schedule or WeeklySchedule.create_default()
        self.presets_override: Dict[str, float] = presets_override or {}

        # Runtime states
        self.sensor_readings: Dict[str, Optional[float]] = {
            s: None for s in self.temp_sensor_ids
        }
        self.current_temp: Optional[float] = None
        self.target_temp: float = 21.0
        self.active_preset: Optional[str] = "comfort"
        self.heat_demand: bool = False
        self.state: RoomState = RoomState.IDLE
        self.hvac_mode: str = "heat"  # "heat" or "off"

        # Interlocks
        self.is_window_open: bool = False
        self.window_open_timestamp: Optional[float] = None
        self.is_presence_detected: Optional[bool] = None

        # Manual Override
        self.manual_override: Optional[ManualOverride] = None

        # TRV states tracking (for UI display and diagnostics)
        self.trv_states: Dict[str, Dict[str, Any]] = {
            trv: {"target": None, "current": None, "valve": None, "hvac_mode": None}
            for trv in self.trv_ids
        }

        # Human diagnostic reasoning
        self.status_reason: str = "Inizializzazione"

    def update_sensor_temperature(
        self, sensor_id: str, temperature: Optional[float]
    ) -> bool:
        """Update temperature for a given sensor and recompute aggregated room temperature.

        Returns True if the aggregated room temperature changed.
        """
        self.sensor_readings[sensor_id] = temperature
        old_agg = self.current_temp
        self.current_temp = self._calculate_aggregated_temperature()
        return old_agg != self.current_temp

    def _calculate_aggregated_temperature(self) -> Optional[float]:
        """Aggregate readings based on selected strategy."""
        valid_readings = [
            t for t in self.sensor_readings.values() if t is not None
        ]
        if not valid_readings:
            return None

        if (
            self.sensor_aggregation == SensorAggregation.PRIMARY_ONLY
            or len(valid_readings) == 1
        ):
            # First configured sensor is primary
            primary_id = self.temp_sensor_ids[0] if self.temp_sensor_ids else None
            if primary_id and self.sensor_readings.get(primary_id) is not None:
                return round(self.sensor_readings[primary_id], 1)
            return round(valid_readings[0], 1)

        if self.sensor_aggregation == SensorAggregation.AVERAGE:
            return round(sum(valid_readings) / len(valid_readings), 1)
        if self.sensor_aggregation == SensorAggregation.MINIMUM:
            return round(min(valid_readings), 1)
        if self.sensor_aggregation == SensorAggregation.MAXIMUM:
            return round(max(valid_readings), 1)

        return round(valid_readings[0], 1)

    def update_window_state(
        self, is_open: bool, now: Optional[float] = None
    ) -> None:
        """Update window open/closed status."""
        t = now if now is not None else time.time()
        self.is_window_open = is_open
        if is_open:
            if self.window_open_timestamp is None:
                self.window_open_timestamp = t
        else:
            self.window_open_timestamp = None

    def update_presence_state(self, is_detected: bool) -> None:
        """Update room presence detection status."""
        self.is_presence_detected = is_detected

    def update_trv_state(
        self,
        trv_id: str,
        current_temp: Optional[float] = None,
        target_temp: Optional[float] = None,
        valve_position: Optional[int] = None,
        hvac_mode: Optional[str] = None,
    ) -> None:
        """Update state metadata of an associated TRV."""
        if trv_id not in self.trv_states:
            self.trv_states[trv_id] = {}
        if current_temp is not None:
            self.trv_states[trv_id]["current"] = current_temp
        if target_temp is not None:
            self.trv_states[trv_id]["target"] = target_temp
        if valve_position is not None:
            self.trv_states[trv_id]["valve"] = valve_position
        if hvac_mode is not None:
            self.trv_states[trv_id]["hvac_mode"] = hvac_mode

    def set_manual_override(
        self,
        target: float,
        mode: OverrideMode = OverrideMode.UNTIL_NEXT_CHANGE,
        duration_minutes: Optional[int] = None,
        now: Optional[float] = None,
        current_day: Optional[str] = None,
        current_time: Optional[str] = None,
    ) -> None:
        """Set a manual temperature override on the room."""
        t = now if now is not None else time.time()
        target_clamped = max(self.min_temp, min(self.max_temp, round(target, 1)))

        expires_at = None
        if mode == OverrideMode.DURATION and duration_minutes:
            expires_at = t + (duration_minutes * 60)

        block_end_min = None
        if mode == OverrideMode.UNTIL_NEXT_CHANGE and current_day and current_time:
            block = self.schedule.get_current_block(current_day, current_time)
            if block:
                block_end_min = parse_time_to_minutes(block.end)

        self.manual_override = ManualOverride(
            target_temp=target_clamped,
            mode=mode,
            set_timestamp=t,
            duration_minutes=duration_minutes,
            expires_at_timestamp=expires_at,
            set_block_end_minutes=block_end_min,
        )

    def clear_manual_override(self) -> None:
        """Cancel any active manual override and return to schedule."""
        self.manual_override = None

    def evaluate_target(
        self,
        day: str,
        time_str: str,
        global_presets: Dict[str, float],
        global_mode: GlobalMode,
        now: Optional[float] = None,
    ) -> float:
        """Determine target temperature by checking global mode, manual overrides, and schedule.

        Order of priority:
        1. GlobalMode: OFF (frost/safety 10°C), FROST (preset frost), AWAY (preset away)
        2. Active Manual Override (if valid and not expired)
        3. Weekly Schedule + Presets
        """
        t = now if now is not None else time.time()
        presets = {**global_presets, **self.presets_override}

        # 1. Global Mode Overrides
        if global_mode == GlobalMode.OFF:
            self.target_temp = presets.get("frost", self.min_temp)
            self.active_preset = "frost"
            return self.target_temp

        if global_mode == GlobalMode.FROST:
            self.target_temp = presets.get("frost", 10.0)
            self.active_preset = "frost"
            return self.target_temp

        if global_mode == GlobalMode.AWAY or global_mode == GlobalMode.VACATION:
            self.target_temp = presets.get("away", 16.0)
            self.active_preset = "away"
            return self.target_temp

        # 2. Manual Override
        if self.manual_override is not None:
            curr_minutes = parse_time_to_minutes(time_str)
            if self.manual_override.is_expired(t, curr_minutes):
                self.manual_override = None
            else:
                self.target_temp = self.manual_override.target_temp
                self.active_preset = None
                return self.target_temp

        # 3. Schedule
        resolved_temp, preset_name, _ = self.schedule.resolve_target(
            day=day,
            time_str=time_str,
            presets=presets,
            fallback_temp=self.min_temp,
        )
        self.target_temp = resolved_temp
        self.active_preset = preset_name
        return self.target_temp

    def evaluate_demand(
        self, now: Optional[float] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Evaluate room heat demand deterministically using hysteresis and interlocks.

        Returns:
            Tuple[demand_active, reason_string, details_dict]
        """
        t = now if now is not None else time.time()

        # Check HVAC Mode
        if self.hvac_mode == "off":
            self.heat_demand = False
            self.state = RoomState.OFF
            self.status_reason = "Stanza spenta (HVAC mode OFF)"
            return (
                False,
                self.status_reason,
                {"hvac_mode": "off", "current_temp": self.current_temp},
            )

        # Check Window Sensor with delay
        if self.is_window_open:
            elapsed_open = (
                t - self.window_open_timestamp
                if self.window_open_timestamp
                else 0
            )
            if elapsed_open >= self.window_delay:
                self.heat_demand = False
                self.state = RoomState.WINDOW_OPEN
                self.status_reason = f"Finestra aperta da {int(elapsed_open)}s"
                return (
                    False,
                    self.status_reason,
                    {"window_open": True, "elapsed": elapsed_open},
                )

        # Check Temperature Availability
        if self.current_temp is None:
            self.heat_demand = False
            self.state = RoomState.UNAVAILABLE
            self.status_reason = "Sensore temperatura non disponibile"
            return (
                False,
                self.status_reason,
                {"current_temp": None, "target": self.target_temp},
            )

        # Evaluate Hysteresis
        demand, reason, details = calculate_heat_demand(
            current_temp=self.current_temp,
            target_temp=self.target_temp,
            hysteresis=self.hysteresis,
            previous_demand=self.heat_demand,
        )

        self.heat_demand = demand
        if demand:
            self.state = RoomState.HEATING
            self.status_reason = (
                f"Richiesta calore attiva: {self.current_temp}°C <= {details['on_threshold']}°C"
            )
        else:
            if self.current_temp >= details["off_threshold"]:
                self.state = RoomState.TARGET_REACHED
                self.status_reason = (
                    f"Target raggiunto: {self.current_temp}°C >= {details['off_threshold']}°C"
                )
            else:
                self.state = RoomState.IDLE
                self.status_reason = (
                    f"A riposo: {self.current_temp}°C (target {self.target_temp}°C)"
                )

        if self.manual_override is not None:
            self.status_reason += " [Override manuale]"

        return (demand, self.status_reason, details)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize room for persistence and UI."""
        return {
            "room_id": self.room_id,
            "name": self.name,
            "zone_id": self.zone_id,
            "temp_sensor_ids": self.temp_sensor_ids,
            "trv_ids": self.trv_ids,
            "sensor_aggregation": self.sensor_aggregation.value,
            "window_sensor_id": self.window_sensor_id,
            "window_delay": self.window_delay,
            "presence_sensor_id": self.presence_sensor_id,
            "min_temp": self.min_temp,
            "max_temp": self.max_temp,
            "temp_step": self.temp_step,
            "hysteresis": self.hysteresis,
            "presets_override": self.presets_override,
            "schedule": self.schedule.to_dict(),
            "manual_override": (
                self.manual_override.to_dict() if self.manual_override else None
            ),
            # Live runtime fields
            "current_temp": self.current_temp,
            "target_temp": self.target_temp,
            "active_preset": self.active_preset,
            "heat_demand": self.heat_demand,
            "state": self.state.value,
            "hvac_mode": self.hvac_mode,
            "is_window_open": self.is_window_open,
            "status_reason": self.status_reason,
            "trv_states": self.trv_states,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HeatingRoom":
        """Instantiate room from dictionary."""
        sched_data = data.get("schedule")
        schedule = (
            WeeklySchedule.from_dict(sched_data)
            if sched_data
            else WeeklySchedule.create_default()
        )

        room = cls(
            room_id=data["room_id"],
            name=data["name"],
            zone_id=data["zone_id"],
            temp_sensor_ids=data.get("temp_sensor_ids", []),
            trv_ids=data.get("trv_ids", []),
            sensor_aggregation=SensorAggregation(
                data.get("sensor_aggregation", SensorAggregation.PRIMARY_ONLY.value)
            ),
            window_sensor_id=data.get("window_sensor_id"),
            window_delay=data.get("window_delay", 15),
            presence_sensor_id=data.get("presence_sensor_id"),
            min_temp=float(data.get("min_temp", 10.0)),
            max_temp=float(data.get("max_temp", 28.0)),
            temp_step=float(data.get("temp_step", 0.5)),
            hysteresis=float(data.get("hysteresis", 0.2)),
            schedule=schedule,
            presets_override=data.get("presets_override", {}),
        )

        if data.get("manual_override"):
            room.manual_override = ManualOverride.from_dict(
                data["manual_override"]
            )
        room.hvac_mode = data.get("hvac_mode", "heat")
        return room
