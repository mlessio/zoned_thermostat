"""Unit tests for the 5 heating control enhancements:
1. Independent per-room presets (Comfort/Eco/etc.)
2. Manual pump override for each zone
3. Thermal storage / buffer tank (puffer) interlock with asymmetric hysteresis
4. WebSocket commands for new features
5. Effective presets calculation and serialization
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from custom_components.zoned_thermostat.const import DOMAIN
from custom_components.zoned_thermostat.coordinator import ZonedThermostatCoordinator
from custom_components.zoned_thermostat.core.enums import GlobalMode, OverrideMode, RoomState
from custom_components.zoned_thermostat.core.pump import PumpAction
from custom_components.zoned_thermostat.core.room import HeatingRoom
from custom_components.zoned_thermostat.core.system import HeatingSystem
from custom_components.zoned_thermostat.core.zone import HeatingZone
from custom_components.zoned_thermostat.websocket import (
    ws_apply_room_preset,
    ws_set_buffer_settings,
    ws_set_room_presets,
    ws_set_zone_pump_manual,
)


class TestEnhancedHeatingFeatures(unittest.TestCase):
    """Test suite for new heating enhancements."""

    def setUp(self):
        """Set up a system with 2 zones, 2 rooms, and pump switches."""
        self.system = HeatingSystem(system_id="sys1", name="Impianto Casa")

        # Zone 1
        self.zone1 = HeatingZone(
            zone_id="zona_giorno",
            name="Zona Giorno",
            pump_switch_id="switch.pompa_giorno",
            min_pump_on=0,
            min_pump_off=0,
            startup_delay=0,
            shutdown_delay=0,
        )
        self.room_cucina = HeatingRoom(
            room_id="cucina",
            name="Cucina",
            zone_id="zona_giorno",
            temp_sensor_ids=["sensor.cucina_temp"],
            presets_override={"comfort": 21.5, "eco": 18.5},
        )
        self.zone1.add_room(self.room_cucina)
        self.system.add_zone(self.zone1)

        # Zone 2
        self.zone2 = HeatingZone(
            zone_id="zona_notte",
            name="Zona Notte",
            pump_switch_id="switch.pompa_notte",
            min_pump_on=0,
            min_pump_off=0,
            startup_delay=0,
            shutdown_delay=0,
        )
        self.room_camera = HeatingRoom(
            room_id="camera",
            name="Camera",
            zone_id="zona_notte",
            temp_sensor_ids=["sensor.camera_temp"],
            presets_override={"comfort": 19.0, "eco": 16.5},
        )
        self.zone2.add_room(self.room_camera)
        self.system.add_zone(self.zone2)

        # Coordinator with mock storage and hass
        self.mock_hass = MagicMock()
        self.mock_hass.services.async_call = AsyncMock()
        self.mock_storage = MagicMock()
        self.mock_storage.async_save = AsyncMock()

        self.coordinator = ZonedThermostatCoordinator(
            hass=self.mock_hass,
            system=self.system,
            storage=self.mock_storage,
        )

    def test_independent_per_room_presets(self):
        """Verify each room has independent presets and effective presets."""
        cucina_eff = self.room_cucina.get_effective_presets(self.system.presets)
        camera_eff = self.room_camera.get_effective_presets(self.system.presets)

        self.assertEqual(cucina_eff["comfort"], 21.5)
        self.assertEqual(cucina_eff["eco"], 18.5)
        self.assertEqual(camera_eff["comfort"], 19.0)
        self.assertEqual(camera_eff["eco"], 16.5)

        # Serialization includes effective_presets
        c_dict = self.room_cucina.to_dict(self.system.presets)
        self.assertIn("effective_presets", c_dict)
        self.assertEqual(c_dict["effective_presets"]["comfort"], 21.5)

        # Apply preset comfort to cucina
        asyncio.run(self.coordinator.async_apply_room_preset("cucina", "comfort"))
        self.assertEqual(self.room_cucina.target_temp, 21.5)
        self.assertEqual(self.room_cucina.active_preset, "comfort")

        # Apply preset comfort to camera
        asyncio.run(self.coordinator.async_apply_room_preset("camera", "comfort"))
        self.assertEqual(self.room_camera.target_temp, 19.0)
        self.assertEqual(self.room_camera.active_preset, "comfort")

        # Update room presets via coordinator API
        asyncio.run(
            self.coordinator.async_set_room_presets(
                "cucina", {"comfort": 22.0, "eco": 19.0}
            )
        )
        self.assertEqual(self.room_cucina.presets_override["comfort"], 22.0)
        asyncio.run(self.coordinator.async_apply_room_preset("cucina", "comfort"))
        self.assertEqual(self.room_cucina.target_temp, 22.0)

    def test_manual_zone_pump_override(self):
        """Verify zone circulation pump can be manually forced ON regardless of temperature."""
        now = 1000.0

        # Initially: rooms are satisfied (no heat demand)
        self.room_cucina.update_sensor_temperature("sensor.cucina_temp", 22.0)
        self.room_cucina.target_temp = 20.0
        self.room_cucina.evaluate_demand(now=now)
        self.assertFalse(self.room_cucina.heat_demand)

        # Evaluate tick -> pump stays OFF
        actions = self.system.evaluate_tick("mon", "12:00", now=now)
        self.assertFalse(self.zone1.pump_controller.is_physically_on)

        # Enable manual pump override on Zone 1
        asyncio.run(self.coordinator.async_set_zone_pump_manual("zona_giorno", True))
        self.assertTrue(self.zone1.manual_pump_mode)

        # Evaluate tick: pump MUST be commanded TURN_ON
        actions = self.system.evaluate_tick("mon", "12:00", now=now + 5)
        self.assertIn("manualmente", self.zone1.status_reason.lower())

        # Disable manual pump override
        asyncio.run(self.coordinator.async_set_zone_pump_manual("zona_giorno", False))
        self.assertFalse(self.zone1.manual_pump_mode)

        # Evaluate tick: pump should turn OFF because room demand is False
        actions = self.system.evaluate_tick("mon", "12:00", now=now + 10)
        self.assertFalse(self.zone1.pump_controller.is_physically_on)

    def test_buffer_tank_interlock_logic(self):
        """Verify thermal storage / buffer tank interlock with asymmetric hysteresis."""
        # Configure buffer tank: min_temp = 45.0°C, hysteresis = 2.0°C (cutoff at 43.0°C)
        self.system.configure_buffer(
            sensor_id="sensor.accumulo_temp", min_temp=45.0, hysteresis=2.0
        )
        self.assertFalse(self.system.is_buffer_ready)

        # Room cucina demands heat (18°C < 21°C target)
        now = 2000.0
        self.room_cucina.target_temp = 21.0
        self.room_cucina.update_sensor_temperature("sensor.cucina_temp", 18.0)
        self.room_cucina.evaluate_demand(now=now)
        self.assertTrue(self.room_cucina.heat_demand)

        # Buffer is at 40°C (< 45°C) -> NOT READY
        self.system.update_buffer_temperature(40.0)
        self.assertFalse(self.system.is_buffer_ready)

        # Run evaluate tick -> Pump must NOT start!
        actions = self.system.evaluate_tick("mon", "12:00", now=now)
        self.assertFalse(self.zone1.pump_controller.is_physically_on)
        self.assertIn("accumulo", self.zone1.status_reason.lower())

        # Buffer heats up to 45.0°C -> BECOMES READY!
        self.system.update_buffer_temperature(45.0)
        self.assertTrue(self.system.is_buffer_ready)

        # Run evaluate tick -> Pump MUST TURN ON!
        actions = self.system.evaluate_tick("mon", "12:00", now=now + 5)
        self.assertTrue(self.zone1.pump_controller.is_physically_on)

        # Buffer cools down slightly to 43.5°C (above cutoff 43.0°C) -> STILL READY
        self.system.update_buffer_temperature(43.5)
        self.assertTrue(self.system.is_buffer_ready)
        actions = self.system.evaluate_tick("mon", "12:00", now=now + 10)
        self.assertTrue(self.zone1.pump_controller.is_physically_on)

        # Buffer cools down to 42.5°C (< 43.0°C cutoff) -> BECOMES NOT READY!
        self.system.update_buffer_temperature(42.5)
        self.assertFalse(self.system.is_buffer_ready)

        # Run evaluate tick -> Pump MUST STOP to wait for heat reserve!
        actions = self.system.evaluate_tick("mon", "12:00", now=now + 15)
        self.assertFalse(self.zone1.pump_controller.is_physically_on)

    def test_buffer_interlock_bypassed_by_manual_pump(self):
        """Verify manual pump override forces pump on even if buffer tank is cold."""
        self.system.configure_buffer(
            sensor_id="sensor.accumulo_temp", min_temp=50.0, hysteresis=3.0
        )
        self.system.update_buffer_temperature(30.0)
        self.assertFalse(self.system.is_buffer_ready)

        now = 3000.0
        # Normal room demand with cold buffer does not start pump
        self.room_cucina.target_temp = 21.0
        self.room_cucina.update_sensor_temperature("sensor.cucina_temp", 18.0)
        self.system.evaluate_tick("mon", "12:00", now=now)
        self.assertFalse(self.zone1.pump_controller.is_physically_on)

        # Enable manual pump mode
        self.zone1.set_manual_pump_mode(True)
        self.system.evaluate_tick("mon", "12:00", now=now + 2)
        self.assertTrue(self.zone1.pump_controller.is_physically_on)

    def test_websocket_commands(self):
        """Test WebSocket command handlers for the new features."""
        mock_conn = MagicMock()
        mock_conn.send_result = MagicMock()
        mock_conn.send_error = MagicMock()

        self.mock_hass.data = {
            DOMAIN: {
                "test_entry": {
                    "coordinator": self.coordinator,
                    "system": self.system,
                }
            }
        }

        # 1. apply_room_preset
        msg = {
            "id": 1,
            "type": "zoned_thermostat/apply_room_preset",
            "room_id": "cucina",
            "preset": "comfort",
            "entry_id": "test_entry",
        }
        asyncio.run(ws_apply_room_preset(self.mock_hass, mock_conn, msg))
        mock_conn.send_result.assert_called_with(1, {"success": True})
        self.assertEqual(self.room_cucina.target_temp, 21.5)

        # 2. set_room_presets
        msg2 = {
            "id": 2,
            "type": "zoned_thermostat/set_room_presets",
            "room_id": "cucina",
            "presets": {"comfort": 23.0, "eco": 19.5},
            "entry_id": "test_entry",
        }
        asyncio.run(ws_set_room_presets(self.mock_hass, mock_conn, msg2))
        mock_conn.send_result.assert_called_with(2, {"success": True})
        self.assertEqual(self.room_cucina.presets_override["comfort"], 23.0)

        # 3. set_zone_pump_manual
        msg3 = {
            "id": 3,
            "type": "zoned_thermostat/set_zone_pump_manual",
            "zone_id": "zona_giorno",
            "manual_on": True,
            "entry_id": "test_entry",
        }
        asyncio.run(ws_set_zone_pump_manual(self.mock_hass, mock_conn, msg3))
        mock_conn.send_result.assert_called_with(3, {"success": True})
        self.assertTrue(self.zone1.manual_pump_mode)

        # 4. set_buffer_settings
        msg4 = {
            "id": 4,
            "type": "zoned_thermostat/set_buffer_settings",
            "sensor_id": "sensor.puffer_high",
            "min_temp": 48.0,
            "hysteresis": 2.5,
            "entry_id": "test_entry",
        }
        asyncio.run(ws_set_buffer_settings(self.mock_hass, mock_conn, msg4))
        mock_conn.send_result.assert_called_with(4, {"success": True})
        self.assertEqual(self.system.buffer_temp_sensor, "sensor.puffer_high")
        self.assertEqual(self.system.buffer_min_temp, 48.0)
        self.assertEqual(self.system.buffer_temp_hysteresis, 2.5)


if __name__ == "__main__":
    unittest.main()
