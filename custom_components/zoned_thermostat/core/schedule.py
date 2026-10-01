"""Weekly schedule and manual override models."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Tuple

from .enums import OverrideMode

DAYS_OF_WEEK = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def parse_time_to_minutes(time_str: str) -> int:
    """Parse 'HH:MM' string into minutes from midnight (0..1439)."""
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {time_str}. Expected 'HH:MM'")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Time out of range: {time_str}")
    return h * 60 + m


def minutes_to_time_str(minutes: int) -> str:
    """Format minutes from midnight into 'HH:MM' string."""
    m_clamped = minutes % 1440
    h = m_clamped // 60
    m = m_clamped % 60
    return f"{h:02d}:{m:02d}"


@dataclass
class ScheduleEntry:
    """A single time window with a target temperature or preset."""

    start: str  # "HH:MM"
    end: str  # "HH:MM"
    preset: Optional[str] = None  # "comfort", "eco", etc.
    target_temp: Optional[float] = None  # Explicit temperature override if not using preset

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary."""
        return {
            "start": self.start,
            "end": self.end,
            "preset": self.preset,
            "target_temp": self.target_temp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduleEntry":
        """Instantiate entry from dictionary."""
        return cls(
            start=data["start"],
            end=data["end"],
            preset=data.get("preset"),
            target_temp=(
                float(data["target_temp"])
                if data.get("target_temp") is not None
                else None
            ),
        )

    def contains(self, minutes_from_midnight: int) -> bool:
        """Check if minutes_from_midnight falls in [start, end)."""
        s = parse_time_to_minutes(self.start)
        e = parse_time_to_minutes(self.end)
        if s <= e:
            return s <= minutes_from_midnight < e
        # Handles wrap-around midnight if any (e.g. 22:30 -> 06:30)
        return minutes_from_midnight >= s or minutes_from_midnight < e


@dataclass
class ManualOverride:
    """Represents a temporary or permanent manual temperature change."""

    target_temp: float
    mode: OverrideMode
    set_timestamp: float = field(default_factory=time.time)
    duration_minutes: Optional[int] = None
    expires_at_timestamp: Optional[float] = None
    set_block_end_minutes: Optional[int] = None  # End minutes of the block active when set
    preset_name: Optional[str] = None

    def is_expired(
        self, now_timestamp: float, current_minutes_from_midnight: int
    ) -> bool:
        """Check whether this manual override has expired."""
        if self.mode == OverrideMode.PERMANENT:
            return False

        if self.mode == OverrideMode.DURATION:
            if self.expires_at_timestamp is not None:
                return now_timestamp >= self.expires_at_timestamp
            if self.duration_minutes is not None:
                return now_timestamp >= (
                    self.set_timestamp + self.duration_minutes * 60
                )
            return False

        if self.mode == OverrideMode.UNTIL_NEXT_CHANGE:
            if self.set_block_end_minutes is not None:
                # If current minutes reached or passed the block end
                # (accounting for day rollover)
                if current_minutes_from_midnight >= self.set_block_end_minutes:
                    return True
            return False

        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert override to dict."""
        return {
            "target_temp": self.target_temp,
            "mode": self.mode.value,
            "set_timestamp": self.set_timestamp,
            "duration_minutes": self.duration_minutes,
            "expires_at_timestamp": self.expires_at_timestamp,
            "set_block_end_minutes": self.set_block_end_minutes,
            "preset_name": self.preset_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManualOverride":
        """Instantiate override from dict."""
        return cls(
            target_temp=float(data["target_temp"]),
            mode=OverrideMode(data["mode"]),
            set_timestamp=float(data.get("set_timestamp", time.time())),
            duration_minutes=data.get("duration_minutes"),
            expires_at_timestamp=data.get("expires_at_timestamp"),
            set_block_end_minutes=data.get("set_block_end_minutes"),
            preset_name=data.get("preset_name"),
        )


class WeeklySchedule:
    """7-day schedule with helper methods to resolve target and clone intervals."""

    def __init__(
        self, days: Optional[Dict[str, List[ScheduleEntry]]] = None
    ) -> None:
        """Initialize the weekly schedule."""
        self.days: Dict[str, List[ScheduleEntry]] = {}
        for d in DAYS_OF_WEEK:
            self.days[d] = []

        if days:
            for day, entries in days.items():
                if day in self.days:
                    self.days[day] = sorted(
                        entries, key=lambda e: parse_time_to_minutes(e.start)
                    )

    @classmethod
    def create_default(cls) -> "WeeklySchedule":
        """Create a standard default schedule (Comfort in morning/evening, Eco midday/night)."""
        sched = cls()
        default_entries = [
            ScheduleEntry(start="06:30", end="08:30", preset="comfort"),
            ScheduleEntry(start="08:30", end="17:00", preset="eco"),
            ScheduleEntry(start="17:00", end="22:30", preset="comfort"),
            ScheduleEntry(start="22:30", end="06:30", preset="sleep"),
        ]
        for day in DAYS_OF_WEEK:
            sched.days[day] = [
                ScheduleEntry(
                    start=e.start,
                    end=e.end,
                    preset=e.preset,
                    target_temp=e.target_temp,
                )
                for e in default_entries
            ]
        return sched

    def resolve_target(
        self,
        day: str,
        time_str: str,
        presets: Dict[str, float],
        fallback_temp: float = 18.0,
    ) -> Tuple[float, Optional[str], Optional[ScheduleEntry]]:
        """Resolve effective target temperature for a given day and time.

        Returns:
            Tuple[resolved_temperature, active_preset_name, matching_entry]
        """
        day_key = day.lower()[:3]
        if day_key not in self.days:
            day_key = "mon"

        minutes = parse_time_to_minutes(time_str)
        day_entries = self.days.get(day_key, [])

        for entry in day_entries:
            if entry.contains(minutes):
                if entry.preset and entry.preset in presets:
                    return (presets[entry.preset], entry.preset, entry)
                if entry.target_temp is not None:
                    return (entry.target_temp, entry.preset, entry)

        # Fallback if no interval matched
        eco_fallback = presets.get("eco", fallback_temp)
        return (eco_fallback, "eco", None)

    def get_current_block(
        self, day: str, time_str: str
    ) -> Optional[ScheduleEntry]:
        """Return the ScheduleEntry active right now, if any."""
        day_key = day.lower()[:3]
        minutes = parse_time_to_minutes(time_str)
        for entry in self.days.get(day_key, []):
            if entry.contains(minutes):
                return entry
        return None

    def copy_day(self, from_day: str, to_day: str) -> None:
        """Copy all entries from one day to another."""
        f = from_day.lower()[:3]
        t = to_day.lower()[:3]
        if f not in self.days or t not in self.days:
            raise ValueError(f"Invalid day: from={from_day}, to={to_day}")

        self.days[t] = [
            ScheduleEntry(
                start=e.start,
                end=e.end,
                preset=e.preset,
                target_temp=e.target_temp,
            )
            for e in self.days[f]
        ]

    def copy_to_week(self, from_day: str) -> None:
        """Copy a single day schedule to all other days of the week."""
        f = from_day.lower()[:3]
        if f not in self.days:
            raise ValueError(f"Invalid day: {from_day}")

        for d in DAYS_OF_WEEK:
            if d != f:
                self.copy_day(f, d)

    def set_day_entries(self, day: str, entries: List[ScheduleEntry]) -> None:
        """Set and sort entries for a specific day."""
        d = day.lower()[:3]
        if d not in self.days:
            raise ValueError(f"Invalid day: {day}")
        self.days[d] = sorted(
            entries, key=lambda e: parse_time_to_minutes(e.start)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize weekly schedule to dictionary."""
        return {
            day: [entry.to_dict() for entry in entries]
            for day, entries in self.days.items()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeeklySchedule":
        """Deserialize weekly schedule from dictionary."""
        days: Dict[str, List[ScheduleEntry]] = {}
        for day, entries_data in data.items():
            days[day] = [
                ScheduleEntry.from_dict(entry_dict)
                for entry_dict in entries_data
            ]
        return cls(days=days)
