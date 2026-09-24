from decimal import Decimal
import hashlib
import json
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models import Tenant, User, TenantMembership, InventoryItem, Warehouse, InventoryMovementRecord
from app.core.models.core import IdempotencyRecord
from app.core.models.marketplace import MarketplaceSellerProfile, MarketplaceListing, MarketplaceOrder, MarketplacePayout, MarketplaceReview, MarketplaceDispute, MarketplaceFeeRule
from app.core.models.market import MarketContext, MarketCurrency
from app.engines.marketplace import MarketplaceService, ListingInput, MarketplaceError
from app.engines.identity import IdentityService
from app.engines.inventory.production import InventoryProductionService
from app.core.contracts import StockMovement


def setup():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True); Base.metadata.create_all(e); db=sessionmaker(e,expire_on_commit=False)()
    ids=IdentityService(db); seller=ids.create_tenant('Seller'); buyer_t=ids.create_tenant('Buyer'); buyer=ids.create_user('buyer','buyer@example.com'); seller_user=ids.create_user('seller','seller@example.com'); ids.add_membership(buyer.id,buyer_t.id,'owner'); ids.add_membership(seller_user.id,seller.id,'owner')
    market=MarketContext(code='YE',country_code='YE',name='Yemen',locale='ar-YE',timezone='Asia/Aden',default_currency='YER',status='active'); db.add(market); db.flush(); db.add(MarketCurrency(market_id=market.id,currency='YER',is_default=True))
    db.add(MarketplaceFeeRule(name='Test Default Marketplace Commission',scope='global',commission_bps=500,fixed_fee=Decimal('0'),priority=100,active=True)); db.commit()
    inv=InventoryProductionService(db); inv.create_item(seller.id,'rice','Rice','bag'); inv.create_warehouse(seller.id,'wh','Main'); inv.record(seller.id,StockMovement('rice','wh',Decimal('20'),'in','opening'))
    return db,seller,buyer_t,buyer,seller_user

def test_seller_listing_public_cart_multiseller_checkout_and_payment_boundary():
    db,seller,bt,buyer,su=setup(); m=MarketplaceService(db)
    m.register_seller(seller.id,'seller-one','Seller One'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,ListingInput('rice','Rice 10kg','', 'product','YER',Decimal('1000'),'rice','wh'))
    m.moderate_listing(l.id,su.id,'approved')
    m.publish_listing(seller.id,l.id)
    assert m.public_listings()[0]['seller']['slug']=='seller-one'
    m.add_to_cart(buyer.id,l.id,Decimal('2'))
    orders=m.checkout(buyer.id)
    assert len(orders)==1 and orders[0].subtotal==Decimal('2000.0000') and orders[0].platform_fee==Decimal('100.0000') and orders[0].total==Decimal('2000.0000')
    payout=db.scalar(select(MarketplacePayout).where(MarketplacePayout.marketplace_order_id==orders[0].id)); assert payout.net_amount==Decimal('1900.0000')
    # reserved stock is 2, not consumed until seller fulfills the authoritative SalesOrder.
    from app.engines.inventory.production import InventoryProductionService
    assert InventoryProductionService(db).snapshot(seller.id,'rice','wh').available==Decimal('18.0000')

def test_tenant_boundary_and_order_lifecycle_review_dispute():
    db,seller,bt,buyer,su=setup(); m=MarketplaceService(db); m.register_seller(seller.id,'s2','S2'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,ListingInput('rice','Rice','', 'product','YER',Decimal('500'),'rice','wh')); m.moderate_listing(l.id,su.id,'approved'); m.publish_listing(seller.id,l.id); m.add_to_cart(buyer.id,l.id,1); o=m.checkout(buyer.id)[0]
    with pytest.raises(MarketplaceError): m.mark_paid(bt.id,o.id,'missing')
    with pytest.raises(MarketplaceError): m.create_review(buyer.id,o.id,l.id,5)
    o.status='paid'; db.commit()
    m.open_dispute(buyer.id,o.id,'not_paid','test')
    assert db.scalar(select(MarketplaceDispute).where(MarketplaceDispute.marketplace_order_id==o.id)).status=='open'

def test_service_listing_is_valid_and_stockless():
    db,seller,bt,buyer,su=setup(); m=MarketplaceService(db); m.register_seller(seller.id,'services','Services'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,ListingInput('repair','Repair Service','', 'service','YER',Decimal('3000'))); m.moderate_listing(l.id,su.id,'approved'); m.publish_listing(seller.id,l.id)
    assert m.public_listings()[0]['listing_type']=='service' and m.public_listings()[0]['stock'] is None


def _checkout_hash(user_id, body):
    return hashlib.sha256(json.dumps(
        {'operation': 'marketplace.checkout.v1', 'user_id': user_id, 'body': body},
        sort_keys=True, separators=(',', ':')
    ).encode('utf-8')).hexdigest()


def test_checkout_idempotency_replays_without_creating_duplicate_orders():
    db,seller,bt,buyer,su=setup(); m=MarketplaceService(db)
    m.register_seller(seller.id,'idem-seller','Idempotent Seller'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,ListingInput('idem-rice','Rice','', 'product','YER',Decimal('1000'),'rice','wh'))
    m.moderate_listing(l.id,su.id,'approved'); m.publish_listing(seller.id,l.id); m.add_to_cart(buyer.id,l.id,1)
    body={'shipping_address_id':None,'shipping_fee':0,'payment_method_code':None}
    key='checkout-e2e-001'; request_hash=_checkout_hash(buyer.id,body)
    first=m.checkout(buyer.id,idempotency_key=key,idempotency_tenant_id=bt.id,idempotency_request_hash=request_hash)
    second=m.checkout(buyer.id,idempotency_key=key,idempotency_tenant_id=bt.id,idempotency_request_hash=request_hash)
    assert [o.id for o in second] == [o.id for o in first]
    assert len(db.scalars(select(MarketplaceOrder)).all()) == 1
    record=db.scalar(select(IdempotencyRecord).where(IdempotencyRecord.tenant_id==bt.id,IdempotencyRecord.key==key))
    assert record is not None and json.loads(record.response_json)['order_ids'] == [first[0].id]


def test_checkout_idempotency_key_rejects_different_request():
    db,seller,bt,buyer,su=setup(); m=MarketplaceService(db)
    m.register_seller(seller.id,'idem-seller-2','Idempotent Seller 2'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,ListingInput('idem-rice-2','Rice','', 'product','YER',Decimal('1000'),'rice','wh'))
    m.moderate_listing(l.id,su.id,'approved'); m.publish_listing(seller.id,l.id); m.add_to_cart(buyer.id,l.id,1)
    body={'shipping_address_id':None,'shipping_fee':0,'payment_method_code':None}
    key='checkout-e2e-002'; request_hash=_checkout_hash(buyer.id,body)
    m.checkout(buyer.id,idempotency_key=key,idempotency_tenant_id=bt.id,idempotency_request_hash=request_hash)
    changed=dict(body); changed['payment_method_code']='different'
    with pytest.raises(MarketplaceError, match='different request'):
        m.checkout(buyer.id,idempotency_key=key,idempotency_tenant_id=bt.id,idempotency_request_hash=_checkout_hash(buyer.id,changed))


def test_cart_mutation_lifecycle_replays_without_double_apply():
    db,seller,bt,buyer,su=setup(); m=MarketplaceService(db)
    m.register_seller(seller.id,'lifecycle-seller','Lifecycle Seller'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,ListingInput('life-rice','Lifecycle Rice','', 'product','YER',Decimal('500'),'rice','wh')); m.moderate_listing(l.id,su.id,'approved'); m.publish_listing(seller.id,l.id)

    first=m.add_to_cart(buyer.id,l.id,1,mutation_key='cart-add-001',tenant_id=bt.id)
    replay=m.add_to_cart(buyer.id,l.id,1,mutation_key='cart-add-001',tenant_id=bt.id)
    assert first == replay
    assert first['items'][0]['quantity']=='1.0000'

    record=db.scalar(select(__import__('app.core.models.core',fromlist=['MutationRecord']).MutationRecord).where(
        __import__('app.core.models.core',fromlist=['MutationRecord']).MutationRecord.tenant_id==bt.id,
        __import__('app.core.models.core',fromlist=['MutationRecord']).MutationRecord.mutation_key=='cart-add-001'))
    assert record.state=='confirmed' and record.resource_type=='marketplace_cart'

    with pytest.raises(MarketplaceError, match='different request'):
        m.add_to_cart(buyer.id,l.id,2,mutation_key='cart-add-001',tenant_id=bt.id)


def test_cart_remove_mutation_is_replay_safe():
    db,seller,bt,buyer,su=setup(); m=MarketplaceService(db)
    m.register_seller(seller.id,'remove-seller','Remove Seller'); m.review_seller_verification(seller.id,su.id,'approved')
    l=m.create_listing(seller.id,ListingInput('remove-rice','Remove Rice','', 'product','YER',Decimal('500'),'rice','wh')); m.moderate_listing(l.id,su.id,'approved'); m.publish_listing(seller.id,l.id)
    m.add_to_cart(buyer.id,l.id,1)
    first=m.remove_from_cart(buyer.id,l.id,mutation_key='cart-remove-001',tenant_id=bt.id)
    replay=m.remove_from_cart(buyer.id,l.id,mutation_key='cart-remove-001',tenant_id=bt.id)
    assert first == replay and first['items']==[]
