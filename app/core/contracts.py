from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class JournalLine:
    account: str
    debit: Decimal
    credit: Decimal

@dataclass(frozen=True)
class JournalCommand:
    reference: str
    currency: str
    lines: tuple[JournalLine, ...]

@dataclass(frozen=True)
class StockMovement:
    item_id: str
    warehouse_id: str
    quantity: Decimal
    direction: str
    reference: str
    destination_warehouse_id: str | None = None
