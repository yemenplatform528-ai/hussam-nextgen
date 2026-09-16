"""Y2 market foundation and integrity closure.

This migration is intentionally provider-neutral.  It establishes the reusable
market context, currency, geography, coverage, provider registry/capability,
payment-method catalog, and structured marketplace-address extension.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_y2_market_foundation"
down_revision = "0004_carrier_lifecycle"
branch_labels = None
depends_on = None


def _has_unique(bind, table, name):
    return any(x.get("name") == name for x in inspect(bind).get_unique_constraints(table))


def _has_check(bind, table, name):
    return any(x.get("name") == name for x in inspect(bind).get_check_constraints(table))


def _has_fk(bind, table, name):
    return any(x.get("name") == name for x in inspect(bind).get_foreign_keys(table))


def _has_index(bind, table, name):
    return any(x.get("name") == name for x in inspect(bind).get_indexes(table))


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    if "market_contexts" not in tables:
        op.create_table(
            "market_contexts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(32), nullable=False),
            sa.Column("country_code", sa.String(2), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("locale", sa.String(32), nullable=False),
            sa.Column("timezone", sa.String(64), nullable=False),
            sa.Column("default_currency", sa.String(10), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("configuration_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("code", name="uq_market_context_code"),
            sa.CheckConstraint("length(country_code) = 2", name="ck_market_context_country_code"),
            sa.CheckConstraint("status IN ('draft','active','suspended','retired')", name="ck_market_context_status"),
            sa.CheckConstraint("length(default_currency) >= 3", name="ck_market_context_currency"),
        )

    if "market_currencies" not in tables:
        op.create_table(
            "market_currencies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("market_id", sa.Integer(), sa.ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("currency", sa.String(10), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("cash_supported", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("electronic_supported", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.UniqueConstraint("market_id", "currency", name="uq_market_currency"),
        )
        op.create_index("ix_market_currency_market", "market_currencies", ["market_id"])

    if "market_geographies" not in tables:
        op.create_table(
            "market_geographies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("market_id", sa.Integer(), sa.ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("parent_id", sa.Integer(), sa.ForeignKey("market_geographies.id", ondelete="RESTRICT"), nullable=True),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("level", sa.String(20), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("name_ar", sa.String(200), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.UniqueConstraint("market_id", "code", name="uq_market_geography_code"),
            sa.UniqueConstraint("market_id", "id", name="uq_market_geography_market_id"),
            sa.ForeignKeyConstraint(["market_id", "parent_id"], ["market_geographies.market_id", "market_geographies.id"], name="fk_market_geography_parent_market", ondelete="RESTRICT"),
            sa.CheckConstraint("level IN ('country','governorate','district','locality')", name="ck_market_geography_level"),
            sa.CheckConstraint("(level = 'country' AND parent_id IS NULL) OR (level <> 'country' AND parent_id IS NOT NULL)", name="ck_market_geography_parent_required"),
            sa.CheckConstraint("status IN ('active','inactive')", name="ck_market_geography_status"),
        )
        op.create_index("ix_market_geography_market_parent", "market_geographies", ["market_id", "parent_id"])

    if "market_coverages" not in tables:
        op.create_table(
            "market_coverages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("market_id", sa.Integer(), sa.ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("geography_id", sa.Integer(), sa.ForeignKey("market_geographies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="available"),
            sa.UniqueConstraint("market_id", "geography_id", name="uq_market_coverage"),
            sa.CheckConstraint("status IN ('available','limited','unavailable','suspended')", name="ck_market_coverage_status"),
            sa.ForeignKeyConstraint(["market_id", "geography_id"], ["market_geographies.market_id", "market_geographies.id"], name="fk_market_coverage_market_geography", ondelete="CASCADE"),
        )

    if "provider_registry_entries" not in tables:
        op.create_table(
            "provider_registry_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(80), nullable=False),
            sa.Column("organization_name", sa.String(200), nullable=False),
            sa.Column("provider_type", sa.String(40), nullable=False),
            sa.Column("product_name", sa.String(160), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="discovered"),
            sa.Column("integration_mode", sa.String(30), nullable=False, server_default="none"),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.UniqueConstraint("code", name="uq_provider_registry_code"),
            sa.CheckConstraint("provider_type IN ('payment','logistics','notification','financial','other')", name="ck_provider_registry_type"),
            sa.CheckConstraint("status IN ('discovered','contract_required','api_pending','integrating','testing','certified','production','suspended')", name="ck_provider_registry_status"),
            sa.CheckConstraint("integration_mode IN ('none','manual','api','webhook','hybrid')", name="ck_provider_registry_integration"),
        )

    if "provider_market_capabilities" not in tables:
        op.create_table(
            "provider_market_capabilities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider_id", sa.Integer(), sa.ForeignKey("provider_registry_entries.id", ondelete="CASCADE"), nullable=False),
            sa.Column("market_id", sa.Integer(), sa.ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("capability", sa.String(80), nullable=False),
            sa.Column("rail", sa.String(80), nullable=False, server_default=""),
            sa.Column("currency", sa.String(10), nullable=False, server_default=""),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.UniqueConstraint("provider_id", "market_id", "capability", "rail", "currency", name="uq_provider_market_capability"),
        )
        op.create_index("ix_provider_market_market", "provider_market_capabilities", ["market_id"])

    if "payment_method_catalog" not in tables:
        op.create_table(
            "payment_method_catalog",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("market_id", sa.Integer(), sa.ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("code", sa.String(40), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("method_type", sa.String(30), nullable=False),
            sa.Column("requires_provider", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.UniqueConstraint("market_id", "code", name="uq_payment_method_market_code"),
            sa.CheckConstraint("method_type IN ('wallet','bank','card','transfer','cash','cod')", name="ck_payment_method_type"),
        )

    # The canonical baseline can already contain these tables.  The following
    # closure is therefore conditional and upgrades older 0004-compatible
    # schemas without duplicating constraints.
    bind = op.get_bind()
    insp = inspect(bind)

    if "market_currencies" in insp.get_table_names() and not _has_index(bind, "market_currencies", "uq_market_currency_default"):
        op.create_index(
            "uq_market_currency_default",
            "market_currencies",
            ["market_id"],
            unique=True,
            sqlite_where=sa.text("is_default = 1"),
            postgresql_where=sa.text("is_default IS TRUE"),
        )

    if "market_geographies" in insp.get_table_names():
        need_unique = not _has_unique(bind, "market_geographies", "uq_market_geography_market_id")
        need_parent_fk = not _has_fk(bind, "market_geographies", "fk_market_geography_parent_market")
        need_parent_check = not _has_check(bind, "market_geographies", "ck_market_geography_parent_required")
        if need_unique or need_parent_fk or need_parent_check:
            if bind.dialect.name == "sqlite":
                with op.batch_alter_table("market_geographies", recreate="always") as batch:
                    if need_unique:
                        batch.create_unique_constraint("uq_market_geography_market_id", ["market_id", "id"])
                    if need_parent_fk:
                        batch.create_foreign_key("fk_market_geography_parent_market", "market_geographies", ["market_id", "parent_id"], ["market_id", "id"], ondelete="RESTRICT")
                    if need_parent_check:
                        batch.create_check_constraint("ck_market_geography_parent_required", "(level = 'country' AND parent_id IS NULL) OR (level <> 'country' AND parent_id IS NOT NULL)")
            else:
                if need_unique:
                    op.create_unique_constraint("uq_market_geography_market_id", "market_geographies", ["market_id", "id"])
                if need_parent_fk:
                    op.create_foreign_key("fk_market_geography_parent_market", "market_geographies", "market_geographies", ["market_id", "parent_id"], ["market_id", "id"], ondelete="RESTRICT")
                if need_parent_check:
                    op.create_check_constraint("ck_market_geography_parent_required", "market_geographies", "(level = 'country' AND parent_id IS NULL) OR (level <> 'country' AND parent_id IS NOT NULL)")

    if "market_coverages" in insp.get_table_names() and not _has_fk(bind, "market_coverages", "fk_market_coverage_market_geography"):
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("market_coverages", recreate="always") as batch:
                batch.create_foreign_key("fk_market_coverage_market_geography", "market_geographies", ["market_id", "geography_id"], ["market_id", "id"], ondelete="CASCADE")
        else:
            op.create_foreign_key("fk_market_coverage_market_geography", "market_coverages", "market_geographies", ["market_id", "geography_id"], ["market_id", "id"], ondelete="CASCADE")

    if "marketplace_addresses" in insp.get_table_names():
        checks = insp.get_check_constraints("marketplace_addresses")
        missing_checks = []
        if "ck_market_address_country_code" not in {c.get("name") for c in checks}:
            missing_checks.append(("ck_market_address_country_code", "country_code IS NULL OR length(country_code) = 2"))
        # These were already part of the model in the canonical baseline, but
        # keep them explicit for older schemas.
        if "ck_market_address_confidence" not in {c.get("name") for c in checks}:
            missing_checks.append(("ck_market_address_confidence", "address_confidence IN ('high','medium','low')"))
        if "ck_market_address_lat" not in {c.get("name") for c in checks}:
            missing_checks.append(("ck_market_address_lat", "geo_lat IS NULL OR (geo_lat >= -90 AND geo_lat <= 90)"))
        if "ck_market_address_lng" not in {c.get("name") for c in checks}:
            missing_checks.append(("ck_market_address_lng", "geo_lng IS NULL OR (geo_lng >= -180 AND geo_lng <= 180)"))
        missing_address_fks = [
            ("fk_marketplace_address_governorate_market", "governorate_id"),
            ("fk_marketplace_address_district_market", "district_id"),
            ("fk_marketplace_address_locality_market", "locality_id"),
        ]
        missing_address_fks = [(n, c) for n, c in missing_address_fks if not _has_fk(bind, "marketplace_addresses", n)]
        if missing_checks or missing_address_fks:
            if bind.dialect.name == "sqlite":
                with op.batch_alter_table("marketplace_addresses", recreate="always") as batch:
                    for n, expr in missing_checks:
                        batch.create_check_constraint(n, expr)
                    for n, col in missing_address_fks:
                        batch.create_foreign_key(n, "market_geographies", ["market_id", col], ["market_id", "id"], ondelete="SET NULL")
            else:
                for n, expr in missing_checks:
                    op.create_check_constraint(n, "marketplace_addresses", expr)
                for n, col in missing_address_fks:
                    op.create_foreign_key(n, "marketplace_addresses", "market_geographies", ["market_id", col], ["market_id", "id"], ondelete="SET NULL")


def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    tables = set(insp.get_table_names())

    if "marketplace_addresses" in tables:
        names = {x.get("name") for x in insp.get_check_constraints("marketplace_addresses")}
        fks = {x.get("name") for x in insp.get_foreign_keys("marketplace_addresses")}
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("marketplace_addresses", recreate="always") as batch:
                for name in (
                    "fk_marketplace_address_governorate_market",
                    "fk_marketplace_address_district_market",
                    "fk_marketplace_address_locality_market",
                ):
                    if name in fks:
                        batch.drop_constraint(name, type_="foreignkey")
                if "ck_market_address_country_code" in names:
                    batch.drop_constraint("ck_market_address_country_code", type_="check")
        else:
            for name in (
                "fk_marketplace_address_governorate_market",
                "fk_marketplace_address_district_market",
                "fk_marketplace_address_locality_market",
            ):
                if name in fks:
                    op.drop_constraint(name, "marketplace_addresses", type_="foreignkey")
            if "ck_market_address_country_code" in names:
                op.drop_constraint("ck_market_address_country_code", "marketplace_addresses", type_="check")

    insp = inspect(bind)
    if "market_coverages" in tables and _has_fk(bind, "market_coverages", "fk_market_coverage_market_geography"):
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("market_coverages", recreate="always") as batch:
                batch.drop_constraint("fk_market_coverage_market_geography", type_="foreignkey")
        else:
            op.drop_constraint("fk_market_coverage_market_geography", "market_coverages", type_="foreignkey")

    insp = inspect(bind)
    if "market_geographies" in tables:
        checks = {x.get("name") for x in insp.get_check_constraints("market_geographies")}
        fks = {x.get("name") for x in insp.get_foreign_keys("market_geographies")}
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("market_geographies", recreate="always") as batch:
                if "fk_market_geography_parent_market" in fks:
                    batch.drop_constraint("fk_market_geography_parent_market", type_="foreignkey")
                if "ck_market_geography_parent_required" in checks:
                    batch.drop_constraint("ck_market_geography_parent_required", type_="check")
                if _has_unique(bind, "market_geographies", "uq_market_geography_market_id"):
                    batch.drop_constraint("uq_market_geography_market_id", type_="unique")
        else:
            if "fk_market_geography_parent_market" in fks:
                op.drop_constraint("fk_market_geography_parent_market", "market_geographies", type_="foreignkey")
            if "ck_market_geography_parent_required" in checks:
                op.drop_constraint("ck_market_geography_parent_required", "market_geographies", type_="check")
            if _has_unique(bind, "market_geographies", "uq_market_geography_market_id"):
                op.drop_constraint("uq_market_geography_market_id", "market_geographies", type_="unique")

    if "market_currencies" in tables and _has_index(bind, "market_currencies", "uq_market_currency_default"):
        op.drop_index("uq_market_currency_default", table_name="market_currencies")
