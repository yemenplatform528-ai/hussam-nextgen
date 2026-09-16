from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.contracts import JournalCommand, JournalLine
from app.core.models import FiscalPeriod, Journal, JournalLineRecord, JournalLink, ExchangeRate
from app.engines.finance.service import AccountingService, AccountingInvariantError

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
        AccountingService().validate_posting(command)
        if self.db.scalar(select(Journal).where(Journal.tenant_id==tenant_id,Journal.reference==command.reference)):
            raise AccountingInvariantError('duplicate journal reference')
        if posting_date:
            period=self.db.scalar(select(FiscalPeriod).where(FiscalPeriod.tenant_id==tenant_id,FiscalPeriod.starts_on<=posting_date,FiscalPeriod.ends_on>=posting_date))
            if not period: raise FinanceLifecycleError('no fiscal period for posting date')
            if period.closed: raise FinanceLifecycleError('fiscal period is closed')
        j=Journal(tenant_id=tenant_id,reference=command.reference.strip(),currency=command.currency.strip().upper(),status='posted')
        self.db.add(j); self.db.flush(); self.db.add_all([JournalLineRecord(journal_id=j.id,account=x.account,debit=x.debit,credit=x.credit) for x in command.lines]); self.db.commit(); self.db.refresh(j); return j
    def reverse(self, tenant_id:int, journal_id:int, reference:str):
        original=self.db.scalar(select(Journal).where(Journal.id==journal_id,Journal.tenant_id==tenant_id,Journal.status=='posted'))
        if not original: raise FinanceLifecycleError('posted journal not found')
        if self.db.scalar(select(JournalLink).where(JournalLink.tenant_id==tenant_id,JournalLink.reversal_of_journal_id==journal_id)):
            raise FinanceLifecycleError('journal already reversed')
        lines=self.db.scalars(select(JournalLineRecord).where(JournalLineRecord.journal_id==journal_id)).all()
        cmd=JournalCommand(reference,original.currency,tuple(JournalLine(x.account,Decimal(str(x.credit)),Decimal(str(x.debit))) for x in lines))
        reversal=self.post(tenant_id,cmd)
        self.db.add(JournalLink(tenant_id=tenant_id,journal_id=reversal.id,reversal_of_journal_id=journal_id)); self.db.commit(); return reversal
    def set_exchange_rate(self, tenant_id:int, base:str, quote:str, rate:Decimal):
        if rate <= 0 or base.strip().upper()==quote.strip().upper(): raise FinanceLifecycleError('invalid exchange rate')
        r=ExchangeRate(tenant_id=tenant_id,base_currency=base.strip().upper(),quote_currency=quote.strip().upper(),rate=rate); self.db.add(r); self.db.commit(); self.db.refresh(r); return r
