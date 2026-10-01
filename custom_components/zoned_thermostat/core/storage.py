"""Storage manager for Zoned Heating Thermostat using Home Assistant Store."""

import logging
from typing import Any, Dict, Optional

from ..const import DOMAIN, SAVE_DELAY, STORAGE_KEY, STORAGE_VERSION
from .system import HeatingSystem

_LOGGER = logging.getLogger(__name__)


class ZonedThermostatStorage:
    """Manages persistent JSON storage in .storage/zoned_thermostat.storage."""

    def __init__(self, hass: Any, entry_id: str) -> None:
        """Initialize the storage helper."""
        self.hass = hass
        self.entry_id = entry_id
        self._store = None
        self._key = f"{STORAGE_KEY}_{entry_id}"

        # Initialize Home Assistant Store helper
        try:
            from homeassistant.helpers.storage import Store

            self._store = Store(hass, STORAGE_VERSION, self._key)
        except Exception as err:
            _LOGGER.debug(
                "Home Assistant Store helper init notice: %s; using in-memory mock.",
                err,
            )
            self._store = None
        self._in_memory_data: Optional[Dict[str, Any]] = None

    async def async_load(self) -> Optional[HeatingSystem]:
        """Load persisted system data and reconstruct HeatingSystem."""
        raw_data: Optional[Dict[str, Any]] = None
        if self._store:
            try:
                raw_data = await self._store.async_load()
            except Exception as err:
                _LOGGER.error("Failed to load from Home Assistant store: %s", err)
                raw_data = None
        else:
            raw_data = self._in_memory_data

        if not raw_data:
            return None

        try:
            return HeatingSystem.from_dict(raw_data)
        except Exception as err:
            _LOGGER.error(
                "Failed to deserialize Zoned Heating Thermostat storage: %s",
                err,
                exc_info=True,
            )
            return None

    async def async_save(self, system: HeatingSystem) -> None:
        """Serialize and save HeatingSystem to disk immediately."""
        data = system.to_dict()
        if self._store:
            try:
                await self._store.async_save(data)
            except Exception as err:
                _LOGGER.error("Failed to save to Home Assistant store: %s", err)
        else:
            self._in_memory_data = data
