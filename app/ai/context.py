"""Context assembly rules for AI-01.

The context builder labels every item. Live domain facts outrank memory; external
content is data, not instructions. No raw database access is exposed to models.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models.ai_foundation import AIMemoryRecord
from .contracts import ContextItem, DataClass, MemoryType


@dataclass(frozen=True)
class ContextEnvelope:
    system_policy: str
    items: list[ContextItem]

    def as_prompt_data(self) -> dict:
        return {"system_policy": self.system_policy, "items": [x.model_dump(mode="json") for x in self.items]}


def build_context(db: Session, tenant_id: int, *, owner_id: str | None = None, agent_code: str | None = None,
                  system_policy: str, live_facts: list[ContextItem] | None = None, max_memories: int = 50) -> ContextEnvelope:
    now = datetime.now(timezone.utc)
    rows = db.scalars(select(AIMemoryRecord).where(
        AIMemoryRecord.tenant_id == tenant_id,
        AIMemoryRecord.revoked_at.is_(None),
        (AIMemoryRecord.expires_at.is_(None) | (AIMemoryRecord.expires_at > now)),
    ).order_by(AIMemoryRecord.updated_at.desc()).limit(max_memories)).all()
    items: list[ContextItem] = []
    for row in rows:
        if row.memory_type == MemoryType.USER_PREFERENCE.value and owner_id and row.owner_id != owner_id:
            continue
        if row.owner_id and owner_id and row.owner_id != owner_id and row.memory_type == MemoryType.USER_PREFERENCE.value:
            continue
        if row.agent_code and agent_code and row.agent_code != agent_code and row.memory_type == MemoryType.AGENT_WORKING.value:
            continue
        cls = DataClass.PERSONAL if row.memory_type == MemoryType.USER_PREFERENCE.value else DataClass.TENANT
        items.append(ContextItem(source="memory", kind=row.memory_type, data_class=cls, trusted=row.trust == "verified", content={"key": row.key, "value": row.value}))
    # Live domain facts are deliberately appended after memory and can be treated as authoritative.
    items.extend(live_facts or [])
    return ContextEnvelope(system_policy=system_policy, items=items)
