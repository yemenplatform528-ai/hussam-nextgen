from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import pytest

from app.core.models.ai_hus import AIAction, AIRun, HUSCompilation
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.oidc import OIDCIdentity
from app.core.models.amazon_completion import HUSExecutionRecord
from app.core.persistence import Base
from app.hus.approval import verify_ai_action_approval
from app.hus.runtime import RuntimeContext, SovereignRuntime, HUSRuntimeError, _hash


def db():
    e = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(e)
    return sessionmaker(e, expire_on_commit=False)()


def seed(s):
    s.add_all([
        Tenant(id=1, name="Test"),
        User(id="owner-1", email="owner@example.com", active=True),
        TenantMembership(user_id="owner-1", tenant_id=1, role="owner", active=True),
        OIDCIdentity(user_id="owner-1", issuer="https://issuer.example", subject="oidc-owner-1"),
        AIRun(id="run-1", tenant_id=1, actor_id="actor-1", purpose="test", status="approved", input_hash="h" * 64),
        HUSCompilation(
            id="c1", tenant_id=1, actor_id="owner-1", spec_version="1.0",
            source_hash="s" * 64, contract_hash="p" * 64, status="active",
            contract={"execution_plan":{"workflows":[{"code":"w","steps":[
                {"id":"w.create","action":{"engine":"commerce","capability":"sales.create"},"risk":"mutation","idempotency_required":True},
                {"id":"w.other","action":{"engine":"commerce","capability":"sales.update"},"risk":"mutation","idempotency_required":True},
            ]}]}}
        ),
    ])
    arguments={"reference":"bound","currency":"YER","lines":[]}
    s.add(AIAction(
        id="approval-1", tenant_id=1, run_id="run-1", tool_code="commerce.sales.create",
        risk="mutation", arguments=arguments, status="approved", approved_by="owner-1",
        approval_provenance={"auth_source":"oidc","oidc_issuer":"https://issuer.example","oidc_subject":"oidc-owner-1",
            "execution_binding":{"compilation_id":"c1","step_id":"w.create","plan_hash":"p"*64,
                "action":"commerce.sales.create","idempotency_key":"idem-1","arguments_hash":_hash(arguments)}}
    ))
    s.commit()


def context(**overrides):
    data=dict(tenant_id=1, actor_id="actor-1", compilation_id="c1", plan_hash="p"*64,
              step_id="w.create", action="commerce.sales.create", approval_ref="approval-1",
              idempotency_key="idem-1", arguments_hash=_hash({"reference":"bound","currency":"YER","lines":[]}))
    data.update(overrides)
    return RuntimeContext(**data)


@pytest.mark.parametrize("field,value", [
    ("step_id","w.other"),
    ("plan_hash","x"*64),
    ("idempotency_key","idem-2"),
    ("action","commerce.sales.update"),
])
def test_approval_cannot_cross_execution_identity(field, value):
    s=db(); seed(s)
    assert verify_ai_action_approval(s, context(**{field:value})) is False


def test_idempotency_collision_cannot_cross_step():
    s=db(); seed(s)
    runtime=SovereignRuntime(s)
    runtime.configure_approval_verifier(lambda db, ctx: True)
    runtime.register_mutation_handler("commerce.sales.create", lambda db, ctx, args: {"ok":True})
    first=runtime.execute(context(), {"reference":"bound","currency":"YER","lines":[]}, approved=True)
    assert first.status=="completed"

    other=RuntimeContext(tenant_id=1,actor_id="actor-1",compilation_id="c1",plan_hash="p"*64,
                          step_id="w.other",action="commerce.sales.create",approval_ref="approval-1",
                          idempotency_key="idem-1")
    runtime.register_mutation_handler("commerce.sales.create", lambda db, ctx, args: {"ok":"same-action"})
    with pytest.raises(HUSRuntimeError, match="different execution intent"):
        runtime.execute(other, {"reference":"bound","currency":"YER","lines":[]}, approved=True)


def test_duplicate_idempotency_with_same_intent_replays():
    s=db(); seed(s)
    runtime=SovereignRuntime(s)
    runtime.configure_approval_verifier(lambda db, ctx: True)
    runtime.register_mutation_handler("commerce.sales.create", lambda db, ctx, args: {"ok":True})
    first=runtime.execute(context(), {"reference":"bound","currency":"YER","lines":[]}, approved=True)
    replay=runtime.execute(context(), {"reference":"bound","currency":"YER","lines":[]}, approved=True)
    assert first.status=="completed"
    assert replay.replayed is True
    assert len(s.scalars(select(HUSExecutionRecord)).all()) == 1
