import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.governance import Role, PermissionRecord, RolePermission, MembershipRole
from app.core.security.jwt import encode_hs256, decode_hs256, InvalidToken
from app.core.security.context import build_context, TenantAccessDenied
from app.engines.identity.runtime import resolve_active_context
from app.core.governance.rbac import permissions_for_membership, require_permission
from app.core.governance.policy import PolicyDenied

SECRET = "x" * 32

def test_jwt_signature_and_expiry_are_verified():
    token = encode_hs256({"sub": "u7", "tenant_id": 3, "exp": 2000}, SECRET)
    claims = decode_hs256(token, SECRET, now=1000)
    assert claims.sub == "u7"
    assert claims.tenant_id == 3
    with pytest.raises(InvalidToken):
        decode_hs256(token, "y" * 32, now=1000)
    with pytest.raises(InvalidToken):
        decode_hs256(token, SECRET, now=2000)

def test_tenant_claim_cannot_be_overridden_by_request():
    claims = decode_hs256(
        encode_hs256({"sub": "u7", "tenant_id": 3, "exp": 2000}, SECRET),
        SECRET, now=1000
    )
    with pytest.raises(TenantAccessDenied):
        build_context(claims, requested_tenant_id=4)

def test_database_membership_is_required():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine)
    with Factory() as s:
        t = Tenant(name="A", status="active")
        u = User(id="u7", email="u@example.com", active=True)
        s.add_all([t, u]); s.flush()
        with pytest.raises(TenantAccessDenied):
            resolve_active_context(s, str(u.id), t.id)
        m = TenantMembership(user_id=u.id, tenant_id=t.id, active=True)
        seller = Role(code="admin", name="Administrator")
        s.add_all([m, seller]); s.flush()
        s.add(MembershipRole(membership_id=m.id, role_id=seller.id)); s.commit()
        ctx = resolve_active_context(s, str(u.id), t.id)
        assert ctx.membership_id == m.id
        assert ctx.role == "admin"

        # Legacy memberships remain compatible when no normalized role row exists.
        # The uniqueness rule prevents a second membership for the same tenant;
        # verify the fallback on the existing membership after removing role links.
        s.query(MembershipRole).filter(MembershipRole.membership_id == m.id).delete()
        m.role = "owner"
        s.commit()
        ctx = resolve_active_context(s, str(u.id), t.id)
        assert ctx.role == "owner"

def test_rbac_is_membership_scoped():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine)
    with Factory() as s:
        t = Tenant(name="A", status="active")
        u = User(id="u7", email="u@example.com", active=True)
        s.add_all([t, u]); s.flush()
        m = TenantMembership(user_id=u.id, tenant_id=t.id, active=True)
        role = Role(code="manager", name="Manager")
        perm = PermissionRecord(code="ledger.post", name="Post ledger")
        s.add_all([m, role, perm]); s.flush()
        s.add(RolePermission(role_id=role.id, permission_id=perm.id))
        s.add(MembershipRole(membership_id=m.id, role_id=role.id))
        s.commit()
        assert "ledger.post" in permissions_for_membership(s, m.id)
        require_permission(s, m.id, "ledger.post")
        with pytest.raises(PolicyDenied):
            require_permission(s, m.id, "tenant.delete")


def test_oidc_state_is_signed_and_expires():
    from app.core.security.oidc import OIDCSettings, make_state, verify_state, extract_nonce
    settings = OIDCSettings("client", "https://issuer.example", "secret", "https://app.example/callback", "s" * 32)
    state = make_state(settings, now=1000)
    assert extract_nonce(state)
    assert verify_state(settings, state, now=1001)
    assert not verify_state(settings, state[:-1] + ("A" if state[-1] != "A" else "B"), now=1001)
    assert not verify_state(settings, state, now=1601)


def test_oidc_authorization_url_is_provider_derived():
    from app.core.security.oidc import OIDCSettings, authorization_url
    settings = OIDCSettings("client", "https://issuer.example", "secret", "https://app.example/callback", "s" * 32)
    url = authorization_url(settings, {"authorization_endpoint": "https://issuer.example/authorize"}, "state", "nonce")
    assert url.startswith("https://issuer.example/authorize?")
    assert "client_id=client" in url and "response_type=code" in url and "nonce=nonce" in url
