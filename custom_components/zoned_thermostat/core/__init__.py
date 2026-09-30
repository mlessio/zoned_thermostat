"""Core domain models and algorithms for Zoned Heating Thermostat."""

from .enums import (
    GlobalMode,
    OverrideMode,
    PresetMode,
    PumpState,
    RoomState,
    SensorAggregation,
    ZoneState,
)
from .events import DiagnosticEvent, EventLogBuffer
from .hysteresis import calculate_heat_demand
from .pump import PumpAction, PumpController
from .room import HeatingRoom
from .schedule import (
    DAYS_OF_WEEK,
    ManualOverride,
    ScheduleEntry,
    WeeklySchedule,
    minutes_to_time_str,
    parse_time_to_minutes,
)
from .system import HeatingSystem
from .zone import HeatingZone

__all__ = [
    "GlobalMode",
    "RoomState",
    "ZoneState",
    "PumpState",
    "OverrideMode",
    "SensorAggregation",
    "PresetMode",
    "DiagnosticEvent",
    "EventLogBuffer",
    "calculate_heat_demand",
    "PumpAction",
    "PumpController",
    "HeatingRoom",
    "ScheduleEntry",
    "ManualOverride",
    "WeeklySchedule",
    "DAYS_OF_WEEK",
    "parse_time_to_minutes",
    "minutes_to_time_str",
    "HeatingZone",
    "HeatingSystem",
]
