"""Pump Controller state machine with anti-short-cycle protections."""

from enum import Enum
import time
from typing import Any, Dict, Optional, Tuple

from .enums import PumpState


class PumpAction(str, Enum):
    """Action required on the physical switch actuator."""

    NONE = "none"
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"


class PumpController:
    """Manages the physical circulation pump with anti-short-cycle timing and delays."""

    def __init__(
        self,
        pump_switch_id: str,
        min_on_time: int = 120,
        min_off_time: int = 120,
        startup_delay: int = 15,
        shutdown_delay: int = 30,
    ) -> None:
        """Initialize the pump controller."""
        self.pump_switch_id = pump_switch_id
        self.min_on_time = min_on_time
        self.min_off_time = min_off_time
        self.startup_delay = startup_delay
        self.shutdown_delay = shutdown_delay

        # Operational state
        self.state: PumpState = PumpState.OFF
        self.is_physically_on: bool = False
        self.zone_demands_heat: bool = False

        # Timestamps (seconds since epoch)
        self.last_turn_on_time: Optional[float] = None
        self.last_turn_off_time: Optional[float] = None
        self.startup_requested_time: Optional[float] = None
        self.shutdown_requested_time: Optional[float] = None

        # Diagnostic message
        self.status_reason: str = "Inizializzato (spento)"

    def update_physical_state(self, is_on: bool, now: Optional[float] = None) -> None:
        """Update physical switch state reported by Home Assistant."""
        t = now if now is not None else time.time()
        if self.is_physically_on != is_on:
            self.is_physically_on = is_on
            if is_on:
                self.last_turn_on_time = t
                self.state = PumpState.ON
                self.status_reason = "Fisicamente accesa"
            else:
                self.last_turn_off_time = t
                self.state = PumpState.OFF
                self.status_reason = "Fisicamente spenta"

    def set_unavailable(self, unavailable: bool = True) -> None:
        """Mark pump entity as unavailable."""
        if unavailable:
            self.state = PumpState.UNAVAILABLE
            self.status_reason = "Entità pompa non disponibile (offline)"
        else:
            if self.state == PumpState.UNAVAILABLE:
                self.state = PumpState.ON if self.is_physically_on else PumpState.OFF
                self.status_reason = "Entità pompa tornata disponibile"

    def evaluate(
        self, zone_demands_heat: bool, now: Optional[float] = None
    ) -> Tuple[PumpAction, str]:
        """Evaluate the state machine based on aggregated zone demand.

        Returns:
            Tuple[PumpAction, reason_string]
        """
        t = now if now is not None else time.time()
        self.zone_demands_heat = zone_demands_heat

        if self.state == PumpState.UNAVAILABLE:
            return (PumpAction.NONE, self.status_reason)

        # -------------------------------------------------------------
        # CASE 1: ZONE DEMANDS HEAT
        # -------------------------------------------------------------
        if zone_demands_heat:
            self.shutdown_requested_time = None  # Reset any pending shutdown

            # If already physically on
            if self.is_physically_on:
                self.state = PumpState.ON
                self.startup_requested_time = None
                self.status_reason = "Pompa attiva per richiesta di calore"
                return (PumpAction.NONE, self.status_reason)

            # Check min_off_time protection
            if self.last_turn_off_time is not None:
                elapsed_off = t - self.last_turn_off_time
                if elapsed_off < self.min_off_time:
                    remaining_off = int(self.min_off_time - elapsed_off)
                    self.state = PumpState.STARTING
                    self.status_reason = (
                        f"Attesa tempo minimo di spegnimento ({remaining_off}s rimanenti)"
                    )
                    return (PumpAction.NONE, self.status_reason)

            # Check startup delay (allows TRVs to open before circulation)
            if self.startup_delay > 0:
                if self.startup_requested_time is None:
                    self.startup_requested_time = t
                    self.state = PumpState.STARTING
                    self.status_reason = (
                        f"Attesa apertura valvole (startup delay {self.startup_delay}s)"
                    )
                    return (PumpAction.NONE, self.status_reason)

                elapsed_startup = t - self.startup_requested_time
                if elapsed_startup < self.startup_delay:
                    remaining_delay = int(self.startup_delay - elapsed_startup)
                    self.state = PumpState.STARTING
                    self.status_reason = (
                        f"Apertura valvole in corso ({remaining_delay}s rimanenti)"
                    )
                    return (PumpAction.NONE, self.status_reason)

            # All clear: turn ON pump
            self.startup_requested_time = None
            self.last_turn_on_time = t
            self.is_physically_on = True
            self.state = PumpState.ON
            self.status_reason = "Avvio pompa (richiesta di calore zona attiva)"
            return (PumpAction.TURN_ON, self.status_reason)

        # -------------------------------------------------------------
        # CASE 2: ZONE DOES NOT DEMAND HEAT
        # -------------------------------------------------------------
        self.startup_requested_time = None  # Cancel pending startup

        # If already physically off
        if not self.is_physically_on:
            self.shutdown_requested_time = None
            self.state = PumpState.OFF
            self.status_reason = "Nessuna richiesta di calore (spenta)"
            return (PumpAction.NONE, self.status_reason)

        # Pump is currently ON: check min_on_time protection
        if self.last_turn_on_time is not None:
            elapsed_on = t - self.last_turn_on_time
            if elapsed_on < self.min_on_time:
                remaining_on = int(self.min_on_time - elapsed_on)
                self.state = PumpState.STOPPING
                self.status_reason = (
                    f"Protezione tempo minimo di accensione ({remaining_on}s rimanenti)"
                )
                return (PumpAction.NONE, self.status_reason)

        # Check shutdown delay (post-circulation)
        if self.shutdown_delay > 0:
            if self.shutdown_requested_time is None:
                self.shutdown_requested_time = t
                self.state = PumpState.STOPPING
                self.status_reason = (
                    f"Post-circolazione in corso (shutdown delay {self.shutdown_delay}s)"
                )
                return (PumpAction.NONE, self.status_reason)

            elapsed_shutdown = t - self.shutdown_requested_time
            if elapsed_shutdown < self.shutdown_delay:
                remaining_shutdown = int(self.shutdown_delay - elapsed_shutdown)
                self.state = PumpState.STOPPING
                self.status_reason = (
                    f"Post-circolazione in corso ({remaining_shutdown}s rimanenti)"
                )
                return (PumpAction.NONE, self.status_reason)

        # All clear: turn OFF pump
        self.shutdown_requested_time = None
        self.last_turn_off_time = t
        self.is_physically_on = False
        self.state = PumpState.OFF
        self.status_reason = "Spegnimento pompa (nessuna richiesta di calore)"
        return (PumpAction.TURN_OFF, self.status_reason)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize pump controller state for UI diagnostics."""
        return {
            "pump_switch_id": self.pump_switch_id,
            "state": self.state.value,
            "is_physically_on": self.is_physically_on,
            "zone_demands_heat": self.zone_demands_heat,
            "status_reason": self.status_reason,
            "min_on_time": self.min_on_time,
            "min_off_time": self.min_off_time,
            "startup_delay": self.startup_delay,
            "shutdown_delay": self.shutdown_delay,
            "last_turn_on_time": self.last_turn_on_time,
            "last_turn_off_time": self.last_turn_off_time,
        }
