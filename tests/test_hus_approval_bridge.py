from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import pytest

from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.ai_hus import AIRun, AIAction, HUSCompilation
from app.core.models.oidc import OIDCIdentity
from app.core.models.amazon_completion import HUSExecutionRecord
from app.core.models.ai_foundation import AITraceEvent
from app.core.persistence import Base
from app.hus.operational import execute_compiled_action
from app.hus.runtime import HUSRuntimeError, SovereignRuntime, _hash


def db():
    e = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(e)
    return sessionmaker(e, expire_on_commit=False)()


def seed(s, *, approval_status="approved", approver_role="owner", approval_args=None):
    s.add(Tenant(id=1, name="Test"))
    s.add(User(id="owner-1", email="owner@example.com", active=True))
    s.add(TenantMembership(user_id="owner-1", tenant_id=1, role=approver_role, active=True))
    s.add(OIDCIdentity(user_id="owner-1", issuer="https://issuer.example", subject="oidc-owner-1"))
    s.add(AIRun(id="run-1", tenant_id=1, actor_id="actor-1", purpose="test", status="approved", input_hash="h" * 64))
    approval_payload = approval_args or args()\n    s.add(AIAction(id="approval-1", tenant_id=1, run_id="run-1", tool_code="commerce.sales.create", risk="mutation", arguments=approval_payload, status=approval_status, approved_by="owner-1", approval_provenance={"auth_source":"oidc","oidc_issuer":"https://issuer.example","oidc_subject":"oidc-owner-1","execution_binding":{"compilation_id":"c1","step_id":"w.create","plan_hash":"p"*64,"action":"commerce.sales.create","idempotency_key":"idem-1","arguments_hash":_hash(approval_payload)}}))
    s.add(HUSCompilation(
        id="c1", tenant_id=1, actor_id="owner-1", spec_version="1.0",
        source_hash="s" * 64, contract_hash="p" * 64, status="active",
        contract={"execution_plan":{"workflows":[{"code":"w","steps":[{
            "id":"w.create","action":{"engine":"commerce","capability":"sales.create"},
            "risk":"mutation","idempotency_required":True
        }]}]}}
    ))
    s.commit()


def args():
    return {"reference":"bridge-test","currency":"YER","lines":[{"item_id":"missing-item","quantity":"1","unit_price":"1"}]}


def test_approved_owner_is_accepted_but_domain_validation_still_applies():
    s = db(); seed(s)
    with pytest.raises(HUSRuntimeError, match="failed"):
        execute_compiled_action(s, 1, "actor-1", "c1", "commerce.sales.create", args(),
                                approved=True, approval_ref="approval-1", idempotency_key="idem-1")
    failed = s.scalars(select(HUSExecutionRecord).where(HUSExecutionRecord.status == "failed")).all()
    assert failed
    assert failed[-1].output_json["verification"]["status"] == "FAIL"
    assert failed[-1].output_json["evidence"]["success_claim"] is False
    events = s.scalars(select(AITraceEvent).where(AITraceEvent.run_id == "run-1").order_by(AITraceEvent.created_at)).all()
    assert [e.event_type for e in events[-3:]] == [
        "HUS_EXECUTION_OBSERVED",
        "HUS_EXECUTION_VERIFICATION_FAILED",
        "HUS_EXECUTION_NO_SUCCESS_EVIDENCE",
    ]


def test_unapproved_action_is_rejected_by_verifier():
    s = db(); seed(s, approval_status="pending_approval")
    with pytest.raises(HUSRuntimeError, match="approval evidence"):
        execute_compiled_action(s, 1, "actor-1", "c1", "commerce.sales.create", args(),
                                approved=True, approval_ref="approval-1", idempotency_key="idem-1")


def test_non_admin_approver_is_rejected_by_verifier():
    s = db(); seed(s, approver_role="member")
    with pytest.raises(HUSRuntimeError, match="approval evidence"):
        execute_compiled_action(s, 1, "actor-1", "c1", "commerce.sales.create", args(),
                                approved=True, approval_ref="approval-1", idempotency_key="idem-1")


def test_wrong_tool_binding_is_rejected():
    s = db(); seed(s)
    action = s.get(AIAction, "approval-1")
    action.tool_code = "finance.finance.read"
    s.commit()
    with pytest.raises(HUSRuntimeError, match="approval evidence"):
        execute_compiled_action(s, 1, "actor-1", "c1", "commerce.sales.create", args(),
                                approved=True, approval_ref="approval-1", idempotency_key="idem-1")


def test_wrong_approved_arguments_are_rejected():
    s = db(); seed(s, approval_args={"reference":"other","currency":"YER","lines":[]})
    with pytest.raises(HUSRuntimeError, match="approval evidence"):
        execute_compiled_action(s, 1, "actor-1", "c1", "commerce.sales.create", args(),
                                approved=True, approval_ref="approval-1", idempotency_key="idem-1")


def test_approval_run_actor_must_match_execution_actor():
    s = db(); seed(s)
    run = s.get(AIRun, "run-1")
    run.actor_id = "different-actor"
    s.commit()
    with pytest.raises(HUSRuntimeError, match="approval evidence"):
        execute_compiled_action(s, 1, "actor-1", "c1", "commerce.sales.create", args(),
                                approved=True, approval_ref="approval-1", idempotency_key="idem-1")


def test_approval_run_must_belong_to_same_tenant():
    s = db(); seed(s)
    other = Tenant(id=2, name="Other")
    s.add(other)
    run = s.get(AIRun, "run-1")
    run.tenant_id = 2
    s.commit()
    with pytest.raises(HUSRuntimeError, match="approval evidence"):
        execute_compiled_action(s, 1, "actor-1", "c1", "commerce.sales.create", args(),
                                approved=True, approval_ref="approval-1", idempotency_key="idem-1")


def test_successful_execution_binds_trace_to_approval_run():
    s = db(); seed(s)
    runtime = SovereignRuntime(s)
    runtime.configure_approval_verifier(lambda db, ctx: True)
    runtime.register_mutation_handler(
        "commerce.sales.create",
        lambda db, ctx, arguments: {"synthetic": True, "reference": arguments["reference"]},
    )
    from app.hus.runtime import RuntimeContext
    ctx = RuntimeContext(
        tenant_id=1, actor_id="actor-1", compilation_id="c1",
        plan_hash="p" * 64, step_id="w.create",
        action="commerce.sales.create", approval_ref="approval-1",
        idempotency_key=None,
    )
    result = runtime.execute(ctx, {"reference":"trace-test"}, idempotency_key="trace-idem-1", approved=True)
    assert result.status == "completed"
    events = s.scalars(select(AITraceEvent).where(AITraceEvent.run_id == "run-1").order_by(AITraceEvent.created_at)).all()
    assert [e.event_type for e in events[-4:]] == [
        "HUS_EXECUTION_STARTED",
        "HUS_EXECUTION_OBSERVED",
        "HUS_EXECUTION_VERIFIED",
        "HUS_EXECUTION_EVIDENCE",
    ]
    execution = s.get(HUSExecutionRecord, result.execution_id)
    assert execution.output_json["verification"]["status"] == "PASS"
    assert execution.output_json["evidence"]["execution_id"] == result.execution_id


def test_idempotency_key_cannot_replay_different_arguments():
    s = db()
    from app.hus.runtime import RuntimeContext
    runtime = SovereignRuntime(s)
    runtime.configure_approval_verifier(lambda db, ctx: True)
    runtime.register_mutation_handler(
        "commerce.sales.create",
        lambda db, ctx, arguments: {"synthetic": True},
    )
    ctx = RuntimeContext(
        tenant_id=1, actor_id="actor-1", compilation_id="c1",
        plan_hash="p" * 64, step_id="w.create",
        action="commerce.sales.create", approval_ref="approval-1",
        idempotency_key=None,
    )
    first = runtime.execute(ctx, {"reference":"same"}, idempotency_key="idem-1", approved=True)
    assert first.status == "completed"
    replay = runtime.execute(ctx, {"reference":"same"}, idempotency_key="idem-1", approved=True)
    assert replay.replayed is True
    with pytest.raises(HUSRuntimeError, match="different arguments"):
        runtime.execute(ctx, {"reference":"different"}, idempotency_key="idem-1", approved=True)
