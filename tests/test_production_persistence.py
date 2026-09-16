import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.db.config import DatabaseSettings
from app.core.db.session import transaction
from app.core.governance.outbox import DomainEvent
from app.core.governance.outbox_repository import OutboxRepository
from app.core.persistence import Base
import app.core.models.core
import app.core.models.finance
import app.core.models.inventory
import app.core.models.governance

def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        DatabaseSettings.from_env()

def test_postgres_url_normalizes_to_psycopg(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
    assert DatabaseSettings.from_env().url.startswith("postgresql+psycopg://")

def test_transaction_rolls_back():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine)
    with pytest.raises(RuntimeError):
        with transaction(Factory) as s:
            s.execute(text("INSERT INTO tenants (name, status) VALUES ('T', 'active')"))
            raise RuntimeError("boom")
    with Factory() as s:
        assert s.execute(text("SELECT COUNT(*) FROM tenants")).scalar_one() == 0

def test_outbox_persists_in_same_transaction():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine)
    with transaction(Factory) as s:
        s.execute(text("INSERT INTO tenants (name, status) VALUES ('T', 'active')"))
        tenant_id = s.execute(text("SELECT id FROM tenants")).scalar_one()
        OutboxRepository(s).append(
            DomainEvent("tenant.created", "tenant", str(tenant_id), tenant_id, {"name": "T"})
        )
    with Factory() as s:
        assert s.execute(text("SELECT COUNT(*) FROM outbox_events")).scalar_one() == 1

def test_postgres_backup_restore_drill_requires_distinct_restore_target():
    from pathlib import Path
    script = Path("scripts/postgres_backup_restore_drill.sh").read_text()
    assert 'RESTORE_DATABASE_URL must point to a distinct restore target' in script
    assert 'EXPECTED_ALEMBIC_REVISION' in script

def test_backup_restore_drill_contains_archive_verification_and_revision_check():
    from pathlib import Path
    script = Path("scripts/postgres_backup_restore_drill.sh").read_text()
    assert 'pg_restore --list' in script
    assert 'pg_restore --clean --if-exists' in script
    assert 'SELECT 1;' in script
    assert 'EXPECTED_ALEMBIC_REVISION' in script
