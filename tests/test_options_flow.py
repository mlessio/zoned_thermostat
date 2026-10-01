"""Unit tests for ZonedThermostatOptionsFlow modifications and inspection."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from custom_components.zoned_thermostat.config_flow import (
    ZonedThermostatOptionsFlow,
)
from custom_components.zoned_thermostat.const import DOMAIN
from custom_components.zoned_thermostat.core.enums import GlobalMode
from custom_components.zoned_thermostat.core.room import HeatingRoom
from custom_components.zoned_thermostat.core.storage import (
    ZonedThermostatStorage,
)
from custom_components.zoned_thermostat.core.system import HeatingSystem
from custom_components.zoned_thermostat.core.zone import HeatingZone


class TestOptionsFlow(unittest.TestCase):
    """Test dynamic reconfiguration through Options Flow."""

    def setUp(self):
        self.hass = MagicMock()
        self.hass.config_entries.async_reload = AsyncMock()
        self.hass.config_entries.async_update_entry = MagicMock()

        self.sys = HeatingSystem(
            system_id="sys1",
            name="Casa Test",
            global_mode=GlobalMode.HOME,
        )
        self.zone_pt = HeatingZone(
            zone_id="pt",
            name="Piano Terra",
            pump_switch_id="switch.pompa_pt",
        )
        self.sala = HeatingRoom(
            room_id="sala",
            name="Sala",
            zone_id="pt",
            temp_sensor_ids=["sensor.sala_temp_old"],
            trv_ids=["climate.trv_sala_old"],
            hysteresis=0.2,
        )
        self.zone_pt.add_room(self.sala)
        self.sys.add_zone(self.zone_pt)

        self.entry = MagicMock()
        self.entry.entry_id = "test_entry_id"
        self.entry.data = self.sys.to_dict()
        self.entry.options = {}

        self.storage = ZonedThermostatStorage(hass=None, entry_id="test_entry_id")
        self.coordinator = MagicMock()
        self.coordinator.system = self.sys
        self.coordinator.storage = self.storage
        self.coordinator._rebuild_tracked_entities = MagicMock()
        self.coordinator._read_initial_states = MagicMock()
        self.coordinator.async_evaluate = AsyncMock()

        self.hass.data = {
            DOMAIN: {
                "test_entry_id": {
                    "system": self.sys,
                    "coordinator": self.coordinator,
                    "storage": self.storage,
                }
            }
        }

        self.flow = ZonedThermostatOptionsFlow(self.entry)
        self.flow.hass = self.hass

    def test_view_config(self):
        """View config step displays formatted summary with entities."""
        res = asyncio.run(self.flow.async_step_view_config())
        self.assertEqual(res["type"], "form")
        self.assertEqual(res["step_id"], "view_config")
        summary = res["description_placeholders"]["summary"]
        self.assertIn("Piano Terra", summary)
        self.assertIn("switch.pompa_pt", summary)
        self.assertIn("sensor.sala_temp_old", summary)
        self.assertIn("climate.trv_sala_old", summary)

    def test_edit_room_sensors_and_trvs(self):
        """Select room and modify its temperature sensor and TRVs."""
        self.flow._selected_room_id = "sala"

        user_input = {
            "temp_sensor": "sensor.sala_temp_NEW",
            "trvs": ["climate.trv_sala_NEW_1", "climate.trv_sala_NEW_2"],
            "window_sensor": "binary_sensor.finestra_sala",
            "hysteresis": 0.3,
        }

        res = asyncio.run(self.flow.async_step_edit_room_form(user_input))
        self.assertEqual(res["type"], "create_entry")

        # Verify domain model room was updated
        updated_room = self.sys.get_room("sala")
        self.assertEqual(updated_room.temp_sensor_ids, ["sensor.sala_temp_NEW"])
        self.assertEqual(
            updated_room.trv_ids,
            ["climate.trv_sala_NEW_1", "climate.trv_sala_NEW_2"],
        )
        self.assertEqual(
            updated_room.window_sensor_id, "binary_sensor.finestra_sala"
        )
        self.assertEqual(updated_room.hysteresis, 0.3)

        # Verify entry reload was triggered
        self.hass.config_entries.async_reload.assert_called_once_with(
            "test_entry_id"
        )

    def test_add_and_remove_room(self):
        """Add new room via options flow and remove it."""
        # 1. Add Cucina
        add_input = {
            "zone_id": "pt",
            "name": "Cucina",
            "temp_sensor": "sensor.cucina_temp",
            "trvs": ["climate.trv_cucina"],
            "window_sensor": None,
            "hysteresis": 0.2,
        }
        res_add = asyncio.run(self.flow.async_step_add_room(add_input))
        self.assertEqual(res_add["type"], "create_entry")

        cucina = self.sys.get_room("cucina")
        self.assertIsNotNone(cucina)
        self.assertEqual(cucina.name, "Cucina")
        self.assertEqual(cucina.temp_sensor_ids, ["sensor.cucina_temp"])

        # 2. Remove Cucina
        remove_input = {"room_id": "cucina"}
        res_rem = asyncio.run(self.flow.async_step_remove_room(remove_input))
        self.assertEqual(res_rem["type"], "create_entry")
        self.assertIsNone(self.sys.get_room("cucina"))


if __name__ == "__main__":
    unittest.main()
