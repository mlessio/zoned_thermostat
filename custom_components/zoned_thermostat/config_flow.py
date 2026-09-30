"""Config Flow and Options Flow for Zoned Heating Thermostat."""

import logging
from typing import Any, Dict, List, Optional
import uuid

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DEFAULT_HYSTERESIS,
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
    """Handle options flow to modify timings, hysteresis, and presets."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Manage global and advanced options."""
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

        return self.async_show_form(step_id="init", data_schema=schema)
