import os
import time
from app.core.models.core import User, TenantMembership
from app.core.security.jwt import encode_hs256
from tests.test_api import setup_client, teardown


def test_backoffice_mutations_require_owner_or_admin():
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
        headers = {"Authorization": f"Bearer {token}"}

        cases = [
            ("/api/v1/retail/customers", {"id": "c1", "name": "Customer"}),
            ("/api/v1/inventory/items", {"id": "item-1", "name": "Item"}),
            ("/api/v1/inventory/warehouses", {"id": "wh-1", "name": "Warehouse"}),
            (
                "/api/v1/sales/orders",
                {
                    "reference": "SO-ROLE-1",
                    "warehouse_id": "wh-1",
                    "currency": "YER",
                    "lines": [{"item_id": "item-1", "quantity": "1", "unit_price": "1"}],
                },
            ),
            ("/api/v1/purchasing/suppliers", {"id": "sup-1", "name": "Supplier"}),
            (
                "/api/v1/workflows/definitions",
                {"code": "role-test", "version": 1, "name": "Role Test", "steps": {}, "active": True},
            ),
        ]
        for path, payload in cases:
            response = client.post(path, headers=headers, json=payload)
            assert response.status_code == 403, (path, response.status_code, response.text)
    finally:
        teardown()
