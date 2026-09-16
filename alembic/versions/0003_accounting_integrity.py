"""Accounting chart-of-accounts registry and journal integrity metadata."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = '0003_accounting_integrity'
down_revision = '0002_oidc_identity_binding'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if 'accounts' not in inspector.get_table_names():
        op.create_table(
            'accounts',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('code', sa.String(64), nullable=False),
            sa.Column('name', sa.String(160), nullable=False),
            sa.Column('account_type', sa.String(30), nullable=False),
            sa.Column('currency', sa.String(10), nullable=True),
            sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('tenant_id', 'code', name='uq_account_tenant_code'),
        )
        op.create_index('ix_accounts_tenant_id', 'accounts', ['tenant_id'])
    cols = {c['name'] for c in inspector.get_columns('journals')}
    if 'posting_date' not in cols:
        op.add_column('journals', sa.Column('posting_date', sa.Date(), nullable=True))
        op.execute(sa.text("UPDATE journals SET posting_date = DATE(created_at) WHERE posting_date IS NULL"))
    if 'content_hash' not in cols:
        op.add_column('journals', sa.Column('content_hash', sa.String(128), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('journals')}
    if 'content_hash' in cols: op.drop_column('journals', 'content_hash')
    if 'posting_date' in cols: op.drop_column('journals', 'posting_date')
    if 'accounts' in inspector.get_table_names():
        op.drop_index('ix_accounts_tenant_id', table_name='accounts')
        op.drop_table('accounts')
