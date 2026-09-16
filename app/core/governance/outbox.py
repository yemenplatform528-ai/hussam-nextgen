from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

@dataclass(frozen=True)
class DomainEvent:
    event_type: str
    aggregate_type: str
    aggregate_id: str
    tenant_id: int
    payload: dict
    event_id: str = ""
    occurred_at: datetime | None = None

    def materialize(self) -> "DomainEvent":
        return DomainEvent(
            event_type=self.event_type,
            aggregate_type=self.aggregate_type,
            aggregate_id=self.aggregate_id,
            tenant_id=self.tenant_id,
            payload=dict(self.payload),
            event_id=self.event_id or str(uuid4()),
            occurred_at=self.occurred_at or datetime.now(timezone.utc),
        )
