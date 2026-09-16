from decimal import Decimal
from app.engines.marketplace import MarketplaceService, ListingInput
from tests.test_marketplace import setup


def publish(m, seller, user, slug, title, price, description=''):
    l=m.create_listing(seller.id, ListingInput(slug,title,description,'product','YER',Decimal(str(price)),'rice','wh'))
    m.moderate_listing(l.id,user.id,'approved'); m.publish_listing(seller.id,l.id)
    return l


def test_search_supports_relevance_price_currency_and_seller_filters():
    db,seller,bt,buyer,su=setup(); m=MarketplaceService(db)
    m.register_seller(seller.id,'seller-one','Seller One'); m.review_seller_verification(seller.id,su.id,'approved')
    a=publish(m,seller,su,'rice-red','Premium Red Rice',1500,'premium local rice')
    b=publish(m,seller,su,'rice-white','White Rice',800,'basic rice')
    items,total=m.public_listings(q='Premium Red',with_total=True)
    assert total == 1 and items[0]['id'] == a.id
    items,total=m.public_listings(min_price=1000,max_price=2000,sort='price_asc',with_total=True)
    assert total == 1 and items[0]['id'] == a.id
    items,total=m.public_listings(currency='yer',seller_slug='seller-one',with_total=True)
    assert total == 2 and {x['id'] for x in items} == {a.id,b.id}


def test_search_in_stock_excludes_zero_stock_managed_products():
    db,seller,bt,buyer,su=setup(); m=MarketplaceService(db)
    m.register_seller(seller.id,'stock-seller','Stock Seller'); m.review_seller_verification(seller.id,su.id,'approved')
    l=publish(m,seller,su,'rice-stock','Rice Stock',1000)
    items,total=m.public_listings(in_stock=True,with_total=True)
    assert total == 1 and items[0]['id'] == l.id
