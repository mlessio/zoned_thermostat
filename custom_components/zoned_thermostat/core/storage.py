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

        # Lazy import of HA Store helper to allow standalone testing
        try:
            from homeassistant.helpers.storage import Store

            self._store = Store(
                hass,
                STORAGE_VERSION,
                self._key,
                delay_save=SAVE_DELAY,
            )
        except ImportError:
            _LOGGER.debug(
                "Home Assistant Store helper not available in environment; using in-memory mock."
            )
            self._store = None
        self._in_memory_data: Optional[Dict[str, Any]] = None

    async def async_load(self) -> Optional[HeatingSystem]:
        """Load persisted system data and reconstruct HeatingSystem."""
        raw_data: Optional[Dict[str, Any]] = None
        if self._store:
            raw_data = await self._store.async_load()
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
        """Serialize and save HeatingSystem to disk."""
        data = system.to_dict()
        if self._store:
            await self._store.async_save(data)
        else:
            self._in_memory_data = data
