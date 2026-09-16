from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)

class AIInsight(Base):
    __tablename__='ai_insights'
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    actor_id: Mapped[str]=mapped_column(String(255),nullable=False)
    kind: Mapped[str]=mapped_column(String(80),nullable=False)
    severity: Mapped[str]=mapped_column(String(20),nullable=False)
    title: Mapped[str]=mapped_column(String(500),nullable=False)
    evidence: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    status: Mapped[str]=mapped_column(String(20),nullable=False,default='open')
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)

class AIMemory(Base):
    __tablename__='ai_memories'
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    actor_id: Mapped[str]=mapped_column(String(255),nullable=False)
    key: Mapped[str]=mapped_column(String(160),nullable=False)
    value: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    source: Mapped[str]=mapped_column(String(40),nullable=False,default='user')
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
    __table_args__=(Index('ix_ai_memory_tenant_key','tenant_id','key',unique=True),)

class AIEvaluation(Base):
    __tablename__='ai_evaluations'
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    tenant_id: Mapped[int]=mapped_column(ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False,index=True)
    actor_id: Mapped[str]=mapped_column(String(255),nullable=False)
    run_id: Mapped[str]=mapped_column(String(64),nullable=False,index=True)
    metric: Mapped[str]=mapped_column(String(100),nullable=False)
    score: Mapped[object]=mapped_column(Numeric(5,4),nullable=False)
    details: Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now_utc,nullable=False)
