from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models import Tenant, User, TenantMembership

class IdentityError(ValueError): pass

class IdentityService:
    def __init__(self, db: Session): self.db = db
    def create_tenant(self, name: str) -> Tenant:
        if not name.strip(): raise IdentityError("tenant name is required")
        t = Tenant(name=name.strip(), status="active"); self.db.add(t); self.db.commit(); self.db.refresh(t); return t
    def create_user(self, user_id: str, email: str) -> User:
        if not user_id.strip() or "@" not in email: raise IdentityError("valid user id and email are required")
        u = User(id=user_id.strip(), email=email.strip().lower()); self.db.add(u); self.db.commit(); self.db.refresh(u); return u
    def add_membership(self, user_id: str, tenant_id: int, role: str = "user") -> TenantMembership:
        tenant = self.db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "active"))
        user = self.db.get(User, user_id)
        if not tenant or not user or not user.active: raise IdentityError("active user and tenant are required")
        if self.db.scalar(select(TenantMembership).where(TenantMembership.user_id == user_id, TenantMembership.tenant_id == tenant_id)):
            raise IdentityError("membership already exists")
        m = TenantMembership(user_id=user_id, tenant_id=tenant_id, role=role, active=True); self.db.add(m); self.db.commit(); self.db.refresh(m); return m
    def authorize(self, user_id: str, tenant_id: int) -> TenantMembership:
        m = self.db.scalar(select(TenantMembership).where(TenantMembership.user_id == user_id, TenantMembership.tenant_id == tenant_id, TenantMembership.active == True))
        tenant = self.db.scalar(select(Tenant).where(Tenant.id == tenant_id, Tenant.status == "active"))
        if not m or not tenant: raise IdentityError("active membership required")
        return m
