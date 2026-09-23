from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models.market import MarketContext
from app.core.models.yemen_capability import MarketCapabilityActivation, PlatformCapability


class CapabilityService:
    """Application service for governed platform capabilities.

    The service owns capability discovery and market-scope invariants. Domain
    systems remain authoritative for their own behavior; this layer only
    answers whether a governed capability is registered and active for a
    market.
    """

    def __init__(self, db: Session):
        self.db = db

    def active_codes(self) -> set[str]:
        return set(
            self.db.scalars(
                select(PlatformCapability.code).where(
                    PlatformCapability.status == "active"
                )
            ).all()
        )

    def get_active(self, code: str) -> PlatformCapability | None:
        return self.db.scalar(
            select(PlatformCapability).where(
                PlatformCapability.code == code,
                PlatformCapability.status == "active",
            )
        )

    def list_active(self) -> list[PlatformCapability]:
        return self.db.scalars(
            select(PlatformCapability)
            .where(PlatformCapability.status == "active")
            .order_by(PlatformCapability.category, PlatformCapability.code)
        ).all()

    def validate_registered(self, codes: list[str]) -> None:
        unknown = sorted(set(codes) - self.active_codes())
        if unknown:
            raise ValueError({"unregistered_capabilities": unknown})

    def validate_market_scope(self, market: MarketContext, capability: PlatformCapability) -> None:
        if market.status != "active":
            raise ValueError("market must be active before capability activation")
        if capability.market_scope and market.code not in set(capability.market_scope):
            raise ValueError("capability is not scoped to this market")

    def get_market_activation(
        self, market_code: str, capability_code: str
    ) -> MarketCapabilityActivation | None:
        return self.db.scalar(
            select(MarketCapabilityActivation)
            .join(
                PlatformCapability,
                PlatformCapability.id == MarketCapabilityActivation.capability_id,
            )
            .join(
                MarketContext,
                MarketContext.id == MarketCapabilityActivation.market_id,
            )
            .where(
                MarketContext.code == market_code.upper(),
                PlatformCapability.code == capability_code,
            )
        )
