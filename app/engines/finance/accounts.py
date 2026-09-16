from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.models.finance_accounts import Account

VALID_TYPES = {'asset', 'liability', 'equity', 'revenue', 'expense'}


def create_account(session: Session, *, tenant_id: int, code: str, name: str, account_type: str,
                   currency: str | None = None) -> Account:
    code, name, account_type = code.strip(), name.strip(), account_type.strip().lower()
    if tenant_id <= 0 or not code or not name or account_type not in VALID_TYPES:
        raise ValueError('valid tenant, code, name and account type are required')
    if session.scalar(select(Account).where(Account.tenant_id == tenant_id, Account.code == code)):
        raise ValueError('duplicate account code')
    account = Account(tenant_id=tenant_id, code=code, name=name, account_type=account_type,
                      currency=currency.strip().upper() if currency else None, active=True)
    session.add(account); session.flush(); return account


def deactivate_account(session: Session, *, tenant_id: int, code: str) -> Account:
    account = session.scalar(select(Account).where(Account.tenant_id == tenant_id, Account.code == code))
    if account is None:
        raise ValueError('account not found in tenant')
    account.active = False
    session.flush()
    return account
