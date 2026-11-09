from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.contracts import JournalCommand
from app.core.models import Journal, JournalLineRecord
from app.engines.finance.service import AccountingService, AccountingInvariantError
from app.engines.finance.accounts import AccountPostingError, validate_posting_accounts

class FinancePersistenceService:
    def __init__(self, db: Session): self.db = db
    def post(self, tenant_id: int, command: JournalCommand) -> Journal:
        AccountingService().validate_posting(command)
        account_codes = [str(line.account or "").strip() for line in command.lines]
        try:
            validate_posting_accounts(self.db, tenant_id=tenant_id, currency=command.currency,
                                      account_codes=account_codes)
        except AccountPostingError as exc:
            raise AccountingInvariantError(str(exc)) from exc
        if self.db.scalar(select(Journal).where(Journal.tenant_id == tenant_id, Journal.reference == command.reference.strip())):
            raise AccountingInvariantError("duplicate journal reference")
        j = Journal(tenant_id=tenant_id, reference=command.reference.strip(), currency=command.currency.strip().upper(), status="posted")
        self.db.add(j); self.db.flush()
        self.db.add_all([JournalLineRecord(journal_id=j.id, account=code, debit=x.debit, credit=x.credit) for x, code in zip(command.lines, account_codes)])
        self.db.commit(); self.db.refresh(j); return j
