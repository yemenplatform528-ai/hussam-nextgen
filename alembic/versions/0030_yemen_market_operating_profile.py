"""seed the Yemen market operating profile"""
from alembic import op
import sqlalchemy as sa
import json
from datetime import datetime, timezone
revision='0030_yemen_market_operating_profile'
down_revision='0029_developer_extension_platform'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    markets=sa.table('market_contexts',sa.column('id',sa.Integer),sa.column('code',sa.String),sa.column('country_code',sa.String),sa.column('name',sa.String),sa.column('locale',sa.String),sa.column('timezone',sa.String),sa.column('default_currency',sa.String),sa.column('status',sa.String),sa.column('configuration_json',sa.Text),sa.column('created_at',sa.DateTime),sa.column('updated_at',sa.DateTime))
    row=bind.execute(sa.select(markets.c.id).where(markets.c.code=='YEM')).first()
    now=datetime.now(timezone.utc)
    if row is None:
        bind.execute(markets.insert().values(code='YEM',country_code='YE',name='Yemen',locale='ar-YE',timezone='Asia/Aden',default_currency='YER',status='active',configuration_json=json.dumps({'commerce':{'cod':True,'cash_at_pickup':True,'manual_transfer':True},'localization':{'arabic_first':True,'english_supported':True},'connectivity':{'offline_drafts':True,'idempotent_mutations':True,'explicit_pending_states':True},'provider_policy':{'provider_neutral':True,'credentials_external':True},'fx_policy':{'no_implicit_conversion':True,'provenance_required':True}}),created_at=now,updated_at=now))
        row=bind.execute(sa.select(markets.c.id).where(markets.c.code=='YEM')).first()
    market_id=row[0]
    currencies=sa.table('market_currencies',sa.column('market_id',sa.Integer),sa.column('currency',sa.String),sa.column('is_default',sa.Boolean),sa.column('cash_supported',sa.Boolean),sa.column('electronic_supported',sa.Boolean))
    for code,default in [('YER',True),('USD',False),('SAR',False)]:
        if bind.execute(sa.select(currencies.c.market_id).where(currencies.c.market_id==market_id,currencies.c.currency==code)).first() is None:
            bind.execute(currencies.insert().values(market_id=market_id,currency=code,is_default=default,cash_supported=True,electronic_supported=(code=='YER')))
    methods=sa.table('payment_method_catalog',sa.column('market_id',sa.Integer),sa.column('code',sa.String),sa.column('name',sa.String),sa.column('method_type',sa.String),sa.column('requires_provider',sa.Boolean),sa.column('active',sa.Boolean))
    for code,name,kind,provider in [
        ('cod','Cash on Delivery','cod',False),
        ('cash_pickup','Cash at Pickup','cash',False),
        ('manual_transfer','Manual Transfer / Reference','transfer',False),
    ]:
        if bind.execute(sa.select(methods.c.id).where(methods.c.market_id==market_id,methods.c.code==code)).first() is None:
            bind.execute(methods.insert().values(market_id=market_id,code=code,name=name,method_type=kind,requires_provider=provider,active=True))

def downgrade():
    bind=op.get_bind()
    market=sa.table('market_contexts',sa.column('id',sa.Integer),sa.column('code',sa.String))
    row=bind.execute(sa.select(market.c.id).where(market.c.code=='YEM')).first()
    if row is None: return
    market_id=row[0]
    methods=sa.table('payment_method_catalog',sa.column('market_id',sa.Integer),sa.column('code',sa.String))
    currencies=sa.table('market_currencies',sa.column('market_id',sa.Integer),sa.column('currency',sa.String))
    bind.execute(methods.delete().where(methods.c.market_id==market_id,methods.c.code.in_(['cod','cash_pickup','manual_transfer'])))
    bind.execute(currencies.delete().where(currencies.c.market_id==market_id,currencies.c.currency.in_(['YER','USD','SAR'])))
    bind.execute(market.delete().where(market.c.id==market_id))