"""Config Flow and Options Flow for Zoned Heating Thermostat."""

import logging
from typing import Any, Dict, List, Optional
import uuid

try:
    import voluptuous as vol
    from homeassistant import config_entries
    from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
    from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
    from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
    from homeassistant.core import callback
    from homeassistant.helpers import selector
except ImportError:
    import unittest.mock as mock

    vol = mock.MagicMock()  # type: ignore

    class _ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            pass

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_show_menu(self, **kwargs):
            return {"type": "menu", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

    class _OptionsFlow:
        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_show_menu(self, **kwargs):
            return {"type": "menu", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

    config_entries = mock.MagicMock()  # type: ignore
    config_entries.ConfigFlow = _ConfigFlow
    config_entries.OptionsFlow = _OptionsFlow
    CLIMATE_DOMAIN = "climate"
    SENSOR_DOMAIN = "sensor"
    SWITCH_DOMAIN = "switch"

    def callback(fn):  # type: ignore
        return fn

    selector = mock.MagicMock()  # type: ignore

from .const import (
    DEFAULT_BUFFER_MIN_TEMP,
    DEFAULT_BUFFER_TEMP_HYSTERESIS,
    DEFAULT_HYSTERESIS,
    DEFAULT_PRESET_COMFORT,
    DEFAULT_PRESET_ECO,
    DEFAULT_PUMP_MIN_OFF_TIME,
    DEFAULT_PUMP_MIN_ON_TIME,
    DEFAULT_PUMP_SHUTDOWN_DELAY,
    DEFAULT_PUMP_STARTUP_DELAY,
    DOMAIN,
    NAME,
)
from .core.system import HeatingSystem
from .core.zone import HeatingZone

_LOGGER = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Generate a clean slug from a text string."""
    return "".join(c if c.isalnum() else "_" for c in text.lower()).strip("_")


class ZonedThermostatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow wizard for Zoned Heating Thermostat."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize wizard state."""
        self._system_name: str = "Riscaldamento"
        self._zones: List[Dict[str, Any]] = []
        self._current_zone_index: int = 0
        self._rooms: List[Dict[str, Any]] = []

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: System Name."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            self._system_name = user_input.get("system_name", "Riscaldamento").strip()
            return await self.async_step_zones()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("system_name", default=self._system_name): str,
                }
            ),
            errors=errors,
        )

    async def async_step_zones(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2: Define Zones (e.g. Piano Terra, Piano Primo)."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            zones_raw = user_input.get("zones", "")
            zone_names = [z.strip() for z in zones_raw.split(",") if z.strip()]
            if not zone_names:
                errors["base"] = "no_zones_defined"
            else:
                self._zones = [
                    {
                        "zone_id": _slugify(name),
                        "name": name,
                        "pump_switch_id": "",
                    }
                    for name in zone_names
                ]
                self._current_zone_index = 0
                return await self.async_step_zone_rooms()

        return self.async_show_form(
            step_id="zones",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "zones", default="Piano Terra, Piano Primo"
                    ): str,
                }
            ),
            description_placeholders={"system_name": self._system_name},
            errors=errors,
        )

    async def async_step_zone_rooms(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Step 3: Define rooms for each zone."""
        current_zone = self._zones[self._current_zone_index]
        errors: Dict[str, str] = {}

        if user_input is not None:
            rooms_raw = user_input.get("rooms", "")
            room_names = [r.strip() for r in rooms_raw.split(",") if r.strip()]
            if not room_names:
                errors["base"] = "no_rooms_defined"
            else:
                for r_name in room_names:
                    self._rooms.append(
                        {
                            "room_id": _slugify(r_name),
                            "name": r_name,
                            "zone_id": current_zone["zone_id"],
                            "zone_name": current_zone["name"],
                        }
                    )
                self._current_zone_index += 1
                if self._current_zone_index < len(self._zones):
                    return await self.async_step_zone_rooms()
                # All zones have room lists defined, now configure sensors for rooms
                self._current_room_index = 0
                return await self.async_step_configure_room()

        default_rooms = (
            "Sala, Cucina, Bunker"
            if current_zone["name"].lower() in ("piano terra", "piano terra ")
            else "Camera, Camera Padronale"
        )

        return self.async_show_form(
            step_id="zone_rooms",
            data_schema=vol.Schema(
                {
                    vol.Required("rooms", default=default_rooms): str,
                }
            ),
            description_placeholders={"zone_name": current_zone["name"]},
            errors=errors,
        )

    async def async_step_configure_room(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Step 4: Configure sensors and TRVs for each room."""
        current_room = self._rooms[self._current_room_index]
        errors: Dict[str, str] = {}

        if user_input is not None:
            current_room["temp_sensor_ids"] = [
                user_input["temp_sensor"]
            ] if user_input.get("temp_sensor") else []
            current_room["trv_ids"] = user_input.get("trvs", [])
            current_room["window_sensor_id"] = user_input.get("window_sensor")

            self._current_room_index += 1
            if self._current_room_index < len(self._rooms):
                return await self.async_step_configure_room()
            # Next: configure pumps
            return await self.async_step_pumps()

        # Autodiscovery suggestions based on room name
        room_slug = current_room["room_id"]
        suggested_sensor = self._find_matching_entity(
            SENSOR_DOMAIN, [room_slug, "temp"]
        )
        suggested_trv = self._find_matching_entities(
            CLIMATE_DOMAIN, [room_slug]
        )

        schema = vol.Schema(
            {
                vol.Required(
                    "temp_sensor",
                    default=suggested_sensor or vol.UNDEFINED,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
                ),
                vol.Optional(
                    "trvs",
                    default=suggested_trv,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=CLIMATE_DOMAIN, multiple=True
                    )
                ),
                vol.Optional("window_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
            }
        )

        return self.async_show_form(
            step_id="configure_room",
            data_schema=schema,
            description_placeholders={
                "room_name": current_room["name"],
                "zone_name": current_room["zone_name"],
            },
            errors=errors,
        )

    async def async_step_pumps(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Step 5: Assign circulation pump switch for each zone."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            for zone in self._zones:
                zone_field = f"pump_{zone['zone_id']}"
                zone["pump_switch_id"] = user_input.get(zone_field)

            return await self.async_step_summary()

        fields: Dict[Any, Any] = {}
        for zone in self._zones:
            suggested_pump = self._find_matching_entity(
                SWITCH_DOMAIN, [zone["zone_id"], "pomp"]
            )
            fields[
                vol.Required(
                    f"pump_{zone['zone_id']}",
                    default=suggested_pump or vol.UNDEFINED,
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=SWITCH_DOMAIN)
            )

        return self.async_show_form(
            step_id="pumps",
            data_schema=vol.Schema(fields),
            description_placeholders={"system_name": self._system_name},
            errors=errors,
        )

    async def async_step_summary(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Step 6: Summary and confirmation."""
        if user_input is not None:
            # Build initial system data dictionary for storage
            system_data = {
                "system_id": str(uuid.uuid4())[:8],
                "name": self._system_name,
                "zones": {
                    z["zone_id"]: {
                        "zone_id": z["zone_id"],
                        "name": z["name"],
                        "pump_switch_id": z["pump_switch_id"],
                        "min_pump_on": DEFAULT_PUMP_MIN_ON_TIME,
                        "min_pump_off": DEFAULT_PUMP_MIN_OFF_TIME,
                        "startup_delay": DEFAULT_PUMP_STARTUP_DELAY,
                        "shutdown_delay": DEFAULT_PUMP_SHUTDOWN_DELAY,
                        "rooms": {
                            r["room_id"]: {
                                "room_id": r["room_id"],
                                "name": r["name"],
                                "zone_id": z["zone_id"],
                                "temp_sensor_ids": r.get("temp_sensor_ids", []),
                                "trv_ids": r.get("trv_ids", []),
                                "window_sensor_id": r.get("window_sensor_id"),
                                "hysteresis": DEFAULT_HYSTERESIS,
                            }
                            for r in self._rooms
                            if r["zone_id"] == z["zone_id"]
                        },
                    }
                    for z in self._zones
                },
            }

            return self.async_create_entry(
                title=self._system_name,
                data=system_data,
            )

        summary_text = "\n".join(
            f"• {z['name']} (Pompa: {z.get('pump_switch_id', 'nessuna')}): "
            + ", ".join(
                r["name"] for r in self._rooms if r["zone_id"] == z["zone_id"]
            )
            for z in self._zones
        )

        return self.async_show_form(
            step_id="summary",
            data_schema=vol.Schema({}),
            description_placeholders={
                "system_name": self._system_name,
                "summary": summary_text,
            },
        )

    def _find_matching_entity(
        self, domain: str, keywords: List[str]
    ) -> Optional[str]:
        """Helper to find an entity whose entity_id contains keywords."""
        states = self.hass.states.async_all(domain)
        for state in states:
            entity_id = state.entity_id.lower()
            if all(k in entity_id for k in keywords):
                return state.entity_id
        return None

    def _find_matching_entities(
        self, domain: str, keywords: List[str]
    ) -> List[str]:
        """Helper to find multiple entities matching keywords."""
        states = self.hass.states.async_all(domain)
        matches = []
        for state in states:
            entity_id = state.entity_id.lower()
            if all(k in entity_id for k in keywords):
                matches.append(state.entity_id)
        return matches

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return ZonedThermostatOptionsFlow(config_entry)


class ZonedThermostatOptionsFlow(config_entries.OptionsFlow):
    """Handle rich options flow to inspect, modify, add and remove rooms, zones, sensors, and pumps."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._selected_room_id: Optional[str] = None
        self._selected_zone_id: Optional[str] = None

    def _get_system(self) -> HeatingSystem:
        """Get the live heating system from coordinator or reconstruct from entry data."""
        entry_id = self._config_entry.entry_id
        domain_data = self.hass.data.get(DOMAIN, {}).get(entry_id, {})
        coordinator = domain_data.get("coordinator")
        if coordinator and coordinator.system:
            return coordinator.system
        return HeatingSystem.from_dict(self._config_entry.data)

    async def _async_save_and_reload(self, system: HeatingSystem) -> None:
        """Save updated system to storage and config entry data, then reload."""
        entry_id = self._config_entry.entry_id
        domain_data = self.hass.data.get(DOMAIN, {}).get(entry_id, {})

        storage = domain_data.get("storage")
        if storage:
            await storage.async_save(system)

        self.hass.config_entries.async_update_entry(
            self._config_entry, data=system.to_dict()
        )

        coordinator = domain_data.get("coordinator")
        if coordinator:
            coordinator._rebuild_tracked_entities()
            coordinator._read_initial_states()
            await coordinator.async_evaluate()

        await self.hass.config_entries.async_reload(entry_id)

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "view_config",
                "buffer_settings",
                "edit_room",
                "edit_zone",
                "add_room",
                "remove_room",
                "add_zone",
                "remove_zone",
                "advanced_options",
            ],
        )

    async def async_step_view_config(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Display read-only comprehensive summary of the current setup."""
        if user_input is not None:
            return await self.async_step_init()

        system = self._get_system()
        lines: List[str] = [f"### Impianto: {system.name}\n"]

        # Buffer Tank Summary
        lines.append("**Accumulo Termico / Puffer:**")
        if system.buffer_temp_sensor:
            status = "PRONTO" if system.is_buffer_ready else "IN RISCALDAMENTO (pompe bloccate)"
            curr = f"{system.buffer_current_temp}°C" if system.buffer_current_temp is not None else "N/D"
            lines.append(f"- Sensore: `{system.buffer_temp_sensor}` (attuale: {curr})")
            lines.append(f"- Soglia minima: {system.buffer_min_temp}°C | Isteresi stop: {system.buffer_temp_hysteresis}°C")
            lines.append(f"- Stato riserva: **{status}**")
        else:
            lines.append("- Nessun sensore accumulo configurato (controllo disattivato)")
        lines.append("")

        for zone in system.zones.values():
            pump_id = zone.pump_controller.pump_switch_id or "Nessuna pompa"
            lines.append(f"**Zona: {zone.name}**")
            lines.append(f"- Pompa: `{pump_id}` (stato fisico: {'ON' if zone.pump_controller.is_physically_on else 'OFF'}, manuale: {'ON' if zone.manual_pump_mode else 'AUTO'})")
            lines.append(
                f"- Tempi Pompa: Min ON {zone.pump_controller.min_on_time}s | Min OFF {zone.pump_controller.min_off_time}s | Avvio {zone.pump_controller.startup_delay}s | Stop {zone.pump_controller.shutdown_delay}s"
            )
            lines.append("- Stanze collegate:")
            if not zone.rooms:
                lines.append("  *(Nessuna stanza configurata per questa zona)*")
            for room in zone.rooms.values():
                s_str = ", ".join(f"`{s}`" for s in room.temp_sensor_ids) if room.temp_sensor_ids else "Nessun sensore"
                t_str = ", ".join(f"`{t}`" for t in room.trv_ids) if room.trv_ids else "Nessuna valvola"
                w_str = f"`{room.window_sensor_id}`" if room.window_sensor_id else "Nessun sensore"
                effective = room.get_effective_presets(system.presets)
                lines.append(f"  • **{room.name}** (Target: {room.target_temp}°C, Isteresi: ±{room.hysteresis}°C):")
                lines.append(f"    - Preset: Comfort {effective.get('comfort')}°C | Eco {effective.get('eco')}°C")
                lines.append(f"    - Temp: {s_str}")
                lines.append(f"    - TRV: {t_str}")
                lines.append(f"    - Finestra: {w_str}")
            lines.append("")

        summary_text = "\n".join(lines)
        return self.async_show_form(
            step_id="view_config",
            data_schema=vol.Schema({}),
            description_placeholders={"summary": summary_text},
        )

    async def async_step_buffer_settings(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Configure thermal storage / buffer tank interlock."""
        system = self._get_system()

        if user_input is not None:
            sensor = user_input.get("buffer_temp_sensor")
            min_temp = float(user_input["buffer_min_temp"])
            hysteresis = float(user_input["buffer_temp_hysteresis"])
            system.configure_buffer(sensor, min_temp, hysteresis)
            await self._async_save_and_reload(system)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Optional(
                    "buffer_temp_sensor",
                    default=system.buffer_temp_sensor or vol.UNDEFINED,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
                ),
                vol.Required(
                    "buffer_min_temp",
                    default=system.buffer_min_temp,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=20.0, max=80.0, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    "buffer_temp_hysteresis",
                    default=system.buffer_temp_hysteresis,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.5, max=10.0, step=0.5, unit_of_measurement="°C"
                    )
                ),
            }
        )

        return self.async_show_form(step_id="buffer_settings", data_schema=schema)

    async def async_step_edit_room(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Select which room to edit."""
        system = self._get_system()
        rooms = system.all_rooms()

        if not rooms:
            return self.async_show_form(
                step_id="edit_room",
                data_schema=vol.Schema({}),
                errors={"base": "no_rooms_defined"},
            )

        if user_input is not None:
            self._selected_room_id = user_input["room_id"]
            return await self.async_step_edit_room_form()

        room_options = {
            r.room_id: f"{r.name} ({system.get_zone(r.zone_id).name if system.get_zone(r.zone_id) else r.zone_id})"
            for r in rooms
        }

        return self.async_show_form(
            step_id="edit_room",
            data_schema=vol.Schema(
                {
                    vol.Required("room_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": k, "label": v}
                                for k, v in room_options.items()
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_edit_room_form(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Edit sensors, TRVs, and hysteresis for selected room."""
        system = self._get_system()
        room = system.get_room(self._selected_room_id)

        if not room:
            return await self.async_step_init()

        if user_input is not None:
            room.temp_sensor_ids = (
                [user_input["temp_sensor"]] if user_input.get("temp_sensor") else []
            )
            room.trv_ids = user_input.get("trvs", [])
            room.window_sensor_id = user_input.get("window_sensor")
            room.hysteresis = float(user_input.get("hysteresis", room.hysteresis))
            if "comfort_temp" in user_input:
                room.set_room_preset("comfort", float(user_input["comfort_temp"]))
            if "eco_temp" in user_input:
                room.set_room_preset("eco", float(user_input["eco_temp"]))
            await self._async_save_and_reload(system)
            return self.async_create_entry(title="", data={})

        curr_sensor = room.temp_sensor_ids[0] if room.temp_sensor_ids else None
        effective = room.get_effective_presets(system.presets)
        schema = vol.Schema(
            {
                vol.Required(
                    "temp_sensor",
                    default=curr_sensor or vol.UNDEFINED,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
                ),
                vol.Optional(
                    "trvs",
                    default=room.trv_ids,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=CLIMATE_DOMAIN, multiple=True
                    )
                ),
                vol.Optional(
                    "window_sensor",
                    default=room.window_sensor_id or vol.UNDEFINED,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Required(
                    "comfort_temp",
                    default=room.presets_override.get(
                        "comfort", effective.get("comfort", DEFAULT_PRESET_COMFORT)
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=14.0, max=30.0, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    "eco_temp",
                    default=room.presets_override.get(
                        "eco", effective.get("eco", DEFAULT_PRESET_ECO)
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10.0, max=25.0, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    "hysteresis",
                    default=room.hysteresis,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1, max=2.0, step=0.05, unit_of_measurement="°C"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="edit_room_form",
            data_schema=schema,
            description_placeholders={"room_name": room.name},
        )

    async def async_step_edit_zone(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Select which zone to edit."""
        system = self._get_system()
        if not system.zones:
            return self.async_show_form(
                step_id="edit_zone",
                data_schema=vol.Schema({}),
                errors={"base": "no_zones_defined"},
            )

        if user_input is not None:
            self._selected_zone_id = user_input["zone_id"]
            return await self.async_step_edit_zone_form()

        zone_options = {z.zone_id: z.name for z in system.zones.values()}
        return self.async_show_form(
            step_id="edit_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("zone_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": k, "label": v}
                                for k, v in zone_options.items()
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_edit_zone_form(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Edit pump switch and timing delays for selected zone."""
        system = self._get_system()
        zone = system.get_zone(self._selected_zone_id)

        if not zone:
            return await self.async_step_init()

        if user_input is not None:
            zone.pump_controller.pump_switch_id = user_input["pump_switch"]
            zone.pump_controller.min_on_time = int(user_input["min_pump_on_time"])
            zone.pump_controller.min_off_time = int(user_input["min_pump_off_time"])
            zone.pump_controller.startup_delay = int(user_input["startup_delay"])
            zone.pump_controller.shutdown_delay = int(user_input["shutdown_delay"])
            await self._async_save_and_reload(system)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(
                    "pump_switch",
                    default=zone.pump_controller.pump_switch_id or vol.UNDEFINED,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=SWITCH_DOMAIN)
                ),
                vol.Required(
                    "min_pump_on_time",
                    default=zone.pump_controller.min_on_time,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30, max=600, step=10, unit_of_measurement="s"
                    )
                ),
                vol.Required(
                    "min_pump_off_time",
                    default=zone.pump_controller.min_off_time,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30, max=600, step=10, unit_of_measurement="s"
                    )
                ),
                vol.Required(
                    "startup_delay",
                    default=zone.pump_controller.startup_delay,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=120, step=5, unit_of_measurement="s"
                    )
                ),
                vol.Required(
                    "shutdown_delay",
                    default=zone.pump_controller.shutdown_delay,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=300, step=5, unit_of_measurement="s"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="edit_zone_form",
            data_schema=schema,
            description_placeholders={"zone_name": zone.name},
        )

    async def async_step_add_room(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Add a new room to an existing zone."""
        system = self._get_system()
        errors: Dict[str, str] = {}

        if user_input is not None:
            zone = system.get_zone(user_input["zone_id"])
            if zone:
                from .core.room import HeatingRoom

                room_name = user_input["name"].strip()
                new_room = HeatingRoom(
                    room_id=_slugify(room_name),
                    name=room_name,
                    zone_id=zone.zone_id,
                    temp_sensor_ids=[user_input["temp_sensor"]] if user_input.get("temp_sensor") else [],
                    trv_ids=user_input.get("trvs", []),
                    window_sensor_id=user_input.get("window_sensor"),
                    hysteresis=float(user_input.get("hysteresis", DEFAULT_HYSTERESIS)),
                    presets_override={
                        "comfort": float(user_input.get("comfort_temp", DEFAULT_PRESET_COMFORT)),
                        "eco": float(user_input.get("eco_temp", DEFAULT_PRESET_ECO)),
                    },
                )
                zone.add_room(new_room)
                await self._async_save_and_reload(system)
                return self.async_create_entry(title="", data={})

        zone_options = [
            {"value": z.zone_id, "label": z.name}
            for z in system.zones.values()
        ]

        schema = vol.Schema(
            {
                vol.Required("zone_id"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=zone_options)
                ),
                vol.Required("name"): str,
                vol.Required("temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=SENSOR_DOMAIN)
                ),
                vol.Optional("trvs", default=[]): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=CLIMATE_DOMAIN, multiple=True
                    )
                ),
                vol.Optional("window_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Required("comfort_temp", default=DEFAULT_PRESET_COMFORT): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=14.0, max=30.0, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required("eco_temp", default=DEFAULT_PRESET_ECO): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10.0, max=25.0, step=0.5, unit_of_measurement="°C"
                    )
                ),
                vol.Required("hysteresis", default=DEFAULT_HYSTERESIS): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1, max=2.0, step=0.05, unit_of_measurement="°C"
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="add_room", data_schema=schema, errors=errors
        )

    async def async_step_remove_room(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Remove a room from the system."""
        system = self._get_system()
        rooms = system.all_rooms()

        if not rooms:
            return self.async_show_form(
                step_id="remove_room",
                data_schema=vol.Schema({}),
                errors={"base": "no_rooms_defined"},
            )

        if user_input is not None:
            r_id = user_input["room_id"]
            for zone in system.zones.values():
                if r_id in zone.rooms:
                    zone.remove_room(r_id)
                    break
            await self._async_save_and_reload(system)
            return self.async_create_entry(title="", data={})

        room_options = [
            {
                "value": r.room_id,
                "label": f"{r.name} ({system.get_zone(r.zone_id).name if system.get_zone(r.zone_id) else r.zone_id})",
            }
            for r in rooms
        ]

        return self.async_show_form(
            step_id="remove_room",
            data_schema=vol.Schema(
                {
                    vol.Required("room_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=room_options)
                    )
                }
            ),
        )

    async def async_step_add_zone(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Add a new zone with its pump switch."""
        system = self._get_system()

        if user_input is not None:
            from .core.zone import HeatingZone

            z_name = user_input["name"].strip()
            new_zone = HeatingZone(
                zone_id=_slugify(z_name),
                name=z_name,
                pump_switch_id=user_input["pump_switch"],
                min_pump_on=DEFAULT_PUMP_MIN_ON_TIME,
                min_pump_off=DEFAULT_PUMP_MIN_OFF_TIME,
                startup_delay=DEFAULT_PUMP_STARTUP_DELAY,
                shutdown_delay=DEFAULT_PUMP_SHUTDOWN_DELAY,
            )
            system.add_zone(new_zone)
            await self._async_save_and_reload(system)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required("name"): str,
                vol.Required("pump_switch"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=SWITCH_DOMAIN)
                ),
            }
        )

        return self.async_show_form(step_id="add_zone", data_schema=schema)

    async def async_step_remove_zone(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Remove an entire zone."""
        system = self._get_system()

        if user_input is not None:
            z_id = user_input["zone_id"]
            system.zones.pop(z_id, None)
            await self._async_save_and_reload(system)
            return self.async_create_entry(title="", data={})

        zone_options = [
            {"value": z.zone_id, "label": z.name}
            for z in system.zones.values()
        ]

        return self.async_show_form(
            step_id="remove_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("zone_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=zone_options)
                    )
                }
            ),
        )

    async def async_step_advanced_options(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Manage global timings and hysteresis options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    "default_hysteresis",
                    default=self._config_entry.options.get(
                        "default_hysteresis", DEFAULT_HYSTERESIS
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1, max=2.0, step=0.05, unit_of_measurement="°C"
                    )
                ),
                vol.Required(
                    "min_pump_on_time",
                    default=self._config_entry.options.get(
                        "min_pump_on_time", DEFAULT_PUMP_MIN_ON_TIME
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30, max=600, step=10, unit_of_measurement="s"
                    )
                ),
                vol.Required(
                    "min_pump_off_time",
                    default=self._config_entry.options.get(
                        "min_pump_off_time", DEFAULT_PUMP_MIN_OFF_TIME
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30, max=600, step=10, unit_of_measurement="s"
                    )
                ),
                vol.Required(
                    "startup_delay",
                    default=self._config_entry.options.get(
                        "startup_delay", DEFAULT_PUMP_STARTUP_DELAY
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=120, step=5, unit_of_measurement="s"
                    )
                ),
                vol.Required(
                    "shutdown_delay",
                    default=self._config_entry.options.get(
                        "shutdown_delay", DEFAULT_PUMP_SHUTDOWN_DELAY
                    ),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=300, step=5, unit_of_measurement="s"
                    )
                ),
            }
        )

        return self.async_show_form(step_id="advanced_options", data_schema=schema)
