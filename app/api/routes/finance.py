from datetime import date
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field
from app.api.dependencies import get_context,get_session,require_owner_or_admin
from app.engines.finance.production import post_journal,PostingLine
from app.engines.finance.reconciliation import trial_balance,reconcile_control_account
from app.engines.finance.accounts import create_account

router=APIRouter(prefix='/finance',tags=['finance'])
class Line(BaseModel): account_id:str; debit:Decimal=Field(default=0,ge=0); credit:Decimal=Field(default=0,ge=0)
class Journal(BaseModel): reference:str; currency:str; posting_date:date; lines:list[Line]=Field(min_length=2)
class AccountIn(BaseModel): code:str; name:str; account_type:str; currency:str|None=None
class ReconcileIn(BaseModel): account_id:str; currency:str; expected_balance:Decimal

@router.post('/journals',status_code=201)
def journal(body:Journal,ctx=Depends(get_context),db=Depends(get_session)):
    require_owner_or_admin(ctx)
    x=post_journal(db,tenant_id=ctx.tenant_id,reference=body.reference,currency=body.currency,posting_date=body.posting_date,actor_id=ctx.user_id,lines=[PostingLine(**v.model_dump()) for v in body.lines]);db.commit();return {'id':x.id,'reference':x.reference,'status':x.status,'currency':x.currency}

@router.post('/accounts',status_code=201)
def account(body:AccountIn,ctx=Depends(get_context),db=Depends(get_session)):
    require_owner_or_admin(ctx)
    try:
        x=create_account(db,tenant_id=ctx.tenant_id,**body.model_dump());db.commit();return {'id':x.id,'code':x.code,'name':x.name,'account_type':x.account_type,'currency':x.currency,'active':x.active}
    except ValueError as exc:
        db.rollback();raise HTTPException(status_code=409,detail=str(exc))

@router.get('/trial-balance')
def get_trial_balance(currency:str,ctx=Depends(get_context),db=Depends(get_session)):
    rows=trial_balance(db,tenant_id=ctx.tenant_id,currency=currency.strip().upper())
    return {'currency':currency.strip().upper(),'accounts':rows,
            'total_debit':sum((x['debit'] for x in rows.values()),Decimal('0')),
            'total_credit':sum((x['credit'] for x in rows.values()),Decimal('0'))}

@router.post('/reconciliation/control')
def reconcile_control(body:ReconcileIn,ctx=Depends(get_context),db=Depends(get_session)):
    require_owner_or_admin(ctx)
    return reconcile_control_account(db,tenant_id=ctx.tenant_id,account_id=body.account_id,currency=body.currency.strip().upper(),expected_balance=body.expected_balance)
