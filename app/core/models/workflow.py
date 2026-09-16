from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)

class WorkflowDefinition(Base):
    __tablename__ = 'workflow_definitions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(__import__('sqlalchemy').Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id','code','version',name='uq_workflow_definition_tenant_code_version'), CheckConstraint('version > 0', name='ck_workflow_definition_positive_version'))

class WorkflowInstance(Base):
    __tablename__ = 'workflow_instances'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    definition_id: Mapped[int] = mapped_column(ForeignKey('workflow_definitions.id', ondelete='RESTRICT'), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False)
    current_step: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='running')
    context_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id','reference',name='uq_workflow_instance_tenant_reference'),
        CheckConstraint("status IN ('running','waiting','completed','failed','cancelled')", name='ck_workflow_instance_status'),
    )

class WorkflowTransition(Base):
    __tablename__ = 'workflow_transitions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    instance_id: Mapped[int] = mapped_column(ForeignKey('workflow_instances.id', ondelete='CASCADE'), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    from_step: Mapped[str] = mapped_column(String(120), nullable=False)
    to_step: Mapped[str] = mapped_column(String(120), nullable=False)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (UniqueConstraint('tenant_id','event_id',name='uq_workflow_transition_tenant_event'),)

class WorkflowTask(Base):
    __tablename__ = 'workflow_tasks'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    instance_id: Mapped[int] = mapped_column(ForeignKey('workflow_instances.id', ondelete='CASCADE'), nullable=False, index=True)
    step: Mapped[str] = mapped_column(String(120), nullable=False)
    task_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='pending')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id','instance_id','task_key',name='uq_workflow_task_tenant_instance_key'),
        CheckConstraint("status IN ('pending','running','succeeded','failed','cancelled')", name='ck_workflow_task_status'),
        CheckConstraint('attempts >= 0', name='ck_workflow_task_attempts_nonnegative'),
    )
