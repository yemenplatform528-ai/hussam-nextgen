"""Close market identity and payout safety for marketplace lifecycle aggregates."""
from alembic import op
import sqlalchemy as sa

revision = '0009_marketplace_lifecycle_financial_isolation'
down_revision = '0008_marketplace_catalog_market_uniqueness'
branch_labels = None
depends_on = None

TABLES = ('marketplace_payouts','marketplace_disputes','marketplace_return_requests')

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_sqlite = bind.dialect.name == 'sqlite'
    for table in TABLES:
        cols = {c['name'] for c in insp.get_columns(table)}
        if 'market_id' not in cols:
            if is_sqlite:
                with op.batch_alter_table(table, recreate='always') as batch:
                    batch.add_column(sa.Column('market_id', sa.Integer(), nullable=True))
                    batch.create_foreign_key(f'fk_{table}_market', 'market_contexts', ['market_id'], ['id'], ondelete='RESTRICT')
                    batch.create_index(f'ix_{table}_market_id', ['market_id'], unique=False)
            else:
                op.add_column(table, sa.Column('market_id', sa.Integer(), nullable=True))
                op.create_foreign_key(f'fk_{table}_market', table, 'market_contexts', ['market_id'], ['id'], ondelete='RESTRICT')
                op.create_index(f'ix_{table}_market_id', table, ['market_id'], unique=False)
        else:
            existing_indexes = {idx['name'] for idx in sa.inspect(bind).get_indexes(table)}
            if f'ix_{table}_market_id' not in existing_indexes:
                op.create_index(f'ix_{table}_market_id', table, ['market_id'], unique=False)
    # Existing rows are safely backfilled from their immutable marketplace order.
    for table in TABLES:
        op.execute(sa.text(f"UPDATE {table} SET market_id=(SELECT market_id FROM marketplace_orders o WHERE o.id={table}.marketplace_order_id) WHERE market_id IS NULL"))

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    is_sqlite = bind.dialect.name == 'sqlite'
    for table in reversed(TABLES):
        has_column = any(c['name'] == 'market_id' for c in sa.inspect(bind).get_columns(table))
        if not has_column:
            continue
        if is_sqlite:
            with op.batch_alter_table(table, recreate='always') as batch:
                batch.drop_index(f'ix_{table}_market_id')
                batch.drop_column('market_id')
        else:
            for idx in insp.get_indexes(table):
                if idx['name'] == f'ix_{table}_market_id':
                    op.drop_index(idx['name'], table_name=table)
            for fk in insp.get_foreign_keys(table):
                if fk['name'] == f'fk_{table}_market':
                    op.drop_constraint(fk['name'], table_name=table, type_='foreignkey')
            op.drop_column(table,'market_id')
