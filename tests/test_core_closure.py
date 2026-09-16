import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.governance import OutboxEvent
from app.core.security.auth_context import authenticate_context
from app.core.security.context import TenantAccessDenied
from app.core.security.jwt import encode_hs256, decode_hs256
from app.core.governance.outbox import DomainEvent
from app.core.governance.outbox_repository import OutboxRepository

SECRET = "x" * 32


def factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_authenticated_context_requires_live_membership_and_returns_membership_id():
    Factory = factory()
    with Factory() as s:
        tenant = Tenant(name="A", status="active")
        user = User(id="u1", email="u1@example.com", active=True)
        s.add_all([tenant, user])
        s.flush()
        membership = TenantMembership(user_id=user.id, tenant_id=tenant.id, active=True)
        s.add(membership)
        s.commit()

        claims = decode_hs256(
            encode_hs256({"sub": "u1", "tenant_id": tenant.id, "exp": 2000}, SECRET),
            SECRET,
            now=1000,
        )
        ctx = authenticate_context(s, claims)
        assert ctx.user_id == "u1"
        assert ctx.tenant_id == tenant.id
        assert ctx.membership_id == membership.id


def test_authenticated_context_rejects_tenant_override():
    Factory = factory()
    with Factory() as s:
        claims = decode_hs256(
            encode_hs256({"sub": "u1", "tenant_id": 1, "exp": 2000}, SECRET),
            SECRET,
            now=1000,
        )
        with pytest.raises(TenantAccessDenied):
            authenticate_context(s, claims, requested_tenant_id=2)


def test_outbox_duplicate_does_not_rollback_outer_transaction():
    Factory = factory()
    with Factory() as s:
        tenant = Tenant(name="A", status="active")
        s.add(tenant)
        s.flush()
        repo = OutboxRepository(s)
        event = DomainEvent("test", "x", "1", tenant.id, {"ok": True}, event_id="evt-1")
        first = repo.append(event)
        second = repo.append(event)
        marker = Tenant(name="B", status="active")
        s.add(marker)
        s.commit()

        assert first.id == second.id
        assert len(s.scalars(select(OutboxEvent)).all()) == 1
        assert s.scalar(select(Tenant).where(Tenant.name == "B")) is not None
