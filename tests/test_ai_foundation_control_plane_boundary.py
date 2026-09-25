import os, time
from app.core.models.core import User, TenantMembership
from app.core.security.jwt import encode_hs256
from tests.test_api import setup_client, teardown


def test_ai_foundation_control_plane_mutations_require_owner_or_admin():
    client, Factory, _ = setup_client()
    try:
        with Factory() as db:
            db.add(User(id="u2", email="member@example.com", active=True))
            db.add(TenantMembership(user_id="u2", tenant_id=1, role="member", active=True))
            db.commit()
        token = encode_hs256(
            {"sub": "u2", "tenant_id": 1, "exp": int(time.time()) + 3600},
            os.environ["JWT_SECRET"],
        )
        h = {"Authorization": f"Bearer {token}"}
        assert client.post(
            "/api/v1/ai/foundation/providers",
            headers=h,
            json={"code": "local", "provider_kind": "local"},
        ).status_code == 403
        assert client.post(
            "/api/v1/ai/foundation/routes",
            headers=h,
            json={"route_code": "default", "provider_code": "local", "model_code": "model", "task_class": "general"},
        ).status_code == 403
        assert client.post(
            "/api/v1/ai/foundation/tools",
            headers=h,
            json={"code": "inventory.read", "description": "Read inventory", "action_class": "read"},
        ).status_code == 403
        assert client.post(
            "/api/v1/ai/foundation/agents",
            headers=h,
            json={"code": "member-agent", "role": "assistant", "scopes": ["read"], "system_policy": "read only"},
        ).status_code == 403
    finally:
        teardown()
