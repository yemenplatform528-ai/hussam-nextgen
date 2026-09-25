import os
import time
from app.core.models.core import User, TenantMembership
from app.core.security.jwt import encode_hs256
from tests.test_api import setup_client, teardown


def test_finance_mutations_require_owner_or_admin():
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

        journal = client.post(
            "/api/v1/finance/journals",
            headers=headers,
            json={
                "reference": "SEC-ROLE-1",
                "currency": "YER",
                "posting_date": "2026-09-25",
                "lines": [
                    {"account_id": "cash", "debit": "1", "credit": "0"},
                    {"account_id": "sales", "debit": "0", "credit": "1"},
                ],
            },
        )
        assert journal.status_code == 403

        account = client.post(
            "/api/v1/finance/accounts",
            headers=headers,
            json={
                "code": "member-forbidden",
                "name": "Member Forbidden",
                "account_type": "asset",
                "currency": "YER",
            },
        )
        assert account.status_code == 403

        reconcile = client.post(
            "/api/v1/finance/reconciliation/control",
            headers=headers,
            json={
                "account_id": "cash",
                "currency": "YER",
                "expected_balance": "0",
            },
        )
        assert reconcile.status_code == 403
    finally:
        teardown()
