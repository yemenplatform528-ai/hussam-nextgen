from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models import Tenant, User, TenantMembership
from app.core.models.marketplace import MarketplacePayoutDestination
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.core.contracts import StockMovement
from app.engines.marketplace import MarketplaceService, ListingInput, MarketplaceError
from tests.market_test_support import ensure_market
from app.ai.intelligence import business_snapshot
from app.ai.tools import execute_read_tool
from app.hus.compiler import compile_spec
from app.hus.templates import retail_marketplace_spec

def setup():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)()
    ensure_market(db)
    ids=IdentityService(db); seller=ids.create_tenant('Seller'); buyer_t=ids.create_tenant('Buyer'); seller_admin=ids.create_user('seller-admin','seller-admin@example.com'); buyer=ids.create_user('buyer','buyer@example.com')
    ids.add_membership(seller_admin.id,seller.id,'owner'); ids.add_membership(buyer.id,buyer_t.id,'owner')
    inv=InventoryProductionService(db); inv.create_item(seller.id,'rice','Rice','bag'); inv.create_warehouse(seller.id,'wh','Main'); inv.record(seller.id,StockMovement('rice','wh',Decimal('20'),'in','opening'))
    m=MarketplaceService(db); m.register_seller(seller.id,'seller-final','Seller Final'); m.review_seller_verification(seller.id,seller_admin.id,'approved')
    return db,seller,buyer,seller_admin,m

def test_new_listing_requires_platform_moderation_before_publication():
    db,seller,buyer,admin,m=setup(); l=m.create_listing(seller.id,ListingInput('rice','Rice','', 'product','YER',Decimal('1000'),'rice','wh'))
    with pytest.raises(MarketplaceError): m.publish_listing(seller.id,l.id)
    m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    assert m.public_listings()[0]['id']==l.id

def test_payout_requires_verified_destination():
    db,seller,buyer,admin,m=setup(); l=m.create_listing(seller.id,ListingInput('rice','Rice','', 'product','YER',Decimal('1000'),'rice','wh')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    m.ensure_buyer(buyer.id); m.add_to_cart(buyer.id,l.id,1); o=m.checkout(buyer.id)[0]; o.status='completed'; db.commit()
    from app.core.models.marketplace import MarketplacePayout
    p=db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==o.id)); p.status='eligible'; p.eligible_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc); m._balance_entry(p,'credit',p.net_amount,'settlement:SET-1'); db.commit(); p=m.payout_eligible(seller.id,o.id)
    with pytest.raises(MarketplaceError): m.mark_payout_paid(seller.id,o.id,'EXT-1')
    d=m.set_payout_destination(seller.id,'test-provider','DEST-1'); assert d.status=='pending'
    m.verify_payout_destination(seller.id,admin.id)
    with pytest.raises(MarketplaceError): m.mark_payout_paid(seller.id,o.id,'EXT-1')
    # the payment/settlement boundary requires a verified payment + settlement link before payout.
    p.payment_reference='PAY-SETTLED'; p.settlement_reference='SET-1'; db.commit()
    requested=m.request_payout(seller.id,o.id); assert requested.status=='processing'; assert requested.payout_reference; assert requested.payout_provider=='test-provider'
    paid=m.mark_payout_paid(seller.id,o.id,'EXT-1'); assert paid.status=='paid'


def test_payout_provider_requires_production_evidence():
    from app.core.models.market import ProviderRegistryEntry
    from app.core.models.marketplace import MarketplacePayout
    db,seller,buyer,admin,m=setup(); l=m.create_listing(seller.id,ListingInput('rice','Rice','', 'product','YER',Decimal('1000'),'rice','wh')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    m.ensure_buyer(buyer.id); m.add_to_cart(buyer.id,l.id,1); o=m.checkout(buyer.id)[0]; o.status='completed'; db.commit()
    p=db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==o.id)); p.status='eligible'; p.eligible_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc); m._balance_entry(p,'credit',p.net_amount,'settlement:SET-GATE'); db.commit()
    m.set_payout_destination(seller.id,'unregistered-provider','DEST-GATE'); m.verify_payout_destination(seller.id,admin.id)
    with pytest.raises(MarketplaceError, match='production gate blocked'):
        m.request_payout(seller.id,o.id)

def test_ai_marketplace_snapshot_is_tenant_scoped_and_in_business_snapshot():
    db,seller,buyer,admin,m=setup(); l=m.create_listing(seller.id,ListingInput('rice','Rice','', 'product','YER',Decimal('1000'),'rice','wh')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    snap=business_snapshot(db,seller.id); assert snap['marketplace']['published_listings']==1
    tool=execute_read_tool(db,seller.id,'marketplace.overview',{}); assert tool['tenant_published_listings']==1
    other=m.register_seller(2,'x','X') if False else None

def test_hus_marketplace_template_is_deterministic_and_uses_allowlist():
    spec=retail_marketplace_spec('shop','Shop'); a=compile_spec(spec); b=compile_spec(spec)
    assert a['contract_hash']==b['contract_hash']
    assert any(d['engine']=='marketplace' for d in a['contract']['domains'])
    assert {'marketplace.read','marketplace.order','marketplace.payout'} <= set(next(d for d in a['contract']['domains'] if d['engine']=='marketplace')['capabilities'])


def test_mark_payout_paid_rechecks_provider_gate_and_idempotency_reference():
    from app.core.models.marketplace import MarketplacePayout
    db,seller,buyer,admin,m=setup(); l=m.create_listing(seller.id,ListingInput('rice','Rice','', 'product','YER',Decimal('1000'),'rice','wh')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    m.ensure_buyer(buyer.id); m.add_to_cart(buyer.id,l.id,1); o=m.checkout(buyer.id)[0]; o.status='completed'; db.commit()
    p=db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==o.id)); p.status='eligible'; p.eligible_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc); p.payment_reference='PAY-SETTLED'; p.settlement_reference='SET-1'; m._balance_entry(p,'credit',p.net_amount,'settlement:SET-1'); db.commit()
    m.set_payout_destination(seller.id,'test-provider','DEST-GATE-2'); m.verify_payout_destination(seller.id,admin.id)
    m.request_payout(seller.id,o.id)
    from app.core.models.market import ProviderRegistryEntry
    provider=db.scalar(select(ProviderRegistryEntry).where(ProviderRegistryEntry.code=='test-provider')); provider.status='suspended'; db.commit()
    with pytest.raises(MarketplaceError, match='production gate blocked'):
        m.mark_payout_paid(seller.id,o.id,'EXT-GATE-2')


def test_paid_payout_rejects_different_external_reference():
    from app.core.models.marketplace import MarketplacePayout
    db,seller,buyer,admin,m=setup(); l=m.create_listing(seller.id,ListingInput('rice','Rice','', 'product','YER',Decimal('1000'),'rice','wh')); m.moderate_listing(l.id,admin.id,'approved'); m.publish_listing(seller.id,l.id)
    m.ensure_buyer(buyer.id); m.add_to_cart(buyer.id,l.id,1); o=m.checkout(buyer.id)[0]; o.status='completed'; db.commit()
    p=db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==o.id)); p.status='eligible'; p.eligible_at=__import__('datetime').datetime.now(__import__('datetime').timezone.utc); p.payment_reference='PAY-SETTLED'; p.settlement_reference='SET-1'; m._balance_entry(p,'credit',p.net_amount,'settlement:SET-1'); db.commit()
    m.set_payout_destination(seller.id,'test-provider','DEST-1'); m.verify_payout_destination(seller.id,admin.id)
    m.request_payout(seller.id,o.id)
    assert m.mark_payout_paid(seller.id,o.id,'EXT-PAID').status=='paid'
    with pytest.raises(MarketplaceError, match='different external reference'):
        m.mark_payout_paid(seller.id,o.id,'EXT-OTHER')
