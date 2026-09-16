from decimal import Decimal
from app.core.contracts import JournalCommand
from app.core.money import money

class AccountingInvariantError(ValueError):
    pass

class AccountingService:
    """Domain-facing accounting boundary. Persistence is intentionally behind this contract."""
    def validate_posting(self, command: JournalCommand) -> None:
        if not command.lines:
            raise AccountingInvariantError("journal must contain lines")
        debit = sum((money(x.debit) for x in command.lines), Decimal("0"))
        credit = sum((money(x.credit) for x in command.lines), Decimal("0"))
        if debit != credit:
            raise AccountingInvariantError("journal is not balanced")
        if debit <= 0:
            raise AccountingInvariantError("journal total must be positive")
        if not command.reference.strip():
            raise AccountingInvariantError("reference is required")
        if not command.currency.strip():
            raise AccountingInvariantError("currency is required")
        for line in command.lines:
            if line.debit < 0 or line.credit < 0:
                raise AccountingInvariantError("debit/credit cannot be negative")
            if line.debit and line.credit:
                raise AccountingInvariantError("a line cannot be both debit and credit")
