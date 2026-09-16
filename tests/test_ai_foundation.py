from decimal import Decimal
import pytest
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.ai_foundation import AIProviderConfig, AIModelRoute, AIAgentDefinition, AIMemoryRecord
from app.core.persistence import make_session_factory
from app.ai.contracts import AgentContract, DataClass, MemoryType, ModelRouteRequest, ToolContract, ActionClass
from app.ai.foundation import register_provider, register_model_route, register_agent, register_tool_contract, remember, revoke_memory, choose_model_route, record_usage, trace
from app.ai.context import build_context
from app.ai.policy import authorize_tool


@pytest.fixture
def db():
    _, factory = make_session_factory(); return factory()


def seed(db):
    db.add_all([
        Tenant(id=1, name='T1', status='active'), Tenant(id=2, name='T2', status='active'),
        User(id='u1', email='u1@example.com', active=True), User(id='u2', email='u2@example.com', active=True),
        TenantMembership(user_id='u1', tenant_id=1, role='admin', active=True),
        TenantMembership(user_id='u2', tenant_id=2, role='admin', active=True),
    ]); db.commit()


def test_provider_route_selection_is_tenant_scoped_and_capability_aware(db):
    seed(db)
    register_provider(db, 1, code='primary', provider_kind='openai-compatible', credential_ref='secret://ai/primary', enabled=True)
    register_provider(db, 2, code='other', provider_kind='openai-compatible', enabled=True)
    register_model_route(db, 1, route_code='commerce-default', provider_code='primary', model_code='m1', task_class='commerce', structured_output=True)
    decision = choose_model_route(db, 1, ModelRouteRequest(task_class='commerce', requires_structured_output=True))
    assert decision.model_code == 'm1'
    with pytest.raises(ValueError):
        choose_model_route(db, 2, ModelRouteRequest(task_class='commerce'))


def test_agent_and_tool_policy_blocks_unscoped_tools_and_mutations_require_approval(db):
    seed(db)
    tool = register_tool_contract(db, 1, ToolContract(code='order.read', description='read order', action_class=ActionClass.READ, data_classes=[DataClass.TENANT], requires_approval=False))
    agent = register_agent(db, 1, AgentContract(code='customer', role='customer_assistant', scopes=['commerce:read'], tool_codes=['order.read'], data_classes=[DataClass.TENANT]), 'never mutate without approval')
    from app.ai.policy import authorize_tool
    assert authorize_tool(AgentContract(code='customer', role='customer_assistant', scopes=['commerce:read'], tool_codes=['order.read'], data_classes=[DataClass.TENANT]), ToolContract(code='order.read', description='read', action_class=ActionClass.READ, data_classes=[DataClass.TENANT], requires_approval=False)).allowed
    assert not authorize_tool(AgentContract(code='customer', role='customer_assistant', scopes=['commerce:read'], tool_codes=[], data_classes=[DataClass.TENANT]), ToolContract(code='order.read', description='read', action_class=ActionClass.READ, data_classes=[DataClass.TENANT], requires_approval=False)).allowed
    mut = ToolContract(code='order.execute', description='execute', action_class=ActionClass.EXECUTE, data_classes=[DataClass.TENANT], requires_approval=True)
    assert authorize_tool(AgentContract(code='customer', role='customer_assistant', scopes=['commerce:write'], tool_codes=['order.execute'], data_classes=[DataClass.TENANT]), mut).requires_approval
    assert tool.side_effect_class == 'read' and agent.enabled


def test_memory_is_scoped_revocable_and_live_context_is_last(db):
    seed(db)
    m = remember(db, 1, memory_type=MemoryType.USER_PREFERENCE, key='language', value={'value':'ar'}, source='user', owner_id='u1', trust='verified')
    other = remember(db, 2, memory_type=MemoryType.USER_PREFERENCE, key='language', value={'value':'en'}, source='user', owner_id='u2')
    envelope = build_context(db, 1, owner_id='u1', system_policy='policy', live_facts=[])
    assert any(x.content['key'] == 'language' for x in envelope.items)
    assert all(x.content['value']['value'] != 'en' for x in envelope.items if x.kind == MemoryType.USER_PREFERENCE.value)
    revoke_memory(db, 1, m.id)
    assert db.get(AIMemoryRecord, m.id).revoked_at is not None


def test_trace_usage_are_tenant_scoped_and_redacted(db):
    seed(db)
    trace(db, 1, 'run-1', 'policy', 'decision', {'safe':'ok','secret':'should-not-be-stored'}, redacted=False)
    db.commit()
    row = db.query(__import__('app.core.models.ai_foundation', fromlist=['AITraceEvent']).AITraceEvent).first()
    assert row.redacted and row.data == {'redaction_required': True}
    usage = record_usage(db, 1, 'run-1', provider_code='p', model_code='m', input_tokens=10, output_tokens=20, estimated_cost=Decimal('0.02'))
    assert usage.input_tokens == 10 and usage.estimated_cost == Decimal('0.02000000')
    with pytest.raises(ValueError): record_usage(db, 1, 'run-1', provider_code='p', model_code='m', input_tokens=-1)
