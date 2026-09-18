from decimal import Decimal
from fastapi import APIRouter,Depends,Request,HTTPException
from pydantic import BaseModel,Field
from app.api.dependencies import get_context,get_session
from app.engines.payments import PaymentProductionService
from app.core.security.payment_webhook import PaymentWebhookSignatureError, secret_for, verify_signature
router=APIRouter(prefix="/payments",tags=["payments"])
class Intent(BaseModel): reference:str;provider:str;amount:Decimal=Field(gt=0);currency:str;market_id:int;rail:str=''
class Provider(BaseModel):provider_payment_id:str
@router.post("/intents",status_code=201)
def create(body:Intent,ctx=Depends(get_context),db=Depends(get_session)):
    x=PaymentProductionService(db).create_intent(ctx.tenant_id,body.reference,body.provider,body.amount,body.currency,market_id=body.market_id,rail=body.rail);return {"id":x.id,"reference":x.reference,"status":x.status,"amount":str(x.amount),"currency":x.currency}
@router.post("/intents/{reference}/processing")
def processing(reference:str,ctx=Depends(get_context),db=Depends(get_session)):
    x=PaymentProductionService(db).mark_processing(ctx.tenant_id,reference);return {"reference":x.reference,"status":x.status}
@router.post("/intents/{reference}/provider")
def provider(reference:str,body:Provider,ctx=Depends(get_context),db=Depends(get_session)):
    x=PaymentProductionService(db).attach_provider_payment(ctx.tenant_id,reference,body.provider_payment_id);return {"reference":x.reference,"provider_payment_id":x.provider_payment_id}

class Webhook(BaseModel):
    tenant_id:int; provider:str; event_id:str; event_type:str; payment_reference:str; provider_payment_id:str|None=None; status:str|None=None; payload:dict|None=None
class Settlement(BaseModel):
    settlement_reference:str; actual_amount:Decimal=Field(gt=0); currency:str; posting_date:str

@router.post("/webhooks")
def webhook(body:Webhook,ctx=Depends(get_context),db=Depends(get_session)):
    if body.tenant_id != ctx.tenant_id:
        raise HTTPException(status_code=403, detail="tenant mismatch")
    x=PaymentProductionService(db).process_webhook(ctx.tenant_id, **body.model_dump(exclude={"tenant_id"})); return {"reference":x.reference,"status":x.status,"provider_payment_id":x.provider_payment_id}

@router.post("/webhooks/signed")
async def signed_webhook(request: Request, db=Depends(get_session)):
    raw = await request.body()
    try:
        body = Webhook.model_validate_json(raw)
        timestamp = request.headers.get("X-Payment-Timestamp", "")
        signature = request.headers.get("X-Payment-Signature", "")
        secret = secret_for(provider=body.provider, tenant_id=body.tenant_id)
        verify_signature(raw_body=raw, timestamp=timestamp, signature=signature, secret=secret)
    except (PaymentWebhookSignatureError, ValueError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    x=PaymentProductionService(db).process_webhook(body.tenant_id, **body.model_dump(exclude={"tenant_id"}))
    return {"reference":x.reference,"status":x.status,"provider_payment_id":x.provider_payment_id,"accepted":"signed"}


@router.post("/intents/{reference}/capture")
def capture(reference:str, posting_date:str,ctx=Depends(get_context),db=Depends(get_session)):
    from datetime import date
    x=PaymentProductionService(db).capture(ctx.tenant_id, reference, posting_date=date.fromisoformat(posting_date), actor_id=ctx.user_id); return {"reference":x.reference,"status":x.status}

class Refund(BaseModel):
    refund_reference:str; amount:Decimal=Field(gt=0); currency:str; reason:str

@router.post("/intents/{reference}/refunds", status_code=201)
def refund(reference:str,body:Refund,ctx=Depends(get_context),db=Depends(get_session)):
    x=PaymentProductionService(db).create_refund(ctx.tenant_id, reference, refund_reference=body.refund_reference, amount=body.amount, currency=body.currency, reason=body.reason)
    return {"reference":x.refund_reference,"payment_reference":x.payment_reference,"status":x.status,"amount":str(x.amount),"currency":x.currency}

class RefundCompletion(BaseModel):
    provider_refund_id:str

@router.post("/refunds/{refund_reference}/complete")
def complete_refund(refund_reference:str,body:RefundCompletion,ctx=Depends(get_context),db=Depends(get_session)):
    x=PaymentProductionService(db).complete_refund(ctx.tenant_id, refund_reference, provider_refund_id=body.provider_refund_id)
    return {"reference":x.refund_reference,"status":x.status,"provider_refund_id":x.provider_refund_id}

@router.post("/intents/{reference}/settle")
def settle(reference:str,body:Settlement,ctx=Depends(get_context),db=Depends(get_session)):
    from datetime import date
    x=PaymentProductionService(db).settle(ctx.tenant_id, reference, settlement_reference=body.settlement_reference, actual_amount=body.actual_amount, currency=body.currency, posting_date=date.fromisoformat(body.posting_date), actor_id=ctx.user_id); return {"reference":x.reference,"status":x.status}
