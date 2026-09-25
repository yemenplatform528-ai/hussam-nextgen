import os, time
from app.core.models.core import User, TenantMembership
from app.core.security.jwt import encode_hs256
from tests.test_api import setup_client, teardown


def test_ai_hus_developer_mutations_require_owner_or_admin():
    client, Factory, owner_token = setup_client()
    try:
        with Factory() as db:
            db.add(User(id="u2", email="member@example.com", active=True))
            db.add(TenantMembership(user_id="u2", tenant_id=1, role="member", active=True))
            db.commit()
        member_token = encode_hs256(
            {"sub": "u2", "tenant_id": 1, "exp": int(time.time()) + 3600},
            os.environ["JWT_SECRET"],
        )
        h = {"Authorization": f"Bearer {member_token}"}
        spec = {
            "spec_version": "1.0",
            "organization": {"code": "demo", "name": "Demo"},
            "domains": [{"code": "retail", "name": "Retail", "engine": "retail"}],
            "workflows": [{"code": "sale", "trigger": "sale.created", "steps": []}],
        }
        assert client.post("/api/v1/hus/compile", headers=h, json={"spec": spec}).status_code == 403
        assert client.post(
            "/api/v1/ai/tools",
            headers=h,
            json={"code": "inventory.read", "name": "Inventory Read", "description": "Read inventory", "risk": "read", "input_schema": {}},
        ).status_code == 403
    finally:
        teardown()
