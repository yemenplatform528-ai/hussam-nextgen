"""Make catalog/product/listing identifiers unique within a market."""
from alembic import op
import sqlalchemy as sa

revision = '0008_marketplace_catalog_market_uniqueness'
down_revision = '0007_marketplace_shipping_geography_and_cart_scope'
branch_labels = None
depends_on = None


def _uniques(table):
    ins = sa.inspect(op.get_bind())
    return {c['name']: tuple(c['column_names']) for c in ins.get_unique_constraints(table)}


def _ensure(table, old_name, old_cols, new_name, new_cols, downgrade=False):
    bind = op.get_bind()
    uniques = _uniques(table)
    target_name, target_cols = (old_name, old_cols) if downgrade else (new_name, new_cols)
    obsolete_name, obsolete_cols = (new_name, new_cols) if downgrade else (old_name, old_cols)
    if target_name in uniques and uniques[target_name] == tuple(target_cols):
        return
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table(table, recreate='always') as batch:
            if obsolete_name in uniques:
                batch.drop_constraint(obsolete_name, type_='unique')
            batch.create_unique_constraint(target_name, target_cols)
    else:
        if obsolete_name in uniques:
            op.drop_constraint(obsolete_name, table, type_='unique')
        if target_name not in uniques:
            op.create_unique_constraint(target_name, table, target_cols)


def upgrade():
    _ensure('marketplace_products','uq_market_product_seller_slug',['seller_tenant_id','slug'],
            'uq_market_product_seller_market_slug',['seller_tenant_id','market_id','slug'])
    _ensure('marketplace_offers','uq_market_offer_seller_sku',['seller_tenant_id','sku_id'],
            'uq_market_offer_seller_market_sku',['seller_tenant_id','market_id','sku_id'])
    _ensure('marketplace_listings','uq_market_listing_seller_slug',['seller_tenant_id','slug'],
            'uq_market_listing_seller_market_slug',['seller_tenant_id','market_id','slug'])


def downgrade():
    _ensure('marketplace_products','uq_market_product_seller_slug',['seller_tenant_id','slug'],
            'uq_market_product_seller_market_slug',['seller_tenant_id','market_id','slug'],downgrade=True)
    _ensure('marketplace_offers','uq_market_offer_seller_sku',['seller_tenant_id','sku_id'],
            'uq_market_offer_seller_market_sku',['seller_tenant_id','market_id','sku_id'],downgrade=True)
    _ensure('marketplace_listings','uq_market_listing_seller_slug',['seller_tenant_id','slug'],
            'uq_market_listing_seller_market_slug',['seller_tenant_id','market_id','slug'],downgrade=True)
