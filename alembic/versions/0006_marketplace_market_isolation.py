"""Close marketplace market isolation without forking the marketplace domain.

The unified 0001 baseline creates the current metadata on a fresh database. This
migration is therefore idempotent for fresh databases and upgrades older databases
by adding the market context columns and backfilling them only when the existing
data has an unambiguous active market.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_marketplace_market_isolation"
down_revision = "0005_y2_market_foundation"
branch_labels = None
depends_on = None

TABLE_COLUMNS = {
    "marketplace_categories": ("market_id", "market_contexts", "CASCADE"),
    "marketplace_products": ("market_id", "market_contexts", "CASCADE"),
    "marketplace_offers": ("market_id", "market_contexts", "CASCADE"),
    "marketplace_listings": ("market_id", "market_contexts", "CASCADE"),
    "marketplace_carts": ("market_id", "market_contexts", "CASCADE"),
    "marketplace_customer_orders": ("market_id", "market_contexts", "RESTRICT"),
    "marketplace_orders": ("market_id", "market_contexts", "RESTRICT"),
    "marketplace_fee_rules": ("market_id", "market_contexts", "CASCADE"),
    "marketplace_shipping_rates": ("market_id", "market_contexts", "CASCADE"),
    "marketplace_shipping_quotes": ("market_id", "market_contexts", "RESTRICT"),
    "marketplace_offer_competitions": ("market_id", "market_contexts", "CASCADE"),
}


def _has_column(inspector, table, column):
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_table(inspector, table):
    return table in inspector.get_table_names()


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, (column, ref_table, ondelete) in TABLE_COLUMNS.items():
        if not _has_table(inspector, table) or _has_column(inspector, table, column):
            continue
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(table, recreate="always") as batch:
                batch.add_column(sa.Column(column, sa.Integer(), nullable=True))
                batch.create_index(f"ix_{table}_market_id", [column], unique=False)
                batch.create_foreign_key(f"fk_{table}_market_id", ref_table, [column], ["id"], ondelete=ondelete)
        else:
            op.add_column(table, sa.Column(column, sa.Integer(), nullable=True))
            op.create_index(f"ix_{table}_market_id", table, [column], unique=False)
            op.create_foreign_key(f"fk_{table}_market_id", table, ref_table, [column], ["id"], ondelete=ondelete)

    # Existing rows can only be migrated safely when there is exactly one active
    # market. Otherwise the operator must assign markets explicitly before this
    # schema can be considered isolated.
    inspector = sa.inspect(bind)
    if not _has_table(inspector, "market_contexts"):
        return
    active_market_ids = [r[0] for r in bind.execute(sa.text("SELECT id FROM market_contexts WHERE status = 'active' ORDER BY id"))]
    for table in TABLE_COLUMNS:
        if not _has_table(inspector, table) or not _has_column(inspector, table, "market_id"):
            continue
        count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE market_id IS NULL")).scalar_one()
        if count == 0:
            continue
        if len(active_market_ids) != 1:
            raise RuntimeError(
                f"Cannot backfill {table}.market_id safely: expected exactly one active market, "
                f"found {len(active_market_ids)}. Assign existing marketplace rows to a market and rerun."
            )
        bind.execute(sa.text(f"UPDATE {table} SET market_id = :market_id WHERE market_id IS NULL"), {"market_id": active_market_ids[0]})

    # Competition cache is market-specific. Fresh databases already have the
    # composite unique constraint from metadata; legacy SQLite databases need
    # the old single-column unique constraint replaced during table recreation.
    if _has_table(inspector, "marketplace_offer_competitions") and _has_column(inspector, "marketplace_offer_competitions", "market_id"):
        table = sa.Table("marketplace_offer_competitions", sa.MetaData(), autoload_with=bind)
        unique_sets = [tuple(c.columns.keys()) for c in table.constraints if isinstance(c, sa.UniqueConstraint)]
        if ("catalog_group_id",) in unique_sets and ("market_id", "catalog_group_id") not in unique_sets:
            if bind.dialect.name == "sqlite":
                # Use a batch recreation with a reflected copy stripped of the legacy unique.
                for c in list(table.constraints):
                    if isinstance(c, sa.UniqueConstraint) and tuple(c.columns.keys()) == ("catalog_group_id",):
                        table.constraints.remove(c)
                table.append_constraint(sa.UniqueConstraint("market_id", "catalog_group_id", name="uq_market_competition_market_group"))
                with op.batch_alter_table("marketplace_offer_competitions", recreate="always", copy_from=table):
                    pass
            else:
                op.drop_constraint(None, "marketplace_offer_competitions", type_="unique")
                op.create_unique_constraint("uq_market_competition_market_group", "marketplace_offer_competitions", ["market_id", "catalog_group_id"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table, (column, _, _) in reversed(list(TABLE_COLUMNS.items())):
        if not _has_table(inspector, table) or not _has_column(inspector, table, column):
            continue
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(table, recreate="always") as batch:
                if table == "marketplace_offer_competitions":
                    try:
                        batch.drop_constraint("uq_market_competition_market_group", type_="unique")
                    except Exception:
                        pass
                    batch.create_unique_constraint("uq_market_competition_group", ["catalog_group_id"])
                try:
                    batch.drop_index(f"ix_{table}_market_id")
                except Exception:
                    pass
                batch.drop_column(column)
        else:
            try:
                op.drop_constraint(f"fk_{table}_market_id", table, type_="foreignkey")
            except Exception:
                pass
            try:
                op.drop_index(f"ix_{table}_market_id", table_name=table)
            except Exception:
                pass
            op.drop_column(table, column)
