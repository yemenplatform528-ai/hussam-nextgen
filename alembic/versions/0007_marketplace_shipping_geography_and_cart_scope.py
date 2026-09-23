"""Close structured shipping geography and per-market buyer carts."""
from alembic import op
import sqlalchemy as sa

revision = "0007_marketplace_shipping_geography_and_cart_scope"
down_revision = "0006_marketplace_market_isolation"
branch_labels = None
depends_on = None


def _has_table(inspector, table):
    return table in inspector.get_table_names()


def _has_column(inspector, table, column):
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "marketplace_shipping_rates"):
        existing = {c["name"] for c in inspector.get_columns("marketplace_shipping_rates")}
        shipping_uniques = [tuple(c["column_names"]) for c in inspector.get_unique_constraints("marketplace_shipping_rates")]
        has_legacy_shipping_unique = ("seller_tenant_id", "governorate", "city", "currency") in shipping_uniques
        existing_indexes = {i["name"] for i in inspector.get_indexes("marketplace_shipping_rates")}
        existing_fks = {f.get("name") for f in inspector.get_foreign_keys("marketplace_shipping_rates")}
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("marketplace_shipping_rates", recreate="always") as batch:
                if "governorate_id" not in existing:
                    batch.add_column(sa.Column("governorate_id", sa.Integer(), nullable=True))
                if "district_id" not in existing:
                    batch.add_column(sa.Column("district_id", sa.Integer(), nullable=True))
                if "locality_id" not in existing:
                    batch.add_column(sa.Column("locality_id", sa.Integer(), nullable=True))
                if has_legacy_shipping_unique:
                    batch.drop_constraint("uq_market_shipping_rate", type_="unique")
                batch.create_unique_constraint(
                    "uq_market_shipping_rate_market_geo",
                    ["seller_tenant_id", "market_id", "governorate_id", "district_id", "locality_id", "currency"],
                )
                if "ix_marketplace_shipping_rates_governorate_id" not in existing_indexes:
                    batch.create_index("ix_marketplace_shipping_rates_governorate_id", ["governorate_id"], unique=False)
                if "ix_marketplace_shipping_rates_district_id" not in existing_indexes:
                    batch.create_index("ix_marketplace_shipping_rates_district_id", ["district_id"], unique=False)
                if "ix_marketplace_shipping_rates_locality_id" not in existing_indexes:
                    batch.create_index("ix_marketplace_shipping_rates_locality_id", ["locality_id"], unique=False)
                if "fk_market_shipping_rate_governorate_market" not in existing_fks:
                    batch.create_foreign_key("fk_market_shipping_rate_governorate_market", "market_geographies", ["market_id", "governorate_id"], ["market_id", "id"], ondelete="SET NULL")
                if "fk_market_shipping_rate_district_market" not in existing_fks:
                    batch.create_foreign_key("fk_market_shipping_rate_district_market", "market_geographies", ["market_id", "district_id"], ["market_id", "id"], ondelete="SET NULL")
                if "fk_market_shipping_rate_locality_market" not in existing_fks:
                    batch.create_foreign_key("fk_market_shipping_rate_locality_market", "market_geographies", ["market_id", "locality_id"], ["market_id", "id"], ondelete="SET NULL")
        else:
            if "governorate_id" not in existing:
                op.add_column("marketplace_shipping_rates", sa.Column("governorate_id", sa.Integer(), nullable=True))
            if "district_id" not in existing:
                op.add_column("marketplace_shipping_rates", sa.Column("district_id", sa.Integer(), nullable=True))
            if "locality_id" not in existing:
                op.add_column("marketplace_shipping_rates", sa.Column("locality_id", sa.Integer(), nullable=True))
            if has_legacy_shipping_unique:
                op.drop_constraint("uq_market_shipping_rate", "marketplace_shipping_rates", type_="unique")
            if "uq_market_shipping_rate_market_geo" not in {c["name"] for c in inspector.get_unique_constraints("marketplace_shipping_rates") if c.get("name")}:
                op.create_unique_constraint("uq_market_shipping_rate_market_geo", "marketplace_shipping_rates", ["seller_tenant_id", "market_id", "governorate_id", "district_id", "locality_id", "currency"])
            if "ix_marketplace_shipping_rates_governorate_id" not in existing_indexes:
                op.create_index("ix_marketplace_shipping_rates_governorate_id", "marketplace_shipping_rates", ["governorate_id"])
            if "ix_marketplace_shipping_rates_district_id" not in existing_indexes:
                op.create_index("ix_marketplace_shipping_rates_district_id", "marketplace_shipping_rates", ["district_id"])
            if "ix_marketplace_shipping_rates_locality_id" not in existing_indexes:
                op.create_index("ix_marketplace_shipping_rates_locality_id", "marketplace_shipping_rates", ["locality_id"])
            if "fk_market_shipping_rate_governorate_market" not in existing_fks:
                op.create_foreign_key("fk_market_shipping_rate_governorate_market", "marketplace_shipping_rates", "market_geographies", ["market_id", "governorate_id"], ["market_id", "id"], ondelete="SET NULL")
            if "fk_market_shipping_rate_district_market" not in existing_fks:
                op.create_foreign_key("fk_market_shipping_rate_district_market", "marketplace_shipping_rates", "market_geographies", ["market_id", "district_id"], ["market_id", "id"], ondelete="SET NULL")
            if "fk_market_shipping_rate_locality_market" not in existing_fks:
                op.create_foreign_key("fk_market_shipping_rate_locality_market", "marketplace_shipping_rates", "market_geographies", ["market_id", "locality_id"], ["market_id", "id"], ondelete="SET NULL")

    inspector = sa.inspect(bind)
    inspector = sa.inspect(bind)
    if _has_table(inspector, "marketplace_carts"):
        uniques = [tuple(c["column_names"]) for c in inspector.get_unique_constraints("marketplace_carts")]
        if ("buyer_user_id",) in uniques:
            if bind.dialect.name == "sqlite":
                with op.batch_alter_table("marketplace_carts", recreate="always") as batch:
                    try:
                        batch.drop_constraint("uq_market_cart_buyer", type_="unique")
                    except Exception:
                        pass
                    batch.create_unique_constraint("uq_market_cart_buyer_market", ["buyer_user_id", "market_id"])
            else:
                op.drop_constraint("uq_market_cart_buyer", "marketplace_carts", type_="unique")
                op.create_unique_constraint("uq_market_cart_buyer_market", "marketplace_carts", ["buyer_user_id", "market_id"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "marketplace_carts"):
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("marketplace_carts", recreate="always") as batch:
                try: batch.drop_constraint("uq_market_cart_buyer_market", type_="unique")
                except Exception: pass
                batch.create_unique_constraint("uq_market_cart_buyer", ["buyer_user_id"])
        else:
            try: op.drop_constraint("uq_market_cart_buyer_market", "marketplace_carts", type_="unique")
            except Exception: pass
            op.create_unique_constraint("uq_market_cart_buyer", "marketplace_carts", ["buyer_user_id"])

    inspector = sa.inspect(bind)
    if _has_table(inspector, "marketplace_shipping_rates"):
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("marketplace_shipping_rates", recreate="always") as batch:
                for name in ("fk_market_shipping_rate_locality_market","fk_market_shipping_rate_district_market","fk_market_shipping_rate_governorate_market"):
                    try: batch.drop_constraint(name, type_="foreignkey")
                    except Exception: pass
                for name in ("ix_marketplace_shipping_rates_locality_id","ix_marketplace_shipping_rates_district_id","ix_marketplace_shipping_rates_governorate_id"):
                    try: batch.drop_index(name)
                    except Exception: pass
                try: batch.drop_constraint("uq_market_shipping_rate_market_geo", type_="unique")
                except Exception: pass
                batch.create_unique_constraint("uq_market_shipping_rate", ["seller_tenant_id","governorate","city","currency"])
                for col in ("locality_id","district_id","governorate_id"):
                    try: batch.drop_column(col)
                    except Exception: pass
        else:
            for name in ("fk_market_shipping_rate_locality_market","fk_market_shipping_rate_district_market","fk_market_shipping_rate_governorate_market"):
                try: op.drop_constraint(name, "marketplace_shipping_rates", type_="foreignkey")
                except Exception: pass
            for name in ("ix_marketplace_shipping_rates_locality_id","ix_marketplace_shipping_rates_district_id","ix_marketplace_shipping_rates_governorate_id"):
                try: op.drop_index(name, table_name="marketplace_shipping_rates")
                except Exception: pass
            try: op.drop_constraint("uq_market_shipping_rate_market_geo", "marketplace_shipping_rates", type_="unique")
            except Exception: pass
            op.create_unique_constraint("uq_market_shipping_rate", "marketplace_shipping_rates", ["seller_tenant_id","governorate","city","currency"])
            for col in ("locality_id","district_id","governorate_id"):
                try: op.drop_column("marketplace_shipping_rates", col)
                except Exception: pass
