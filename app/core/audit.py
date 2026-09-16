from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class AuditEvent:
    action: str
    actor_id: str
    tenant_id: int
    subject: str
    subject_id: str
    occurred_at: datetime
    metadata: dict


def make_audit(action: str, actor_id: str, tenant_id: int, subject: str, subject_id: str, metadata: dict | None = None) -> AuditEvent:
    return AuditEvent(action, actor_id, tenant_id, subject, subject_id, datetime.now(timezone.utc), metadata or {})
