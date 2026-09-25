import os, time
from app.core.models.core import User, TenantMembership
from app.core.models.ai_hus import AIToolDefinition, AIRun, AIAction
from app.core.security.jwt import encode_hs256
from tests.test_api import setup_client, teardown


def test_ai_action_approval_requires_owner_or_admin():
    client, Factory, _ = setup_client()
    try:
        with Factory() as db:
            db.add(User(id="u2", email="member@example.com", active=True))
            db.add(TenantMembership(user_id="u2", tenant_id=1, role="member", active=True))
            db.add(AIToolDefinition(tenant_id=1, code="inventory.write", name="Inventory Write", description="Mutation", risk="mutation", input_schema={}, enabled=True))
            db.add(AIRun(id="run-1", tenant_id=1, actor_id="u1", purpose="test", status="waiting_approval", input_hash="h"*64))
            db.add(AIAction(id="action-1", tenant_id=1, run_id="run-1", tool_code="inventory.write", risk="mutation", arguments={}, status="pending_approval"))
            db.commit()
        token = encode_hs256({"sub":"u2","tenant_id":1,"exp":int(time.time())+3600}, os.environ["JWT_SECRET"])
        response = client.post("/api/v1/ai/actions/action-1/approve", headers={"Authorization":f"Bearer {token}"})
        assert response.status_code == 403
    finally:
        teardown()
