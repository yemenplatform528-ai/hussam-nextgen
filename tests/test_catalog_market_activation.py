from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import pytest
from app.core.persistence import Base
from app.core.models.market import MarketContext
from app.engines.catalog import CatalogService, ProductInput, CatalogError
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.engines.marketplace import MarketplaceService


def make_db():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e)
    return sessionmaker(e,expire_on_commit=False)()


def setup_seller(db):
    ids=IdentityService(db); seller=ids.create_tenant('Seller'); user=ids.create_user('seller','seller@example.com'); ids.add_membership(user.id,seller.id,'owner')
    inv=InventoryProductionService(db); inv.create_item(seller.id,'rice','Rice','bag'); inv.create_warehouse(seller.id,'wh','Main')
    m=MarketplaceService(db); m.register_seller(seller.id,'seller','Seller'); m.review_seller_verification(seller.id,user.id,'approved')
    return seller


def test_catalog_does_not_autocreate_market():
    db=make_db(); seller=setup_seller(db); c=CatalogService(db)
    with pytest.raises(CatalogError, match='market context is required'):
        c.create_product(seller.id, ProductInput('x','X'))
    assert db.scalars(select(MarketContext)).all() == []
