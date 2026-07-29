from typing import Generic, List, TypeVar
from pydantic import PrivateAttr
from app.shared.kernel.entity import Entity
from app.shared.kernel.domain_event import DomainEvent

ID = TypeVar("ID")

class AggregateRoot(Entity[ID], Generic[ID]):
    """Base class for Aggregate Roots that manage domain events."""
    _domain_events: List[DomainEvent] = PrivateAttr(default_factory=list)

    def add_domain_event(self, event: DomainEvent) -> None:
        """Record a domain event."""
        if not hasattr(self, "_domain_events") or self._domain_events is None:
            self._domain_events = []
        self._domain_events.append(event)

    def clear_domain_events(self) -> None:
        """Clear all recorded domain events."""
        self._domain_events = []

    def get_domain_events(self) -> List[DomainEvent]:
        """Get all recorded domain events."""
        return getattr(self, "_domain_events", []) or []
