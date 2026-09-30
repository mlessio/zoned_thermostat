"""Unit tests for the pump controller with anti-short-cycle protections."""

import unittest

from custom_components.zoned_thermostat.core.enums import PumpState
from custom_components.zoned_thermostat.core.pump import PumpAction, PumpController


class TestPumpController(unittest.TestCase):
    """Test pump controller transitions, delays, and min on/off constraints."""

    def setUp(self):
        """Set up pump with known timings: 100s min on, 100s min off, 10s startup, 20s shutdown."""
        self.pump = PumpController(
            pump_switch_id="switch.pompa_pt",
            min_on_time=100,
            min_off_time=100,
            startup_delay=10,
            shutdown_delay=20,
        )

    def test_startup_delay(self):
        """Demand activates -> pump enters STARTING -> turns ON after startup_delay."""
        t0 = 1000.0

        # At t0: demand ON -> enters STARTING, action NONE
        action, reason = self.pump.evaluate(zone_demands_heat=True, now=t0)
        self.assertEqual(action, PumpAction.NONE)
        self.assertEqual(self.pump.state, PumpState.STARTING)

        # At t0 + 5s (less than startup_delay of 10s): still STARTING
        action, reason = self.pump.evaluate(zone_demands_heat=True, now=t0 + 5.0)
        self.assertEqual(action, PumpAction.NONE)
        self.assertEqual(self.pump.state, PumpState.STARTING)

        # At t0 + 10s: startup delay elapsed -> action TURN_ON, state ON
        action, reason = self.pump.evaluate(zone_demands_heat=True, now=t0 + 10.0)
        self.assertEqual(action, PumpAction.TURN_ON)
        self.assertEqual(self.pump.state, PumpState.ON)
        self.assertTrue(self.pump.is_physically_on)

    def test_min_on_time_protection(self):
        """Demand drops before min_on_time has elapsed -> pump stays ON / STOPPING without turning off immediately."""
        t0 = 1000.0
        # Turn pump ON at t0 + 10s
        self.pump.evaluate(zone_demands_heat=True, now=t0)
        self.pump.evaluate(zone_demands_heat=True, now=t0 + 10.0)
        self.assertEqual(self.pump.state, PumpState.ON)

        # At t0 + 50s (only 40s elapsed since turn_on, min_on_time is 100s): demand goes OFF
        action, reason = self.pump.evaluate(zone_demands_heat=False, now=t0 + 50.0)
        self.assertEqual(action, PumpAction.NONE)
        self.assertEqual(self.pump.state, PumpState.STOPPING)
        self.assertTrue(self.pump.is_physically_on)
        self.assertIn("Protezione tempo minimo di accensione", reason)

        # At t0 + 109s (99s elapsed since turn_on): still protected
        action, _ = self.pump.evaluate(zone_demands_heat=False, now=t0 + 109.0)
        self.assertEqual(action, PumpAction.NONE)
        self.assertTrue(self.pump.is_physically_on)

        # At t0 + 111s (101s elapsed): min_on_time is satisfied, now shutdown_delay (20s) begins!
        action, reason = self.pump.evaluate(zone_demands_heat=False, now=t0 + 111.0)
        self.assertEqual(action, PumpAction.NONE)
        self.assertEqual(self.pump.state, PumpState.STOPPING)
        self.assertIn("Post-circolazione in corso", reason)

        # At t0 + 132s (21s after shutdown began): shutdown delay elapsed -> action TURN_OFF
        action, reason = self.pump.evaluate(zone_demands_heat=False, now=t0 + 132.0)
        self.assertEqual(action, PumpAction.TURN_OFF)
        self.assertEqual(self.pump.state, PumpState.OFF)
        self.assertFalse(self.pump.is_physically_on)

    def test_min_off_time_protection(self):
        """After turning OFF, pump cannot turn ON immediately until min_off_time elapses."""
        t0 = 1000.0
        # Turn ON
        self.pump.evaluate(zone_demands_heat=True, now=t0)
        self.pump.evaluate(zone_demands_heat=True, now=t0 + 10.0)
        # Turn OFF at t0 + 140s
        self.pump.evaluate(zone_demands_heat=False, now=t0 + 120.0)
        self.pump.evaluate(zone_demands_heat=False, now=t0 + 141.0)
        self.assertFalse(self.pump.is_physically_on)
        self.assertEqual(self.pump.last_turn_off_time, t0 + 141.0)

        # New demand arrives at t0 + 160s (only 19s after turn_off, min_off_time is 100s)
        action, reason = self.pump.evaluate(zone_demands_heat=True, now=t0 + 160.0)
        self.assertEqual(action, PumpAction.NONE)
        self.assertEqual(self.pump.state, PumpState.STARTING)
        self.assertIn("Attesa tempo minimo di spegnimento", reason)

        # At t0 + 242s (101s after turn_off): min_off_time satisfied -> now startup delay starts
        action, reason = self.pump.evaluate(zone_demands_heat=True, now=t0 + 242.0)
        self.assertEqual(action, PumpAction.NONE)
        self.assertIn("startup delay", reason)

        # At t0 + 253s (11s after startup requested): turns ON
        action, reason = self.pump.evaluate(zone_demands_heat=True, now=t0 + 253.0)
        self.assertEqual(action, PumpAction.TURN_ON)
        self.assertTrue(self.pump.is_physically_on)


if __name__ == "__main__":
    unittest.main()
