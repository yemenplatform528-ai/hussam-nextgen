from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base

def now_utc(): return datetime.now(timezone.utc)

class DeveloperExtension(Base):
    __tablename__ = 'developer_extensions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default='')
    extension_type: Mapped[str] = mapped_column(String(30), nullable=False, default='module')
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft')
    market_scope: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('tenant_id','code', name='uq_developer_extension_tenant_code'),
        CheckConstraint("extension_type IN ('config','module','adapter','platform')", name='ck_developer_extension_type'),
        CheckConstraint("status IN ('draft','validated','testing','published','active','suspended','retired')", name='ck_developer_extension_status'),
    )

class DeveloperExtensionVersion(Base):
    __tablename__ = 'developer_extension_versions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    extension_id: Mapped[str] = mapped_column(ForeignKey('developer_extensions.id', ondelete='CASCADE'), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    compatibility: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    test_status: Mapped[str] = mapped_column(String(30), nullable=False, default='pending')
    test_evidence_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    test_run_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    release_status: Mapped[str] = mapped_column(String(30), nullable=False, default='draft')
    rollback_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        UniqueConstraint('extension_id','version', name='uq_developer_extension_version'),
        CheckConstraint("test_status IN ('pending','passed','failed')", name='ck_developer_extension_test_status'),
        CheckConstraint("(test_status = 'pending') OR (test_evidence_hash IS NOT NULL AND test_run_id IS NOT NULL AND tested_at IS NOT NULL)", name='ck_developer_extension_test_evidence'),
        CheckConstraint("release_status IN ('draft','sandbox','published','active','suspended','rolled_back')", name='ck_developer_extension_release_status'),
    )

class DeveloperExtensionAudit(Base):
    __tablename__ = 'developer_extension_audit'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    extension_id: Mapped[str] = mapped_column(ForeignKey('developer_extensions.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
