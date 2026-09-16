from decimal import Decimal
import pytest
from app.core.money import money
from app.core.contracts import JournalCommand, JournalLine, StockMovement
from app.engines.finance.service import AccountingService, AccountingInvariantError
from app.engines.inventory.service import InventoryService, InventoryInvariantError


def test_money_is_decimal():
    assert money("10.005") == Decimal("10.01")
    assert isinstance(money("2"), Decimal)


def test_balanced_journal_passes():
    cmd = JournalCommand("SALE-1", "YER", (
        JournalLine("cash", Decimal("100"), Decimal("0")),
        JournalLine("sales", Decimal("0"), Decimal("100")),
    ))
    AccountingService().validate_posting(cmd)


def test_unbalanced_journal_fails():
    cmd = JournalCommand("BAD-1", "YER", (
        JournalLine("cash", Decimal("100"), Decimal("0")),
        JournalLine("sales", Decimal("0"), Decimal("90")),
    ))
    with pytest.raises(AccountingInvariantError):
        AccountingService().validate_posting(cmd)


def test_inventory_movement_requires_positive_quantity():
    movement = StockMovement("item", "wh-1", Decimal("0"), "in", "GRN-1")
    with pytest.raises(InventoryInvariantError):
        InventoryService().validate_movement(movement)
