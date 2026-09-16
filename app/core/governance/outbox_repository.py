from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.governance.outbox import DomainEvent
from app.core.models.governance import OutboxEvent

class OutboxRepository:
    def __init__(self, session):
        self.session = session

    def append(self, event: DomainEvent) -> OutboxEvent:
        e = event.materialize()
        existing = self.session.scalar(
            select(OutboxEvent).where(OutboxEvent.event_id == e.event_id)
        )
        if existing is not None:
            return existing

        record = OutboxEvent(
            event_id=e.event_id,
            tenant_id=e.tenant_id,
            event_type=e.event_type,
            aggregate_type=e.aggregate_type,
            aggregate_id=e.aggregate_id,
            payload=e.payload,
            published=False,
        )
        try:
            with self.session.begin_nested():
                self.session.add(record)
                self.session.flush()
        except IntegrityError:
            existing = self.session.scalar(
                select(OutboxEvent).where(OutboxEvent.event_id == e.event_id)
            )
            if existing is None:
                raise
            return existing
        return record

    def unpublished(self, limit: int = 100) -> list[OutboxEvent]:
        return list(
            self.session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.published.is_(False))
                .order_by(OutboxEvent.id)
                .limit(limit)
            )
        )

    def mark_published(self, record: OutboxEvent) -> None:
        record.published = True
