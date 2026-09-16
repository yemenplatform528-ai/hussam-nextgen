from decimal import Decimal
import hashlib
from sqlalchemy import select, func
from app.core.models.core import Journal, JournalLineRecord
from app.core.models.finance_accounts import Account


def account_balance(session, *, tenant_id: int, account_id: str, currency: str) -> Decimal:
    debit = session.scalar(select(func.coalesce(func.sum(JournalLineRecord.debit), 0))
        .join(Journal, Journal.id == JournalLineRecord.journal_id)
        .where(Journal.tenant_id == tenant_id,
               JournalLineRecord.account == str(account_id),
               Journal.currency == currency))
    credit = session.scalar(select(func.coalesce(func.sum(JournalLineRecord.credit), 0))
        .join(Journal, Journal.id == JournalLineRecord.journal_id)
        .where(Journal.tenant_id == tenant_id,
               JournalLineRecord.account == str(account_id),
               Journal.currency == currency))
    return Decimal(str(debit or 0)) - Decimal(str(credit or 0))


def trial_balance(session, *, tenant_id: int, currency: str) -> dict[str, dict[str, Decimal]]:
    rows = session.execute(
        select(JournalLineRecord.account,
               func.coalesce(func.sum(JournalLineRecord.debit), 0),
               func.coalesce(func.sum(JournalLineRecord.credit), 0))
        .join(Journal, Journal.id == JournalLineRecord.journal_id)
        .where(Journal.tenant_id == tenant_id, Journal.currency == currency)
        .group_by(JournalLineRecord.account)
        .order_by(JournalLineRecord.account)
    ).all()
    result = {}
    for account, debit, credit in rows:
        d, c = Decimal(str(debit or 0)), Decimal(str(credit or 0))
        result[str(account)] = {'debit': d, 'credit': c, 'balance': d - c}
    return result


def ledger_totals(session, *, tenant_id: int, currency: str) -> tuple[Decimal, Decimal]:
    rows = trial_balance(session, tenant_id=tenant_id, currency=currency).values()
    return (sum((x['debit'] for x in rows), Decimal('0')), sum((x['credit'] for x in rows), Decimal('0')))


def verify_journal_integrity(session, *, tenant_id: int, journal_id: int) -> bool:
    journal = session.scalar(select(Journal).where(Journal.id == journal_id, Journal.tenant_id == tenant_id))
    if journal is None:
        raise ValueError('journal not found in tenant')
    lines = session.scalars(select(JournalLineRecord).where(JournalLineRecord.journal_id == journal.id).order_by(JournalLineRecord.id)).all()
    payload = '|'.join(f'{x.account}|{Decimal(str(x.debit)):.4f}|{Decimal(str(x.credit)):.4f}' for x in lines)
    payload = f'{journal.tenant_id}|{journal.reference}|{journal.currency}|{journal.posting_date}|{payload}'
    return journal.content_hash == hashlib.sha256(payload.encode()).hexdigest()


def reconcile_control_account(session, *, tenant_id: int, currency: str, account_id: str,
                              expected_balance: Decimal) -> dict[str, object]:
    actual = account_balance(session, tenant_id=tenant_id, account_id=account_id, currency=currency)
    expected = Decimal(str(expected_balance))
    delta = actual - expected
    return {'status': 'matched' if delta == 0 else 'mismatch', 'account': str(account_id),
            'currency': currency, 'expected': expected, 'actual': actual, 'delta': delta}


def account_registry(session, *, tenant_id: int) -> list[Account]:
    return session.scalars(select(Account).where(Account.tenant_id == tenant_id).order_by(Account.code)).all()
