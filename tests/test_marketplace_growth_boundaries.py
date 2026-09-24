from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.marketplace_growth import TransferIn, transfer
from app.core.models.marketplace_growth import MarketplaceInventoryTransfer, MarketplaceWarehouse
from app.core.models.core import Tenant
from app.core.persistence import Base


def setup_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with Factory() as db:
        db.add_all([
            Tenant(id=1, name="Seller A", status="active"),
            Tenant(id=2, name="Seller B", status="active"),
        ])
        db.add_all([
            MarketplaceWarehouse(owner_tenant_id=1, code="A-1", name="A warehouse", warehouse_type="seller"),
            MarketplaceWarehouse(owner_tenant_id=1, code="A-2", name="A warehouse 2", warehouse_type="seller"),
            MarketplaceWarehouse(owner_tenant_id=2, code="B-1", name="B warehouse", warehouse_type="seller"),
        ])
        db.commit()
    return Factory


def ctx(tenant_id):
    return SimpleNamespace(role="owner", tenant_id=tenant_id)


def test_inventory_transfer_requires_both_warehouses_in_current_tenant():
    Factory = setup_db()
    with Factory() as db:
        with pytest.raises(ValueError, match="warehouses not found for seller"):
            transfer(
                TransferIn(from_warehouse_id=1, to_warehouse_id=3, quantity=1, reference="cross"),
                ctx(1),
                db,
            )
        transfer(
            TransferIn(from_warehouse_id=1, to_warehouse_id=2, quantity=2, reference="own"),
            ctx(1),
            db,
        )
        row = db.scalar(select(MarketplaceInventoryTransfer).where(MarketplaceInventoryTransfer.reference == "own"))
        assert row is not None
        assert row.seller_tenant_id == 1
