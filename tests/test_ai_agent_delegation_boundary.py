import os, time
from app.core.models.core import User, TenantMembership
from app.core.security.jwt import encode_hs256
from tests.test_api import setup_client, teardown


def test_ai_delegation_completion_requires_owner_or_admin():
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
        response = client.post(
            "/api/v1/ai/agents/delegations/nonexistent/complete",
            headers=h,
            json={"status": "spoofed"},
        )
        assert response.status_code == 403
    finally:
        teardown()
