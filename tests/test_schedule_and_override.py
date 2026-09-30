"""Unit tests for weekly scheduling, presets, and manual overrides."""

import unittest

from custom_components.zoned_thermostat.core.enums import (
    GlobalMode,
    OverrideMode,
)
from custom_components.zoned_thermostat.core.room import HeatingRoom
from custom_components.zoned_thermostat.core.schedule import (
    ScheduleEntry,
    WeeklySchedule,
    minutes_to_time_str,
    parse_time_to_minutes,
)


class TestScheduleAndOverride(unittest.TestCase):
    """Test weekly schedule resolution and override mechanics."""

    def setUp(self):
        self.presets = {
            "comfort": 21.0,
            "eco": 18.0,
            "sleep": 17.0,
            "away": 16.0,
            "frost": 10.0,
        }
        self.schedule = WeeklySchedule()
        # Monday schedule:
        # 06:30 - 08:30 -> comfort (21.0)
        # 08:30 - 17:00 -> eco (18.0)
        # 17:00 - 22:30 -> comfort (21.0)
        # 22:30 - 06:30 -> sleep (17.0)
        self.schedule.set_day_entries(
            "mon",
            [
                ScheduleEntry(start="06:30", end="08:30", preset="comfort"),
                ScheduleEntry(start="08:30", end="17:00", preset="eco"),
                ScheduleEntry(start="17:00", end="22:30", preset="comfort"),
                ScheduleEntry(start="22:30", end="06:30", preset="sleep"),
            ],
        )

    def test_schedule_resolution_times(self):
        """Verify target resolution matches configured intervals."""
        # 07:00 -> comfort (21.0)
        t, preset, _ = self.schedule.resolve_target("mon", "07:00", self.presets)
        self.assertEqual(t, 21.0)
        self.assertEqual(preset, "comfort")

        # 12:00 -> eco (18.0)
        t, preset, _ = self.schedule.resolve_target("mon", "12:00", self.presets)
        self.assertEqual(t, 18.0)
        self.assertEqual(preset, "eco")

        # 20:00 -> comfort (21.0)
        t, preset, _ = self.schedule.resolve_target("mon", "20:00", self.presets)
        self.assertEqual(t, 21.0)
        self.assertEqual(preset, "comfort")

        # 23:00 -> sleep (17.0)
        t, preset, _ = self.schedule.resolve_target("mon", "23:00", self.presets)
        self.assertEqual(t, 17.0)
        self.assertEqual(preset, "sleep")

        # 04:00 (wrap around midnight) -> sleep (17.0)
        t, preset, _ = self.schedule.resolve_target("mon", "04:00", self.presets)
        self.assertEqual(t, 17.0)
        self.assertEqual(preset, "sleep")

    def test_preset_dynamic_inheritance(self):
        """Updating preset value instantly changes resolved target without modifying schedule."""
        self.presets["comfort"] = 21.5
        t, _, _ = self.schedule.resolve_target("mon", "07:00", self.presets)
        self.assertEqual(t, 21.5)

    def test_copy_day_and_week(self):
        """Copying Monday to Tuesday, and then to all week."""
        self.schedule.copy_day("mon", "tue")
        t, preset, _ = self.schedule.resolve_target("tue", "07:00", self.presets)
        self.assertEqual(t, 21.0)
        self.assertEqual(preset, "comfort")

        self.schedule.copy_to_week("mon")
        for d in ["wed", "thu", "fri", "sat", "sun"]:
            t, _, _ = self.schedule.resolve_target(d, "07:00", self.presets)
            self.assertEqual(t, 21.0)

    def test_manual_override_in_room(self):
        """Test manual override behavior and automatic expiration."""
        room = HeatingRoom(
            room_id="sala",
            name="Sala",
            zone_id="pt",
            schedule=self.schedule,
        )

        now = 100000.0
        # Schedule at 07:00 gives 21.0°C
        target = room.evaluate_target(
            "mon", "07:00", self.presets, GlobalMode.HOME, now=now
        )
        self.assertEqual(target, 21.0)
        self.assertIsNone(room.manual_override)

        # Set manual override to 23.0°C for 60 minutes
        room.set_manual_override(
            target=23.0,
            mode=OverrideMode.DURATION,
            duration_minutes=60,
            now=now,
        )
        self.assertIsNotNone(room.manual_override)

        # At now + 30 min (1800s): override still active
        target = room.evaluate_target(
            "mon", "07:30", self.presets, GlobalMode.HOME, now=now + 1800.0
        )
        self.assertEqual(target, 23.0)

        # At now + 61 min (3660s): override expired, reverts to schedule!
        target = room.evaluate_target(
            "mon", "08:00", self.presets, GlobalMode.HOME, now=now + 3660.0
        )
        self.assertEqual(target, 21.0)
        self.assertIsNone(room.manual_override)

    def test_global_mode_overrides_schedule(self):
        """Global AWAY mode forces away temperature regardless of schedule."""
        room = HeatingRoom(
            room_id="sala",
            name="Sala",
            zone_id="pt",
            schedule=self.schedule,
        )
        target = room.evaluate_target("mon", "07:00", self.presets, GlobalMode.AWAY)
        self.assertEqual(target, 16.0)
        self.assertEqual(room.active_preset, "away")


if __name__ == "__main__":
    unittest.main()
