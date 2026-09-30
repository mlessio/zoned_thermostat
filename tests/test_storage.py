"""Unit tests for storage serialization and boot recovery."""

import asyncio
import unittest

from custom_components.zoned_thermostat.core.enums import (
    GlobalMode,
    OverrideMode,
    SensorAggregation,
)
from custom_components.zoned_thermostat.core.room import HeatingRoom
from custom_components.zoned_thermostat.core.storage import (
    ZonedThermostatStorage,
)
from custom_components.zoned_thermostat.core.system import HeatingSystem
from custom_components.zoned_thermostat.core.zone import HeatingZone


class TestStorage(unittest.TestCase):
    """Test full system serialization roundtrip through storage."""

    def test_serialization_roundtrip(self):
        """Serialize a full 2-zone system and reconstruct it identically."""
        sys = HeatingSystem(
            system_id="system_123",
            name="Villa Termica",
            global_mode=GlobalMode.HOME,
            presets={"comfort": 21.5, "eco": 18.5, "frost": 10.0},
        )

        zone_pt = HeatingZone(
            zone_id="pt",
            name="Piano Terra",
            pump_switch_id="switch.pompa_pt",
            min_pump_on=150,
            min_pump_off=150,
            startup_delay=20,
            shutdown_delay=40,
        )

        room_cucina = HeatingRoom(
            room_id="cucina",
            name="Cucina",
            zone_id="pt",
            temp_sensor_ids=["sensor.cucina_temp"],
            trv_ids=["climate.trv_cucina_1", "climate.trv_cucina_2"],
            sensor_aggregation=SensorAggregation.PRIMARY_ONLY,
            window_sensor_id="binary_sensor.finestra_cucina",
            window_delay=25,
            hysteresis=0.3,
        )
        room_cucina.set_manual_override(22.5, mode=OverrideMode.DURATION, duration_minutes=90)
        zone_pt.add_room(room_cucina)
        sys.add_zone(zone_pt)

        # Use storage manager in mock/in-memory mode
        storage = ZonedThermostatStorage(hass=None, entry_id="test_entry")

        async def _test():
            await storage.async_save(sys)
            restored_sys = await storage.async_load()
            return restored_sys

        restored_sys = asyncio.run(_test())

        self.assertIsNotNone(restored_sys)
        self.assertEqual(restored_sys.system_id, "system_123")
        self.assertEqual(restored_sys.name, "Villa Termica")
        self.assertEqual(restored_sys.global_mode, GlobalMode.HOME)
        self.assertEqual(restored_sys.presets["comfort"], 21.5)

        restored_zone = restored_sys.get_zone("pt")
        self.assertIsNotNone(restored_zone)
        self.assertEqual(restored_zone.name, "Piano Terra")
        self.assertEqual(restored_zone.pump_controller.pump_switch_id, "switch.pompa_pt")
        self.assertEqual(restored_zone.pump_controller.min_on_time, 150)
        self.assertEqual(restored_zone.pump_controller.startup_delay, 20)

        restored_room = restored_sys.get_room("cucina")
        self.assertIsNotNone(restored_room)
        self.assertEqual(restored_room.name, "Cucina")
        self.assertEqual(restored_room.trv_ids, ["climate.trv_cucina_1", "climate.trv_cucina_2"])
        self.assertEqual(restored_room.window_sensor_id, "binary_sensor.finestra_cucina")
        self.assertEqual(restored_room.window_delay, 25)
        self.assertEqual(restored_room.hysteresis, 0.3)
        self.assertIsNotNone(restored_room.manual_override)
        self.assertEqual(restored_room.manual_override.target_temp, 22.5)


if __name__ == "__main__":
    unittest.main()
