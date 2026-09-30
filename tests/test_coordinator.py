"""Unit tests for the ZonedThermostatCoordinator evaluation loop and fail-safes."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.zoned_thermostat.coordinator import (
    ZonedThermostatCoordinator,
)
from custom_components.zoned_thermostat.core.enums import (
    GlobalMode,
    OverrideMode,
    PumpState,
    RoomState,
)
from custom_components.zoned_thermostat.core.pump import PumpAction
from custom_components.zoned_thermostat.core.room import HeatingRoom
from custom_components.zoned_thermostat.core.storage import (
    ZonedThermostatStorage,
)
from custom_components.zoned_thermostat.core.system import HeatingSystem
from custom_components.zoned_thermostat.core.zone import HeatingZone


class TestCoordinator(unittest.TestCase):
    """Test coordinator state routing, evaluation, service calls, and safety fail-safes."""

    def setUp(self):
        self.hass = MagicMock()
        self.hass.services.async_call = AsyncMock()
        self.hass.states.get = MagicMock(return_value=None)

        self.sys = HeatingSystem(
            system_id="sys1",
            name="Impianto Test",
            presets={"comfort": 21.0, "eco": 18.0, "sleep": 17.0, "frost": 10.0},
        )

        self.zone_pt = HeatingZone(
            zone_id="pt",
            name="Piano Terra",
            pump_switch_id="switch.pompa_pt",
            min_pump_on=60,
            min_pump_off=60,
            startup_delay=10,
            shutdown_delay=15,
        )

        self.cucina = HeatingRoom(
            room_id="cucina",
            name="Cucina",
            zone_id="pt",
            temp_sensor_ids=["sensor.cucina_temp"],
            trv_ids=["climate.trv_cucina"],
            hysteresis=0.2,
        )
        self.zone_pt.add_room(self.cucina)
        self.sys.add_zone(self.zone_pt)

        self.storage = ZonedThermostatStorage(hass=None, entry_id="test_entry")
        self.coordinator = ZonedThermostatCoordinator(
            self.hass, self.sys, self.storage
        )

    def test_state_processing_unavailable_sensor(self):
        """When temperature sensor becomes unavailable, room must switch to UNAVAILABLE and cancel demand."""
        # 1. Initially at 20.0°C (target 21.0°C) -> demand True
        self.cucina.update_sensor_temperature("sensor.cucina_temp", 20.0)
        self.cucina.evaluate_demand()
        self.assertTrue(self.cucina.heat_demand)

        # 2. Sensor reports "unavailable"
        self.coordinator._process_state("sensor.cucina_temp", "unavailable", {})
        self.assertIsNone(self.cucina.current_temp)

        self.cucina.evaluate_demand()
        self.assertFalse(self.cucina.heat_demand)
        self.assertEqual(self.cucina.state, RoomState.UNAVAILABLE)

    def test_state_processing_pump_switch(self):
        """Pump switch reports physical ON/OFF state from Home Assistant."""
        self.coordinator._process_state("switch.pompa_pt", "on", {})
        self.assertTrue(self.zone_pt.pump_controller.is_physically_on)
        self.assertEqual(self.zone_pt.pump_controller.state, PumpState.ON)

        self.coordinator._process_state("switch.pompa_pt", "off", {})
        self.assertFalse(self.zone_pt.pump_controller.is_physically_on)
        self.assertEqual(self.zone_pt.pump_controller.state, PumpState.OFF)

    def test_manual_override_api(self):
        """Coordinator set_room_temperature creates override and dispatches update."""
        asyncio.run(
            self.coordinator.async_set_room_temperature(
                room_id="cucina",
                target_temp=22.5,
                mode=OverrideMode.DURATION,
                duration_minutes=45,
            )
        )

        self.assertIsNotNone(self.cucina.manual_override)
        self.assertEqual(self.cucina.target_temp, 22.5)
        self.assertEqual(self.cucina.manual_override.mode, OverrideMode.DURATION)

        # Clear override
        asyncio.run(self.coordinator.async_clear_room_override("cucina"))
        self.assertIsNone(self.cucina.manual_override)

    def test_global_mode_change_api(self):
        """Changing global mode updates system and evaluates target."""
        asyncio.run(self.coordinator.async_set_global_mode(GlobalMode.AWAY))
        self.assertEqual(self.sys.global_mode, GlobalMode.AWAY)
        self.assertEqual(self.cucina.target_temp, 16.0)

    def test_hvac_mode_off_api(self):
        """Setting room HVAC mode to OFF halts demand immediately."""
        self.cucina.update_sensor_temperature("sensor.cucina_temp", 19.0)
        self.cucina.evaluate_demand()
        self.assertTrue(self.cucina.heat_demand)

        asyncio.run(self.coordinator.async_set_room_hvac_mode("cucina", "off"))
        self.assertEqual(self.cucina.hvac_mode, "off")
        self.assertFalse(self.cucina.heat_demand)
        self.assertEqual(self.cucina.state, RoomState.OFF)


if __name__ == "__main__":
    unittest.main()
