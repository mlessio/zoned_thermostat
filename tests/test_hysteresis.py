"""Unit tests for the hysteresis heat demand algorithm."""

import unittest

from custom_components.zoned_thermostat.core.hysteresis import calculate_heat_demand


class TestHysteresis(unittest.TestCase):
    """Test deterministic hysteresis calculation."""

    def test_demand_starts_at_or_below_on_threshold(self):
        """Target 21.0, Hysteresis 0.2 -> On threshold is 20.8°C."""
        # 20.9 is above threshold: no demand
        demand, reason, details = calculate_heat_demand(
            current_temp=20.9, target_temp=21.0, hysteresis=0.2, previous_demand=False
        )
        self.assertFalse(demand)
        self.assertEqual(details["on_threshold"], 20.8)
        self.assertEqual(details["off_threshold"], 21.2)

        # 20.8 is equal to threshold: demand starts
        demand, reason, _ = calculate_heat_demand(
            current_temp=20.8, target_temp=21.0, hysteresis=0.2, previous_demand=False
        )
        self.assertTrue(demand)

        # 20.5 is well below threshold: demand starts
        demand, reason, _ = calculate_heat_demand(
            current_temp=20.5, target_temp=21.0, hysteresis=0.2, previous_demand=False
        )
        self.assertTrue(demand)

    def test_deadband_retains_previous_state(self):
        """In range (20.8, 21.2), state is retained."""
        # Previous demand was False, temp is 21.0 -> stays False
        demand, _, _ = calculate_heat_demand(
            current_temp=21.0, target_temp=21.0, hysteresis=0.2, previous_demand=False
        )
        self.assertFalse(demand)

        # Previous demand was True, temp rises to 21.0 -> stays True (still heating)
        demand, _, _ = calculate_heat_demand(
            current_temp=21.0, target_temp=21.0, hysteresis=0.2, previous_demand=True
        )
        self.assertTrue(demand)

    def test_demand_stops_at_or_above_off_threshold(self):
        """Target 21.0, Hysteresis 0.2 -> Off threshold is 21.2°C."""
        # 21.1: still in deadband, previous demand was True -> stays True
        demand, _, _ = calculate_heat_demand(
            current_temp=21.1, target_temp=21.0, hysteresis=0.2, previous_demand=True
        )
        self.assertTrue(demand)

        # 21.2: reached off threshold -> stops demand
        demand, reason, _ = calculate_heat_demand(
            current_temp=21.2, target_temp=21.0, hysteresis=0.2, previous_demand=True
        )
        self.assertFalse(demand)

        # 21.5: above threshold -> stays False
        demand, _, _ = calculate_heat_demand(
            current_temp=21.5, target_temp=21.0, hysteresis=0.2, previous_demand=False
        )
        self.assertFalse(demand)

    def test_unavailable_sensor_fails_safe(self):
        """If sensor is None (offline/unavailable), demand must be False."""
        demand, reason, details = calculate_heat_demand(
            current_temp=None, target_temp=21.0, hysteresis=0.2, previous_demand=True
        )
        self.assertFalse(demand)
        self.assertEqual(reason, "sensor_unavailable")


if __name__ == "__main__":
    unittest.main()
