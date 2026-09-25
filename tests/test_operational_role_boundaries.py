import os
import time

from app.core.security.jwt import encode_hs256
from tests.test_api import setup_client, teardown


def test_operational_mutations_require_owner_or_admin():
    client, Factory, _ = setup_client()
    try:
        with Factory() as db:
            from app.core.models.core import User, TenantMembership
            db.add(User(id="u2", email="member@example.com", active=True))
            db.add(TenantMembership(user_id="u2", tenant_id=1, role="member", active=True))
            db.commit()

        token = encode_hs256(
            {"sub": "u2", "tenant_id": 1, "exp": int(time.time()) + 3600},
            os.environ["JWT_SECRET"],
        )
        headers = {"Authorization": f"Bearer {token}"}

        assert client.post("/api/v1/payments/intents", headers=headers, json={
            "reference": "ROLE-PAY-1", "provider": "wallet", "amount": "10",
            "currency": "YER", "market_id": 1, "rail": "wallet",
        }).status_code == 403

        assert client.post("/api/v1/logistics/shipments", headers=headers, json={
            "order_id": 1, "reference": "ROLE-SHP-1", "origin_warehouse_id": "wh-a",
            "destination": "Aden", "carrier": "local", "currency": "YER",
        }).status_code == 403

        assert client.post("/api/v1/documents", headers=headers, json={
            "document_type": "invoice", "reference": "ROLE-DOC-1", "title": "Role boundary",
        }).status_code == 403

        assert client.post("/api/v1/carriers", headers=headers, json={
            "code": "role-carrier", "name": "Role Carrier",
        }).status_code == 403
    finally:
        teardown()
