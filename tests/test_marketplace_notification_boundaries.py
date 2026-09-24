from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.marketplace_growth import NotificationIn, notification
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.marketplace_growth import MarketplaceNotification
from app.core.persistence import Base


def setup_db():
    engine=create_engine("sqlite+pysqlite:///:memory:",future=True,connect_args={"check_same_thread":False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Factory=sessionmaker(bind=engine,expire_on_commit=False,autoflush=False)
    with Factory() as db:
        db.add_all([
            Tenant(id=1,name="Seller",status="active"),
            Tenant(id=2,name="Other",status="active"),
            User(id="seller-user",email="seller@example.test",active=True),
            User(id="same-tenant-user",email="same@example.test",active=True),
            User(id="other-tenant-user",email="other@example.test",active=True),
        ])
        db.add_all([
            TenantMembership(user_id="seller-user",tenant_id=1,role="owner",active=True),
            TenantMembership(user_id="same-tenant-user",tenant_id=1,role="member",active=True),
            TenantMembership(user_id="other-tenant-user",tenant_id=2,role="owner",active=True),
        ])
        db.commit()
    return Factory


def ctx():
    return SimpleNamespace(role="owner",tenant_id=1,user_id="seller-user")


def test_seller_notification_recipient_must_be_in_current_tenant():
    Factory=setup_db()
    with Factory() as db:
        with pytest.raises(ValueError,match="not in seller tenant"):
            notification(
                NotificationIn(recipient_user_id="other-tenant-user",notification_type="order",title="Private"),
                ctx(),db,
            )
        notification(
            NotificationIn(recipient_user_id="same-tenant-user",notification_type="order",title="Private"),
            ctx(),db,
        )
        row=db.scalar(select(MarketplaceNotification).where(MarketplaceNotification.recipient_user_id=="same-tenant-user"))
        assert row is not None and row.tenant_id==1
