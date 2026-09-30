"""Unit tests for room sensor aggregation and window/presence interlocks."""

import unittest

from custom_components.zoned_thermostat.core.enums import (
    RoomState,
    SensorAggregation,
)
from custom_components.zoned_thermostat.core.room import HeatingRoom


class TestRoomInterlocks(unittest.TestCase):
    """Test multi-sensor aggregation strategies and window sensor behavior."""

    def test_multi_sensor_average(self):
        """Average aggregation across multiple temperature sensors."""
        room = HeatingRoom(
            room_id="sala",
            name="Sala",
            zone_id="pt",
            temp_sensor_ids=["sensor.sala_1", "sensor.sala_2", "sensor.sala_3"],
            sensor_aggregation=SensorAggregation.AVERAGE,
        )

        room.update_sensor_temperature("sensor.sala_1", 20.0)
        room.update_sensor_temperature("sensor.sala_2", 21.0)
        room.update_sensor_temperature("sensor.sala_3", 22.0)

        # Average: (20 + 21 + 22) / 3 = 21.0
        self.assertEqual(room.current_temp, 21.0)

    def test_multi_sensor_min_max(self):
        """Minimum and Maximum aggregation strategies."""
        room_min = HeatingRoom(
            room_id="sala_min",
            name="Sala Min",
            zone_id="pt",
            temp_sensor_ids=["sensor.sala_1", "sensor.sala_2"],
            sensor_aggregation=SensorAggregation.MINIMUM,
        )
        room_min.update_sensor_temperature("sensor.sala_1", 19.5)
        room_min.update_sensor_temperature("sensor.sala_2", 21.0)
        self.assertEqual(room_min.current_temp, 19.5)

        room_max = HeatingRoom(
            room_id="sala_max",
            name="Sala Max",
            zone_id="pt",
            temp_sensor_ids=["sensor.sala_1", "sensor.sala_2"],
            sensor_aggregation=SensorAggregation.MAXIMUM,
        )
        room_max.update_sensor_temperature("sensor.sala_1", 19.5)
        room_max.update_sensor_temperature("sensor.sala_2", 21.0)
        self.assertEqual(room_max.current_temp, 21.0)

    def test_window_sensor_interlock(self):
        """Window open interlock suspends heat demand after window_delay."""
        room = HeatingRoom(
            room_id="cucina",
            name="Cucina",
            zone_id="pt",
            temp_sensor_ids=["sensor.cucina_temp"],
            window_sensor_id="binary_sensor.finestra_cucina",
            window_delay=10,  # 10s delay
            hysteresis=0.2,
        )
        room.target_temp = 21.0
        room.update_sensor_temperature("sensor.cucina_temp", 20.0)

        t0 = 1000.0
        demand, reason, _ = room.evaluate_demand(now=t0)
        self.assertTrue(demand)
        self.assertEqual(room.state, RoomState.HEATING)

        # Window opens at t0 + 2.0s
        room.update_window_state(is_open=True, now=t0 + 2.0)

        # At t0 + 5.0s (3s after open, delay is 10s): still heating
        demand, _, _ = room.evaluate_demand(now=t0 + 5.0)
        self.assertTrue(demand)

        # At t0 + 13.0s (11s after open, delay elapsed): demand must drop to False!
        demand, reason, _ = room.evaluate_demand(now=t0 + 13.0)
        self.assertFalse(demand)
        self.assertEqual(room.state, RoomState.WINDOW_OPEN)
        self.assertIn("Finestra aperta", reason)

        # Window closes at t0 + 20.0s
        room.update_window_state(is_open=False, now=t0 + 20.0)

        # Normal demand resumes!
        demand, reason, _ = room.evaluate_demand(now=t0 + 21.0)
        self.assertTrue(demand)
        self.assertEqual(room.state, RoomState.HEATING)


if __name__ == "__main__":
    unittest.main()
