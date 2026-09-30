"""Diagnostic Event Log buffer for Zoned Heating Thermostat."""

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional


@dataclass
class DiagnosticEvent:
    """Represents a significant state change or decision in the heating system."""

    entity_type: str
    entity_id: str
    entity_name: str
    event_type: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    iso_time: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return asdict(self)


class EventLogBuffer:
    """Thread-safe ring buffer for diagnostic events."""

    def __init__(self, max_size: int = 100) -> None:
        """Initialize the event buffer with a fixed size."""
        self._max_size = max_size
        self._events: deque[DiagnosticEvent] = deque(maxlen=max_size)

    def record(
        self,
        entity_type: str,
        entity_id: str,
        entity_name: str,
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticEvent:
        """Record a new event and append to circular buffer."""
        event = DiagnosticEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            event_type=event_type,
            message=message,
            metadata=metadata or {},
        )
        self._events.append(event)
        return event

    def get_events(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return list of events in reverse chronological order (newest first)."""
        all_events = list(self._events)
        all_events.reverse()
        if limit is not None and limit > 0:
            all_events = all_events[:limit]
        return [e.to_dict() for e in all_events]

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()

    def __len__(self) -> int:
        """Return number of events currently in buffer."""
        return len(self._events)
