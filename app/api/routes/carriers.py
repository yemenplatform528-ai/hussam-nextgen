from datetime import datetime
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from app.api.dependencies import get_context, get_session
from app.engines.carriers import CarrierLifecycleService, CarrierError

router = APIRouter(prefix='/carriers', tags=['carriers'])

class CarrierIn(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    secret_ref: str | None = Field(default=None, max_length=255)

class CarrierEventIn(BaseModel):
    external_event_id: str = Field(min_length=1, max_length=255)
    shipment_reference: str = Field(min_length=1, max_length=255)
    event_type: str = Field(min_length=1, max_length=80)
    payload: dict
    location: str | None = None
    note: str | None = None
    occurred_at: datetime | None = None

@router.post('', status_code=201)
def register(body: CarrierIn, ctx=Depends(get_context), db=Depends(get_session)):
    try:
        x = CarrierLifecycleService(db).register(ctx.tenant_id, body.code, body.name, body.secret_ref)
        return {'id': x.id, 'code': x.code, 'name': x.name, 'active': x.active}
    except CarrierError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.post('/events')
def event(body: CarrierEventIn, x_carrier_signature: str = Header(default=''), x_carrier_code: str = Header(default=''), ctx=Depends(get_context), db=Depends(get_session)):
    if not x_carrier_code:
        raise HTTPException(status_code=400, detail='X-Carrier-Code is required')
    try:
        x = CarrierLifecycleService(db).ingest_event(ctx.tenant_id, x_carrier_code, external_event_id=body.external_event_id,
            shipment_reference=body.shipment_reference, event_type=body.event_type, payload=body.payload,
            signature=x_carrier_signature, location=body.location, note=body.note, occurred_at=body.occurred_at)
        return {'id': x.id, 'reference': x.reference, 'status': x.status}
    except CarrierError as e:
        message = str(e)
        status = 401 if 'signature' in message else 400
        raise HTTPException(status_code=status, detail=message)
    except Exception as e:
        if isinstance(e, ValueError): raise HTTPException(status_code=400, detail=str(e))
        raise
