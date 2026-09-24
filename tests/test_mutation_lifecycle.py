from sqlalchemy import select
import pytest

from app.core.models.core import Tenant, User, MutationRecord
from app.core.persistence import make_session_factory
from app.core.services.mutation_lifecycle import MutationLifecycleError, MutationLifecycleService, canonical_request_hash


def _db():
    engine, factory = make_session_factory()
    return factory()


def test_mutation_lifecycle_reserve_replay_and_conflict():
    db = _db()
    tenant = Tenant(name="Lifecycle Tenant")
    user = User(id="lifecycle-user", email="lifecycle@example.com")
    db.add_all([tenant, user])
    db.commit()

    service = MutationLifecycleService(db)
    body = {"listing_id": 10, "quantity": 2}
    h = canonical_request_hash("marketplace.cart.add", user.id, body)
    first, replay = service.reserve(tenant.id, user.id, "marketplace.cart.add", "m-001", h)
    assert replay is False
    service.transition(first, "confirmed", resource_type="cart_item", resource_id="55", response={"id": 55})
    db.commit()

    second, replay = service.reserve(tenant.id, user.id, "marketplace.cart.add", "m-001", h)
    assert replay is True
    assert second.id == first.id
    assert second.state == "confirmed"

    with pytest.raises(MutationLifecycleError, match="different request"):
        service.reserve(tenant.id, user.id, "marketplace.cart.add", "m-001",
                        canonical_request_hash("marketplace.cart.add", user.id, {"listing_id": 10, "quantity": 3}))


def test_mutation_lifecycle_conflict_requires_explicit_resolution():
    db = _db()
    tenant = Tenant(name="Conflict Tenant")
    user = User(id="conflict-user", email="conflict@example.com")
    db.add_all([tenant, user])
    db.commit()
    service = MutationLifecycleService(db)
    h = canonical_request_hash("marketplace.cart.update", user.id, {"quantity": 3})
    record, _ = service.reserve(tenant.id, user.id, "marketplace.cart.update", "m-002", h)
    service.transition(record, "conflict", response={"reason": "server_changed"})
    with pytest.raises(MutationLifecycleError, match="requires explicit"):
        service.transition(record, "pending")
    service.transition(record, "confirmed", resource_type="cart", resource_id="7", response={"quantity": 3})
    assert record.state == "confirmed"
