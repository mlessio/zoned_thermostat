"""Unit test verifying the real multi-floor domestic heating scenario.

Scenario (Specification #42):
PIANO TERRA:
- Sala:   target 21.0°C, current 21.5°C -> demand = OFF
- Cucina: target 21.0°C, current 20.5°C -> demand = ON  (20.5 <= 20.8)
- Bunker: target 20.0°C, current 20.4°C -> demand = OFF

Result:
- Piano Terra demand = ON
- Pompa PT = ON (after startup delay)

PIANO PRIMO:
- Camera:           target 20.0°C, current 21.0°C -> demand = OFF
- Camera padronale: target 21.0°C, current 21.3°C -> demand = OFF

Result:
- Piano Primo demand = OFF
- Pompa P1 = OFF

SUBSEQUENT TRANSITION:
- Cucina reaches 21.2°C (target 21.0°C + hysteresis 0.2°C)

Result:
- Cucina demand = OFF
- Piano Terra demand = OFF
- Pompa PT = OFF (after min_on and shutdown delay)
"""

import unittest

from custom_components.zoned_thermostat.core.enums import (
    GlobalMode,
    OverrideMode,
    PumpState,
    RoomState,
    ZoneState,
)
from custom_components.zoned_thermostat.core.pump import PumpAction
from custom_components.zoned_thermostat.core.room import HeatingRoom
from custom_components.zoned_thermostat.core.system import HeatingSystem
from custom_components.zoned_thermostat.core.zone import HeatingZone


class TestRealScenario(unittest.TestCase):
    """Execution of the realistic two-floor multi-room system test."""

    def setUp(self):
        self.system = HeatingSystem(
            system_id="impianto_casa",
            name="Riscaldamento Casa",
            presets={"comfort": 21.0, "eco": 18.0, "sleep": 17.0, "bunker": 20.0},
        )

        # -------------------------------------------------------------
        # PIANO TERRA
        # -------------------------------------------------------------
        self.zone_pt = HeatingZone(
            zone_id="piano_terra",
            name="Piano Terra",
            pump_switch_id="switch.pompa_pt",
            min_pump_on=120,
            min_pump_off=120,
            startup_delay=15,
            shutdown_delay=30,
        )

        self.sala = HeatingRoom(
            room_id="sala",
            name="Sala",
            zone_id="piano_terra",
            temp_sensor_ids=["sensor.sala_temperature"],
            trv_ids=["climate.trv_sala_1", "climate.trv_sala_2"],
            hysteresis=0.2,
        )
        self.cucina = HeatingRoom(
            room_id="cucina",
            name="Cucina",
            zone_id="piano_terra",
            temp_sensor_ids=["sensor.cucina_temperature"],
            trv_ids=["climate.trv_cucina"],
            hysteresis=0.2,
        )
        self.bunker = HeatingRoom(
            room_id="bunker",
            name="Bunker",
            zone_id="piano_terra",
            temp_sensor_ids=["sensor.bunker_temperature"],
            trv_ids=["climate.trv_bunker"],
            hysteresis=0.2,
        )

        self.zone_pt.add_room(self.sala)
        self.zone_pt.add_room(self.cucina)
        self.zone_pt.add_room(self.bunker)
        self.system.add_zone(self.zone_pt)

        # -------------------------------------------------------------
        # PIANO PRIMO
        # -------------------------------------------------------------
        self.zone_p1 = HeatingZone(
            zone_id="piano_primo",
            name="Piano Primo",
            pump_switch_id="switch.pompa_p1",
            min_pump_on=120,
            min_pump_off=120,
            startup_delay=15,
            shutdown_delay=30,
        )

        self.camera = HeatingRoom(
            room_id="camera",
            name="Camera",
            zone_id="piano_primo",
            temp_sensor_ids=["sensor.camera_temperature"],
            trv_ids=["climate.trv_camera"],
            hysteresis=0.2,
        )
        self.padronale = HeatingRoom(
            room_id="camera_padronale",
            name="Camera Padronale",
            zone_id="piano_primo",
            temp_sensor_ids=["sensor.padronale_temperature"],
            trv_ids=["climate.trv_padronale"],
            hysteresis=0.2,
        )

        self.zone_p1.add_room(self.camera)
        self.zone_p1.add_room(self.padronale)
        self.system.add_zone(self.zone_p1)

    def test_complete_real_cycle(self):
        """Execute the exact sequence described in requirement 42."""
        t0 = 1000.0

        # Set targets via manual override so evaluate_tick respects them:
        # Sala: 21.0°C, current 21.5°C
        self.sala.set_manual_override(21.0, mode=OverrideMode.PERMANENT)
        self.sala.update_sensor_temperature("sensor.sala_temperature", 21.5)

        # Cucina: 21.0°C, current 20.5°C
        self.cucina.set_manual_override(21.0, mode=OverrideMode.PERMANENT)
        self.cucina.update_sensor_temperature("sensor.cucina_temperature", 20.5)

        # Bunker: 20.0°C, current 20.4°C
        self.bunker.set_manual_override(20.0, mode=OverrideMode.PERMANENT)
        self.bunker.update_sensor_temperature("sensor.bunker_temperature", 20.4)

        # Camera: 20.0°C, current 21.0°C
        self.camera.set_manual_override(20.0, mode=OverrideMode.PERMANENT)
        self.camera.update_sensor_temperature("sensor.camera_temperature", 21.0)

        # Padronale: 21.0°C, current 21.3°C
        self.padronale.set_manual_override(21.0, mode=OverrideMode.PERMANENT)
        self.padronale.update_sensor_temperature("sensor.padronale_temperature", 21.3)

        # -------------------------------------------------------------
        # STEP 1: INITIAL TICK EVALUATION
        # -------------------------------------------------------------
        # Run system tick at t0
        self.system.evaluate_tick("mon", "10:00", now=t0)

        # Verify Room Demands:
        self.assertFalse(self.sala.heat_demand, "Sala must NOT demand heat (21.5 >= 20.8)")
        self.assertTrue(self.cucina.heat_demand, "Cucina MUST demand heat (20.5 <= 20.8)")
        self.assertFalse(self.bunker.heat_demand, "Bunker must NOT demand heat (20.4 >= 19.8)")

        self.assertFalse(self.camera.heat_demand, "Camera must NOT demand heat (21.0 >= 19.8)")
        self.assertFalse(self.padronale.heat_demand, "Padronale must NOT demand heat (21.3 >= 20.8)")

        # Verify Zone Demands:
        self.assertTrue(self.zone_pt.heat_demand, "Piano Terra demand MUST be ON")
        self.assertIn("cucina", self.zone_pt.active_rooms)
        self.assertEqual(len(self.zone_pt.active_rooms), 1)

        self.assertFalse(self.zone_p1.heat_demand, "Piano Primo demand MUST be OFF")
        self.assertEqual(len(self.zone_p1.active_rooms), 0)

        # Verify Pump PT entered STARTING (startup delay 15s)
        self.assertEqual(self.zone_pt.pump_controller.state, PumpState.STARTING)
        self.assertEqual(self.zone_p1.pump_controller.state, PumpState.OFF)

        # -------------------------------------------------------------
        # STEP 2: ELAPSE STARTUP DELAY (15s)
        # -------------------------------------------------------------
        t1 = t0 + 15.0
        instructions = self.system.evaluate_tick("mon", "10:00", now=t1)

        # Pump PT should now produce TURN_ON action and enter state ON
        pt_instructions = [
            (z, act, reason) for z, act, reason in instructions if z.zone_id == "piano_terra"
        ]
        self.assertEqual(len(pt_instructions), 1)
        self.assertEqual(pt_instructions[0][1], PumpAction.TURN_ON)
        self.assertEqual(self.zone_pt.pump_controller.state, PumpState.ON)

        # Pump P1 remains OFF
        self.assertEqual(self.zone_p1.pump_controller.state, PumpState.OFF)

        # Diagnostic summary check:
        diag = self.zone_pt.get_diagnostic_summary()
        self.assertTrue(diag["heat_demand"])
        self.assertEqual(diag["active_rooms"], ["cucina"])
        self.assertIn("Cucina", diag["status_reason"])

        # -------------------------------------------------------------
        # STEP 3: CUCINA HEATS UP TO 21.2°C (OFF threshold reached)
        # -------------------------------------------------------------
        # Advance time by 200s (satisfying min_on_time of 120s)
        t2 = t1 + 200.0
        self.cucina.update_sensor_temperature("sensor.cucina_temperature", 21.2)

        self.system.evaluate_tick("mon", "10:03", now=t2)

        # Cucina demand should now turn OFF
        self.assertFalse(self.cucina.heat_demand, "Cucina demand must turn OFF at 21.2°C")
        self.assertEqual(self.cucina.state, RoomState.TARGET_REACHED)

        # Zone PT demand turns OFF
        self.assertFalse(self.zone_pt.heat_demand, "Piano Terra demand must turn OFF")
        self.assertEqual(len(self.zone_pt.active_rooms), 0)

        # Pump PT enters STOPPING (shutdown delay 30s)
        self.assertEqual(self.zone_pt.pump_controller.state, PumpState.STOPPING)

        # -------------------------------------------------------------
        # STEP 4: ELAPSE SHUTDOWN DELAY (30s)
        # -------------------------------------------------------------
        t3 = t2 + 30.0
        instructions_stop = self.system.evaluate_tick("mon", "10:04", now=t3)

        pt_stop = [
            (z, act, reason) for z, act, reason in instructions_stop if z.zone_id == "piano_terra"
        ]
        self.assertEqual(len(pt_stop), 1)
        self.assertEqual(pt_stop[0][1], PumpAction.TURN_OFF)
        self.assertEqual(self.zone_pt.pump_controller.state, PumpState.OFF)
        self.assertFalse(self.zone_pt.pump_controller.is_physically_on)

        # Event log check:
        events = self.system.event_log.get_events()
        self.assertGreater(len(events), 0)
        # Ensure Cucina, Piano Terra and Pump transitions were all recorded
        logged_entities = {e["entity_name"] for e in events}
        self.assertIn("Cucina", logged_entities)
        self.assertIn("Piano Terra", logged_entities)
        self.assertIn("Pompa Piano Terra", logged_entities)


if __name__ == "__main__":
    unittest.main()
