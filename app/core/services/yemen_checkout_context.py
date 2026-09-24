from sqlalchemy import or_, select

from app.core.models.market import MarketContext, MarketCoverage, MarketGeography, PaymentMethodCatalogEntry
from app.core.models.marketplace import (
    MarketplaceAddress,
    MarketplaceSellerProfile,
    MarketplaceShippingRate,
)
from app.core.services.market_context import MarketContextService


class YemenCheckoutContextService:
    """Build a deterministic, client-safe Yemen checkout context.

    This service composes existing market, address and shipping primitives.
    It never converts money and never certifies an external payment provider.
    """

    def __init__(self, db):
        self.db = db
        self.market_context = MarketContextService(db)

    def build(
        self,
        market_code: str,
        *,
        user_id: str | None = None,
        address_id: int | None = None,
        seller_tenant_ids: list[int] | None = None,
    ) -> dict:
        market = self.market_context.get_market(market_code)
        if market is None:
            raise ValueError("market not found")
        if market.status != "active":
            raise ValueError("market is not active")

        runtime = self.market_context.runtime_context(market)
        address = None
        if address_id is not None:
            if not user_id:
                raise ValueError("user context is required for address selection")
            address = self.db.scalar(
                select(MarketplaceAddress).where(
                    MarketplaceAddress.id == address_id,
                    MarketplaceAddress.user_id == user_id,
                    MarketplaceAddress.active.is_(True),
                    MarketplaceAddress.market_id == market.id,
                )
            )
            if address is None:
                raise ValueError("delivery address is not available in this market")

        methods = [
            {
                "code": item["code"],
                "name": item["name"],
                "method_type": item["method_type"],
                "requires_provider": item["requires_provider"],
                "available": True,
            }
            for item in runtime["payments"]["methods"]
        ]
        cod_available = any(
            item["method_type"] == "cod" or item["code"].lower() in {"cod", "cash_on_delivery"}
            for item in methods
        )

        delivery = runtime["delivery"].get("configuration", {})
        modes = delivery.get("modes", [])
        if not isinstance(modes, list):
            modes = []

        address_context = None
        if address is not None:
            covered = self._coverage_status(market.id, address)
            address_context = {
                "id": address.id,
                "market_id": address.market_id,
                "country_code": address.country_code,
                "governorate": address.governorate,
                "city": address.city,
                "governorate_id": address.governorate_id,
                "district_id": address.district_id,
                "locality_id": address.locality_id,
                "coverage": covered,
            }

        sellers = []
        for seller_id in seller_tenant_ids or []:
            sellers.append(self._seller_context(market, seller_id, address))

        return {
            "schema_version": "1.0",
            "market": {
                "code": market.code,
                "id": market.id,
                "country_code": market.country_code,
                "locale": market.locale,
                "timezone": market.timezone,
            },
            "money": {
                "currency": market.default_currency,
                "label": self._currency_label(runtime, market.default_currency),
                "conversion": {
                    "required_source_context": True,
                    "automatic_conversion": False,
                },
            },
            "delivery": {
                "modes": modes,
                "destination": address_context,
            },
            "payments": {
                "methods": methods,
                "cod": {"available": cod_available},
            },
            "sellers": sellers,
        }

    def _currency_label(self, runtime: dict, currency: str) -> str:
        units = [
            unit for unit in runtime["money"]["money_units"]
            if unit["currency"] == currency
        ]
        if not units:
            return currency
        preferred = next((x for x in units if x["variant"] == "current"), units[0])
        return preferred.get("name_ar") or preferred.get("name") or currency

    def _coverage_status(self, market_id: int, address) -> str:
        geo_ids = [
            address.locality_id,
            address.district_id,
            address.governorate_id,
        ]
        geo_ids = [x for x in geo_ids if x is not None]
        if not geo_ids:
            return "unknown"

        row = self.db.execute(
            select(MarketCoverage.status, MarketGeography.level)
            .join(MarketGeography, MarketGeography.id == MarketCoverage.geography_id)
            .where(
                MarketCoverage.market_id == market_id,
                MarketGeography.market_id == market_id,
                MarketCoverage.geography_id.in_(geo_ids),
                MarketGeography.status == "active",
            )
            .order_by(MarketGeography.level.desc())
        ).first()
        return row.status if row else "unknown"

    def _seller_context(self, market: MarketContext, seller_tenant_id: int, address):
        seller = self.db.scalar(
            select(MarketplaceSellerProfile).where(
                MarketplaceSellerProfile.tenant_id == seller_tenant_id,
                MarketplaceSellerProfile.status == "active",
            )
        )
        if seller is None:
            raise ValueError("seller is not active")

        currency = market.default_currency
        cod_available = bool(
            self.db.scalar(
                select(PaymentMethodCatalogEntry.id).where(
                    PaymentMethodCatalogEntry.market_id == market.id,
                    PaymentMethodCatalogEntry.active.is_(True),
                    or_(
                        PaymentMethodCatalogEntry.method_type == "cod",
                        PaymentMethodCatalogEntry.code.in_({"cod", "cash_on_delivery"}),
                    ),
                ).limit(1)
            )
        )
        rate_available = False
        if address is not None:
            predicates = []
            if address.locality_id is not None:
                predicates.append(MarketplaceShippingRate.locality_id == address.locality_id)
            if address.district_id is not None:
                predicates.append(MarketplaceShippingRate.district_id == address.district_id)
            if address.governorate_id is not None:
                predicates.append(MarketplaceShippingRate.governorate_id == address.governorate_id)
            if predicates:
                rate = self.db.scalar(
                    select(MarketplaceShippingRate).where(
                        MarketplaceShippingRate.seller_tenant_id == seller_tenant_id,
                        MarketplaceShippingRate.market_id == market.id,
                        MarketplaceShippingRate.currency == currency,
                        MarketplaceShippingRate.active.is_(True),
                        or_(*predicates),
                    ).order_by(
                        MarketplaceShippingRate.locality_id.is_(None),
                        MarketplaceShippingRate.district_id.is_(None),
                        MarketplaceShippingRate.governorate_id.is_(None),
                    )
                )
                rate_available = rate is not None

        return {
            "seller_tenant_id": seller_tenant_id,
            "currency": currency,
            "delivery": {
                "available": rate_available,
                "requires_address": address is None,
            },
            "payment": {
                "cod_available": cod_available,
            },
        }
