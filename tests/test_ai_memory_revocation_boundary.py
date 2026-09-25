import os, time
from app.core.models.core import User, TenantMembership
from app.core.models.ai_foundation import AIMemoryRecord
from app.core.security.jwt import encode_hs256
from tests.test_api import setup_client, teardown


def test_ai_memory_revoke_requires_owner_or_admin():
    client, Factory, _ = setup_client()
    try:
        with Factory() as db:
            db.add(User(id="u2", email="member@example.com", active=True))
            db.add(TenantMembership(user_id="u2", tenant_id=1, role="member", active=True))
            db.add(AIMemoryRecord(id="m1", tenant_id=1, owner_id="u1", memory_type="user_preference", key="locale", value={"value":"ar"}, source="user", trust="verified"))
            db.commit()
        token = encode_hs256({"sub":"u2","tenant_id":1,"exp":int(time.time())+3600}, os.environ["JWT_SECRET"])
        response = client.post("/api/v1/ai/foundation/memory/m1/revoke", headers={"Authorization":f"Bearer {token}"})
        assert response.status_code == 403
    finally:
        teardown()
