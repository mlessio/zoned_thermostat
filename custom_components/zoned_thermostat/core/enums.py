"""Enumerations for the Zoned Heating Thermostat domain model."""

from enum import Enum


class StrEnum(str, Enum):
    """String enum for serialization compatibility."""

    def __str__(self) -> str:
        return self.value


class GlobalMode(StrEnum):
    """Global heating system mode."""

    HOME = "home"
    AWAY = "away"
    FROST = "frost"
    OFF = "off"
    VACATION = "vacation"


class RoomState(StrEnum):
    """Operating state of a heating room."""

    IDLE = "idle"
    HEATING = "heating"
    TARGET_REACHED = "target_reached"
    OFF = "off"
    AWAY = "away"
    FROST = "frost"
    WINDOW_OPEN = "window_open"
    UNAVAILABLE = "unavailable"
    MANUAL_OVERRIDE = "manual_override"


class ZoneState(StrEnum):
    """Operating state of a heating zone."""

    IDLE = "idle"
    HEATING = "heating"
    OFF = "off"
    UNAVAILABLE = "unavailable"


class PumpState(StrEnum):
    """Physical and logical state of a circulation pump."""

    OFF = "off"
    STARTING = "starting"
    ON = "on"
    STOPPING = "stopping"
    UNAVAILABLE = "unavailable"


class OverrideMode(StrEnum):
    """Expiration policy for manual temperature overrides."""

    UNTIL_NEXT_CHANGE = "until_next_change"
    DURATION = "duration"
    PERMANENT = "permanent"


class SensorAggregation(StrEnum):
    """Strategy to aggregate readings from multiple temperature sensors."""

    PRIMARY_ONLY = "primary_only"
    AVERAGE = "average"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"


class PresetMode(StrEnum):
    """Standard heating presets."""

    NONE = "none"
    COMFORT = "comfort"
    ECO = "eco"
    SLEEP = "sleep"
    AWAY = "away"
    FROST = "frost"
