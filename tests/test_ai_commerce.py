from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.persistence import Base
from app.core.models.core import Tenant, User, TenantMembership
from app.core.models.marketplace import MarketplaceListing, MarketplaceCustomerOrder
from app.ai.commerce import customer_context, customer_recommendations, seller_intelligence, create_commerce_proposal

def db_session():
    e=create_engine('sqlite+pysqlite:///:memory:',future=True)
    Base.metadata.create_all(e)
    return sessionmaker(e,expire_on_commit=False)()

def seed(db):
    db.add_all([Tenant(id=1,name='T1',status='active'),Tenant(id=2,name='T2',status='active'),
                User(id='u1',email='u1@example.com',active=True),User(id='u2',email='u2@example.com',active=True),
                TenantMembership(user_id='u1',tenant_id=1,role='admin',active=True),TenantMembership(user_id='u2',tenant_id=2,role='admin',active=True)])
    db.commit()

def test_customer_recommendations_are_public_and_tenant_safe():
    db=db_session(); seed(db)
    db.add_all([
        MarketplaceListing(id=1,seller_tenant_id=1,market_id=None,slug='phone',title='Yemen Phone',description='smart phone',listing_type='product',currency='YER',unit_price=100,status='published',stock_policy='managed',item_id='item-1',warehouse_id='wh-1',moderation_status='approved'),
        MarketplaceListing(id=2,seller_tenant_id=2,market_id=None,slug='hidden',title='Hidden',description='smart phone',listing_type='product',currency='YER',unit_price=200,status='draft',stock_policy='managed',item_id='item-1',warehouse_id='wh-1',moderation_status='pending')])
    db.commit()
    r=customer_recommendations(db,1,'u1','phone')
    assert [x['id'] for x in r['items']] == [1]
    assert r['grounding']['live_records'] is True

def test_customer_context_only_returns_users_orders():
    db=db_session(); seed(db)
    db.add_all([MarketplaceCustomerOrder(id=1,reference='A',buyer_user_id='u1',currency='YER',subtotal=10,shipping_fee=0,total=10,status='paid'),
                MarketplaceCustomerOrder(id=2,reference='B',buyer_user_id='u2',currency='YER',subtotal=20,shipping_fee=0,total=20,status='paid')]); db.commit()
    x=customer_context(db,1,'u1'); assert len(x['orders'])==1 and x['orders'][0]['reference']=='A'

def test_seller_intelligence_and_proposal_do_not_execute_mutation():
    db=db_session(); seed(db)
    db.add(MarketplaceListing(id=1,seller_tenant_id=1,slug='x',title='X',description='',listing_type='product',currency='YER',unit_price=1,status='draft',stock_policy='managed',item_id='item-1',warehouse_id='wh-1',moderation_status='pending')); db.commit()
    info=seller_intelligence(db,1); assert any(x['kind']=='publication_gap' for x in info['opportunities'])
    out=create_commerce_proposal(db,1,'u1','improve listings')
    assert out['proposal']['status']=='pending_approval'
    assert db.query(MarketplaceListing).filter_by(id=1).one().status=='draft'
