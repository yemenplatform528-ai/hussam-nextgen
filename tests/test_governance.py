import pytest

from app.core.governance.policy import PolicyDenied, require_permissions
from app.core.governance.lifecycle import InvalidTransition, LifecycleState, transition
from app.core.governance.outbox import DomainEvent
from app.core.governance.idempotency import IdempotencyConflict, IdempotencyResult, ensure_same_request

def test_policy_requires_all_permissions():
    require_permissions({"tenant.read", "ledger.post"}, {"tenant.read"})
    with pytest.raises(PolicyDenied):
        require_permissions({"tenant.read"}, {"tenant.read", "ledger.post"})

def test_lifecycle_is_explicit_and_closed():
    assert transition(LifecycleState.DRAFT, LifecycleState.ACTIVE) == LifecycleState.ACTIVE
    with pytest.raises(InvalidTransition):
        transition(LifecycleState.ARCHIVED, LifecycleState.ACTIVE)

def test_event_gets_stable_identity_and_time():
    e = DomainEvent("ledger.posted", "journal", "j1", 7, {"reference": "R1"}).materialize()
    assert e.event_id
    assert e.occurred_at is not None
    assert e.tenant_id == 7

def test_idempotency_replays_same_request_but_rejects_mismatch():
    existing = IdempotencyResult("K1", "fp-a", 201, {"ok": True})
    assert ensure_same_request(existing, "K1", "fp-a") == existing
    with pytest.raises(IdempotencyConflict):
        ensure_same_request(existing, "K1", "fp-b")
