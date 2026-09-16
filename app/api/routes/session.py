from fastapi import APIRouter, Depends
from app.api.dependencies import get_context
router=APIRouter(prefix="/session", tags=["session"])
@router.get("")
def session(ctx=Depends(get_context)):
    return {"user_id":ctx.user_id,"tenant_id":ctx.tenant_id,"membership_id":ctx.membership_id}
