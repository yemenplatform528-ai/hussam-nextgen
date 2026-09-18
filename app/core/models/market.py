from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, Text, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.persistence import Base


def now_utc():
    return datetime.now(timezone.utc)


class MarketContext(Base):
    """Platform-level market configuration; tenant-neutral and provider-neutral."""
    __tablename__ = "market_contexts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    default_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    configuration_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    __table_args__ = (
        CheckConstraint("length(country_code) = 2", name="ck_market_context_country_code"),
        CheckConstraint("status IN ('draft','active','suspended','retired')", name="ck_market_context_status"),
        CheckConstraint("length(default_currency) >= 3", name="ck_market_context_currency"),
    )


class MarketCurrency(Base):
    """Currencies enabled for a market. FX rates are deliberately not stored here."""
    __tablename__ = "market_currencies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cash_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    electronic_supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        UniqueConstraint("market_id", "currency", name="uq_market_currency"),
        Index("ix_market_currency_market", "market_id"),
        Index(
            "uq_market_currency_default",
            "market_id",
            unique=True,
            sqlite_where=text("is_default = 1"),
            postgresql_where=text("is_default IS TRUE"),
        ),
    )


class MarketGeography(Base):
    """Reusable hierarchical geography; Yemen is data, not hard-coded application logic."""
    __tablename__ = "market_geographies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("market_geographies.id", ondelete="RESTRICT"), nullable=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    __table_args__ = (
        UniqueConstraint("market_id", "code", name="uq_market_geography_code"),
        UniqueConstraint("market_id", "id", name="uq_market_geography_market_id"),
        ForeignKeyConstraint(["market_id", "parent_id"], ["market_geographies.market_id", "market_geographies.id"], name="fk_market_geography_parent_market", ondelete="RESTRICT"),
        CheckConstraint("level IN ('country','governorate','district','locality')", name="ck_market_geography_level"),
        CheckConstraint("(level = 'country' AND parent_id IS NULL) OR (level <> 'country' AND parent_id IS NOT NULL)", name="ck_market_geography_parent_required"),
        CheckConstraint("status IN ('active','inactive')", name="ck_market_geography_status"),
        Index("ix_market_geography_market_parent", "market_id", "parent_id"),
    )


class MarketCoverage(Base):
    """Declares which geography nodes are operationally covered by a market."""
    __tablename__ = "market_coverages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False)
    geography_id: Mapped[int] = mapped_column(ForeignKey("market_geographies.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    __table_args__ = (
        UniqueConstraint("market_id", "geography_id", name="uq_market_coverage"),
        CheckConstraint("status IN ('available','limited','unavailable','suspended')", name="ck_market_coverage_status"),
        ForeignKeyConstraint(["market_id", "geography_id"], ["market_geographies.market_id", "market_geographies.id"], name="fk_market_coverage_market_geography", ondelete="CASCADE"),
    )


class MarketMoneyUnit(Base):
    """Market-scoped monetary unit variant; keeps denomination/issuance distinctions separate from ISO currency code."""
    __tablename__ = "market_money_units"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    variant: Mapped[str] = mapped_column(String(30), nullable=False, default="standard")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    __table_args__ = (
        UniqueConstraint("market_id", "code", name="uq_market_money_unit_code"),
        CheckConstraint("variant IN ('standard','current','legacy','denomination')", name="ck_market_money_unit_variant"),
        CheckConstraint("status IN ('active','inactive','deprecated')", name="ck_market_money_unit_status"),
    )


class MarketExchangeRate(Base):
    """Market/geography-scoped FX observation with explicit provenance and effective time."""
    __tablename__ = "market_exchange_rates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False)
    geography_id: Mapped[int | None] = mapped_column(ForeignKey("market_geographies.id", ondelete="RESTRICT"), nullable=True)
    base_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    rate: Mapped[object] = mapped_column(Numeric(24, 10), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    __table_args__ = (
        CheckConstraint("rate > 0", name="ck_market_fx_positive_rate"),
        CheckConstraint("base_currency <> quote_currency", name="ck_market_fx_distinct_currencies"),
        CheckConstraint("source_type IN ('official','provider','market_observed','manual')", name="ck_market_fx_source_type"),
        CheckConstraint("status IN ('active','superseded','void')", name="ck_market_fx_status"),
        ForeignKeyConstraint(["market_id", "geography_id"], ["market_geographies.market_id", "market_geographies.id"], name="fk_market_fx_market_geography", ondelete="RESTRICT"),
        Index("ix_market_fx_lookup", "market_id", "geography_id", "base_currency", "quote_currency", "effective_at"),
    )


class ProviderRegistryEntry(Base):
    """Provider catalog entry. Credentials and execution are intentionally out of this registry."""
    __tablename__ = "provider_registry_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    organization_name: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="discovered")
    integration_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="none")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    __table_args__ = (
        CheckConstraint("provider_type IN ('payment','logistics','notification','financial','other')", name="ck_provider_registry_type"),
        CheckConstraint("status IN ('discovered','contract_required','api_pending','integrating','testing','certified','production','suspended')", name="ck_provider_registry_status"),
        CheckConstraint("integration_mode IN ('none','manual','api','webhook','hybrid')", name="ck_provider_registry_integration"),
    )


class ProviderMarketCapability(Base):
    __tablename__ = "provider_market_capabilities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("provider_registry_entries.id", ondelete="CASCADE"), nullable=False)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False)
    capability: Mapped[str] = mapped_column(String(80), nullable=False)
    # Empty string means provider capability is not restricted to a specific rail/currency.
    # Keeping these fields non-null makes the uniqueness invariant portable across SQLite/PostgreSQL.
    rail: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        UniqueConstraint("provider_id", "market_id", "capability", "rail", "currency", name="uq_provider_market_capability"),
        Index("ix_provider_market_market", "market_id"),
    )


class PaymentMethodCatalogEntry(Base):
    __tablename__ = "payment_method_catalog"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("market_contexts.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    method_type: Mapped[str] = mapped_column(String(30), nullable=False)
    requires_provider: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    __table_args__ = (
        UniqueConstraint("market_id", "code", name="uq_payment_method_market_code"),
        CheckConstraint("method_type IN ('wallet','bank','card','transfer','cash','cod')", name="ck_payment_method_type"),
    )
