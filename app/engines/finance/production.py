from dataclasses import dataclass
import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import select

from app.core.models.core import Journal, JournalLineRecord
from app.core.models.finance import FiscalPeriod, JournalLink
from app.core.security.context import TenantAccessDenied

class FinanceError(ValueError):
    pass

@dataclass(frozen=True)
class PostingLine:
    account_id: str
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")

def _validate_lines(lines):
    if not lines:
        raise FinanceError("journal requires at least one line")
    td = Decimal("0"); tc = Decimal("0")
    for line in lines:
        d, c = Decimal(str(line.debit)), Decimal(str(line.credit))
        if d < 0 or c < 0:
            raise FinanceError("debit and credit must be non-negative")
        if (d > 0 and c > 0) or (d == 0 and c == 0):
            raise FinanceError("each line must contain debit OR credit")
        td += d; tc += c
    if td != tc or td <= 0:
        raise FinanceError("journal must balance with a positive total")
    return td

def _open_period(session, tenant_id, posting_date):
    periods = session.scalars(select(FiscalPeriod).where(
        FiscalPeriod.tenant_id == tenant_id,
        FiscalPeriod.starts_on <= posting_date,
        FiscalPeriod.ends_on >= posting_date,
        FiscalPeriod.closed.is_(False),
    )).all()
    if len(periods) != 1:
        raise FinanceError("posting date is not in exactly one open fiscal period")
    return periods[0]

def post_journal(session, *, tenant_id: int, reference: str, currency: str,
                 posting_date: date, lines, actor_id: str | None = None) -> Journal:
    if tenant_id <= 0:
        raise TenantAccessDenied("valid tenant context is required")
    if not reference or not currency:
        raise FinanceError("reference and currency are required")
    _validate_lines(lines)
    _open_period(session, tenant_id, posting_date)
    if session.scalar(select(Journal).where(
        Journal.tenant_id == tenant_id, Journal.reference == reference)):
        raise FinanceError("duplicate journal reference")
    journal = Journal(tenant_id=tenant_id, reference=reference.strip(), currency=currency.strip().upper(),
                      status="posted", posting_date=posting_date, created_at=datetime.now(timezone.utc))
    session.add(journal); session.flush()
    for line in lines:
        session.add(JournalLineRecord(
            journal_id=journal.id, account=str(line.account_id),
            debit=Decimal(str(line.debit)), credit=Decimal(str(line.credit))))
    session.flush()
    line_records = session.scalars(select(JournalLineRecord).where(JournalLineRecord.journal_id == journal.id).order_by(JournalLineRecord.id)).all()
    payload = '|'.join(f'{x.account}|{Decimal(str(x.debit)):.4f}|{Decimal(str(x.credit)):.4f}' for x in line_records)
    payload = f'{journal.tenant_id}|{journal.reference}|{journal.currency}|{journal.posting_date}|{payload}'
    journal.content_hash = hashlib.sha256(payload.encode()).hexdigest()
    session.flush()
    return journal

def reverse_journal(session, *, tenant_id: int, journal_id: int,
                    reversal_reference: str, reversal_date: date) -> Journal:
    original = session.scalar(select(Journal).where(
        Journal.id == journal_id, Journal.tenant_id == tenant_id))
    if original is None:
        raise FinanceError("journal not found in tenant")
    if original.status != "posted":
        raise FinanceError("only posted journals can be reversed")
    if not reversal_reference:
        raise FinanceError("reversal reference is required")
    if session.scalar(select(JournalLink).where(
        JournalLink.tenant_id == tenant_id,
        JournalLink.reversal_of_journal_id == original.id)):
        raise FinanceError("journal has already been reversed")
    _open_period(session, tenant_id, reversal_date)
    original_lines = session.scalars(select(JournalLineRecord).where(
        JournalLineRecord.journal_id == original.id)).all()
    reversed_lines = [PostingLine(
        account_id=x.account, debit=Decimal(x.credit), credit=Decimal(x.debit))
        for x in original_lines]
    reversal = post_journal(session, tenant_id=tenant_id,
        reference=reversal_reference, currency=original.currency,
        posting_date=reversal_date, lines=reversed_lines)
    session.add(JournalLink(tenant_id=tenant_id, journal_id=reversal.id,
                            reversal_of_journal_id=original.id))
    session.flush()
    return reversal
