from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.contracts import JournalCommand
from app.core.models import Journal, JournalLineRecord
from app.engines.finance.service import AccountingService, AccountingInvariantError

class FinancePersistenceService:
    def __init__(self, db: Session): self.db = db
    def post(self, tenant_id: int, command: JournalCommand) -> Journal:
        AccountingService().validate_posting(command)
        if self.db.scalar(select(Journal).where(Journal.tenant_id == tenant_id, Journal.reference == command.reference)):
            raise AccountingInvariantError("duplicate journal reference")
        j = Journal(tenant_id=tenant_id, reference=command.reference.strip(), currency=command.currency.strip().upper(), status="posted")
        self.db.add(j); self.db.flush()
        self.db.add_all([JournalLineRecord(journal_id=j.id, account=x.account, debit=x.debit, credit=x.credit) for x in command.lines])
        self.db.commit(); self.db.refresh(j); return j
