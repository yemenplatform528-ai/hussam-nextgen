"""Provider-neutral carrier registry and signed event ledger."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision='0004_carrier_lifecycle'
down_revision='0003_accounting_integrity'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind(); insp=inspect(bind); tables=set(insp.get_table_names())
    if 'carrier_integrations' not in tables:
        op.create_table('carrier_integrations',
            sa.Column('id',sa.Integer(),primary_key=True),
            sa.Column('tenant_id',sa.Integer(),sa.ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False),
            sa.Column('code',sa.String(80),nullable=False),
            sa.Column('name',sa.String(160),nullable=False),
            sa.Column('webhook_secret_ref',sa.String(255),nullable=True),
            sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()),
            sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
            sa.UniqueConstraint('tenant_id','code',name='uq_carrier_integration_tenant_code'))
        op.create_index('ix_carrier_integrations_tenant_id','carrier_integrations',['tenant_id'])
    if 'carrier_events' not in tables:
        op.create_table('carrier_events',
            sa.Column('id',sa.Integer(),primary_key=True),
            sa.Column('tenant_id',sa.Integer(),sa.ForeignKey('tenants.id',ondelete='CASCADE'),nullable=False),
            sa.Column('carrier_id',sa.Integer(),sa.ForeignKey('carrier_integrations.id',ondelete='CASCADE'),nullable=False),
            sa.Column('shipment_id',sa.Integer(),sa.ForeignKey('shipments.id',ondelete='CASCADE'),nullable=False),
            sa.Column('external_event_id',sa.String(255),nullable=False),
            sa.Column('event_type',sa.String(80),nullable=False),
            sa.Column('payload_hash',sa.String(128),nullable=False),
            sa.Column('received_at',sa.DateTime(timezone=True),nullable=False),
            sa.UniqueConstraint('tenant_id','carrier_id','external_event_id',name='uq_carrier_event_external_id'))
        op.create_index('ix_carrier_events_tenant_id','carrier_events',['tenant_id'])
        op.create_index('ix_carrier_events_carrier_id','carrier_events',['carrier_id'])
        op.create_index('ix_carrier_events_shipment_id','carrier_events',['shipment_id'])

def downgrade():
    bind=op.get_bind(); insp=inspect(bind); tables=set(insp.get_table_names())
    if 'carrier_events' in tables:
        for n in ('ix_carrier_events_shipment_id','ix_carrier_events_carrier_id','ix_carrier_events_tenant_id'): op.drop_index(n,table_name='carrier_events')
        op.drop_table('carrier_events')
    if 'carrier_integrations' in tables:
        op.drop_index('ix_carrier_integrations_tenant_id',table_name='carrier_integrations')
        op.drop_table('carrier_integrations')
