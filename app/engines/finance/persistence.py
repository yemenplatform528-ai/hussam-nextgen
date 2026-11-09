from sqlalchemy.orm import Session
from app.core.contracts import JournalCommand
from app.engines.finance.service import AccountingInvariantError
from app.engines.finance.production import FinanceError, PostingLine, post_journal

class FinancePersistenceService:
    def __init__(self, db: Session): self.db = db
    def post(self, tenant_id: int, command: JournalCommand) -> Journal:
        if command.posting_date is None:
            raise AccountingInvariantError("posting date is required")
        try:
            j = post_journal(
                self.db, tenant_id=tenant_id, reference=command.reference,
                currency=command.currency, posting_date=command.posting_date,
                lines=[PostingLine(x.account, debit=x.debit, credit=x.credit) for x in command.lines],
            )
            self.db.commit(); self.db.refresh(j); return j
        except FinanceError as exc:
            self.db.rollback()
            raise AccountingInvariantError(str(exc)) from exc
