from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.contracts import JournalCommand
from app.core.models import FiscalPeriod, ExchangeRate
from app.engines.finance.production import FinanceError, PostingLine, post_journal, reverse_journal

class FinanceLifecycleError(ValueError): pass

class FinanceLifecycleService:
    def __init__(self, db: Session): self.db=db
    def open_period(self, tenant_id:int, name:str, starts_on:date, ends_on:date):
        if starts_on > ends_on: raise FinanceLifecycleError('period dates are invalid')
        p=FiscalPeriod(tenant_id=tenant_id,name=name.strip(),starts_on=starts_on,ends_on=ends_on,closed=False); self.db.add(p); self.db.commit(); self.db.refresh(p); return p
    def close_period(self, tenant_id:int, period_id:int):
        p=self.db.scalar(select(FiscalPeriod).where(FiscalPeriod.id==period_id,FiscalPeriod.tenant_id==tenant_id))
        if not p: raise FinanceLifecycleError('period not found')
        p.closed=True; self.db.commit(); return p
    def post(self, tenant_id:int, command:JournalCommand, posting_date:date|None=None):
        effective_date = posting_date or command.posting_date
        if effective_date is None:
            raise FinanceLifecycleError('posting date is required')
        try:
            journal = post_journal(
                self.db, tenant_id=tenant_id, reference=command.reference,
                currency=command.currency, posting_date=effective_date,
                lines=[PostingLine(x.account, debit=x.debit, credit=x.credit) for x in command.lines],
            )
            self.db.commit(); self.db.refresh(journal); return journal
        except FinanceError as exc:
            self.db.rollback()
            raise FinanceLifecycleError(str(exc)) from exc
    def reverse(self, tenant_id:int, journal_id:int, reference:str, reversal_date:date):
        try:
            reversal = reverse_journal(
                self.db, tenant_id=tenant_id, journal_id=journal_id,
                reversal_reference=reference, reversal_date=reversal_date,
            )
            self.db.commit(); self.db.refresh(reversal); return reversal
        except FinanceError as exc:
            self.db.rollback()
            raise FinanceLifecycleError(str(exc)) from exc
    def set_exchange_rate(self, tenant_id:int, base:str, quote:str, rate:Decimal):
        if rate <= 0 or base.strip().upper()==quote.strip().upper(): raise FinanceLifecycleError('invalid exchange rate')
        r=ExchangeRate(tenant_id=tenant_id,base_currency=base.strip().upper(),quote_currency=quote.strip().upper(),rate=rate); self.db.add(r); self.db.commit(); self.db.refresh(r); return r
