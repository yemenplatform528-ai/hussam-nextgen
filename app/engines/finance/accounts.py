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


class AccountPostingError(ValueError):
    """Raised when a journal line does not resolve to a valid tenant account."""


def validate_posting_accounts(session: Session, *, tenant_id: int, currency: str,
                              account_codes: list[str], allow_inactive: bool = False) -> None:
    normalized_currency = str(currency or "").strip().upper()
    codes = [str(code or "").strip() for code in account_codes]
    if tenant_id <= 0 or not normalized_currency or not codes or any(not code for code in codes):
        raise AccountPostingError("valid tenant, currency and account codes are required")

    rows = session.scalars(
        select(Account)
        .where(Account.tenant_id == tenant_id, Account.code.in_(set(codes)))
        .with_for_update()
    ).all()
    by_code = {row.code: row for row in rows}
    missing = set(codes) - set(by_code)
    if missing:
        raise AccountPostingError("posting account not found in tenant chart of accounts")

    for code in set(codes):
        account = by_code[code]
        if not account.active and not allow_inactive:
            raise AccountPostingError("posting account is inactive")
        if account.currency and account.currency.strip().upper() != normalized_currency:
            raise AccountPostingError("posting account currency does not match journal currency")
