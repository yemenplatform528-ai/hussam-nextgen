import json
from sqlalchemy import select

from app.core.models.market import (
    MarketContext,
    MarketCoverage,
    MarketCurrency,
    MarketGeography,
    MarketMoneyUnit,
    PaymentMethodCatalogEntry,
)
from app.core.services.capabilities import CapabilityService


class MarketContextService:
    """Resolve one governed market into a reusable runtime context.

    This is a composition boundary only: domain services remain authoritative
    for money, geography, payments, logistics, and other business behavior.
    """

    def __init__(self, db):
        self.db = db
        self.capabilities = CapabilityService(db)

    def get_market(self, market_code: str) -> MarketContext | None:
        return self.db.scalar(
            select(MarketContext).where(MarketContext.code == market_code.upper())
        )

    @staticmethod
    def _json_object(value):
        if not value:
            return {}
        if isinstance(value, dict):
            return value
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def runtime_context(self, market: MarketContext) -> dict:
        currencies = self.db.scalars(
            select(MarketCurrency)
            .where(MarketCurrency.market_id == market.id)
            .order_by(MarketCurrency.currency)
        ).all()
        money_units = self.db.scalars(
            select(MarketMoneyUnit)
            .where(
                MarketMoneyUnit.market_id == market.id,
                MarketMoneyUnit.status == "active",
            )
            .order_by(MarketMoneyUnit.code)
        ).all()
        payment_methods = self.db.scalars(
            select(PaymentMethodCatalogEntry)
            .where(
                PaymentMethodCatalogEntry.market_id == market.id,
                PaymentMethodCatalogEntry.active.is_(True),
            )
            .order_by(PaymentMethodCatalogEntry.code)
        ).all()
        coverage = self.db.execute(
            select(MarketCoverage, MarketGeography)
            .join(
                MarketGeography,
                MarketGeography.id == MarketCoverage.geography_id,
            )
            .where(
                MarketCoverage.market_id == market.id,
                MarketCoverage.status.in_({"available", "limited"}),
                MarketGeography.status == "active",
            )
            .order_by(MarketGeography.level, MarketGeography.code)
        ).all()
        activations = self.capabilities.list_market_activations(market)
        activation_by_code = {
            capability.code: activation
            for activation, capability in activations
        }

        def active_configuration(code: str) -> dict:
            activation = activation_by_code.get(code)
            if activation is None or activation.status != "active":
                return {}
            return self._json_object(activation.configuration)

        document_configuration = active_configuration("yem_arabic_documents")
        notification_configuration = active_configuration("yem_notification_channels")
        ai_hus_configuration = active_configuration("yem_ai_hus_context")
        local_pricing_configuration = active_configuration("yem_local_pricing")
        business_verticals_configuration = active_configuration("yem_business_verticals")
        branch_warehouse_configuration = active_configuration("yem_branch_warehouse_network")
        local_reporting_configuration = active_configuration("yem_local_reporting")

        return {
            "market": {
                "code": market.code,
                "country_code": market.country_code,
                "name": market.name,
                "locale": market.locale,
                "timezone": market.timezone,
                "default_currency": market.default_currency,
                "status": market.status,
                "configuration": self._json_object(market.configuration_json),
            },
            "money": {
                "currencies": [
                    {
                        "currency": x.currency,
                        "is_default": x.is_default,
                        "cash_supported": x.cash_supported,
                        "electronic_supported": x.electronic_supported,
                    }
                    for x in currencies
                ],
                "money_units": [
                    {
                        "code": x.code,
                        "currency": x.currency,
                        "variant": x.variant,
                        "name": x.name,
                        "name_ar": x.name_ar,
                        "metadata": self._json_object(x.metadata_json),
                    }
                    for x in money_units
                ],
            },
            "payments": {
                "methods": [
                    {
                        "code": x.code,
                        "name": x.name,
                        "method_type": x.method_type,
                        "requires_provider": x.requires_provider,
                    }
                    for x in payment_methods
                ],
            },
            "geography": {
                "coverage": [
                    {
                        "code": geography.code,
                        "level": geography.level,
                        "name": geography.name,
                        "name_ar": geography.name_ar,
                        "status": coverage_row.status,
                    }
                    for coverage_row, geography in coverage
                ],
            },
            "delivery": {
                "configuration": (
                    activation_by_code["yem_delivery_modes"].configuration
                    if "yem_delivery_modes" in activation_by_code
                    and activation_by_code["yem_delivery_modes"].status == "active"
                    else {}
                ),
            },
            "connectivity": {
                "configuration": (
                    activation_by_code["yem_connectivity_policy"].configuration
                    if "yem_connectivity_policy" in activation_by_code
                    and activation_by_code["yem_connectivity_policy"].status == "active"
                    else {}
                ),
            },
            "documents": {
                "configuration": document_configuration,
                "lifecycle": ["draft", "finalized", "void"],
                "versioned": True,
                "immutable_versions": True,
            },
            "notifications": {
                "configuration": notification_configuration,
                "channels": notification_configuration.get("channels", ["in_app"]),
                "tenant_scoped": True,
            },
            "ai_hus": {
                "configuration": ai_hus_configuration,
                "market_context": {
                    "market_code": market.code,
                    "country_code": market.country_code,
                    "locale": market.locale,
                    "timezone": market.timezone,
                    "default_currency": market.default_currency,
                },
                "governance": {
                    "ai_proposes_not_authorizes": True,
                    "hus_uses_domain_contracts": True,
                },
            },
            "capabilities": [
                {
                    "code": capability.code,
                    "category": capability.category,
                    "status": activation.status,
                    "configuration": activation.configuration,
                }
                for activation, capability in activations
            ],
        }
