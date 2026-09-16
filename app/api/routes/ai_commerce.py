"""AI-02 governed commerce intelligence API."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.api.dependencies import get_context, get_session
from app.ai.commerce import customer_context, customer_recommendations, seller_intelligence, create_commerce_proposal, build_customer_ai_context

router = APIRouter(tags=["ai-commerce"])

class CommerceQuery(BaseModel):
    query: str | None = Field(default=None, max_length=300)
    market_id: int | None = None
    limit: int = Field(default=10, ge=1, le=50)

class ProposalIn(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    market_id: int | None = None

@router.get("/ai/commerce/customer/context")
def customer_context_endpoint(market_id: int | None = None, ctx=Depends(get_context), db=Depends(get_session)):
    return customer_context(db, ctx.tenant_id, ctx.user_id, market_id)

@router.post("/ai/commerce/customer/recommendations")
def customer_recommendations_endpoint(body: CommerceQuery, ctx=Depends(get_context), db=Depends(get_session)):
    return customer_recommendations(db, ctx.tenant_id, ctx.user_id, body.query, body.market_id, body.limit)

@router.post("/ai/commerce/customer/context-envelope")
def customer_context_envelope(body: CommerceQuery, ctx=Depends(get_context), db=Depends(get_session)):
    return build_customer_ai_context(db, ctx.tenant_id, ctx.user_id, body.query or "", body.market_id).as_prompt_data()

@router.get("/ai/commerce/seller/intelligence")
def seller_intelligence_endpoint(market_id: int | None = None, ctx=Depends(get_context), db=Depends(get_session)):
    return seller_intelligence(db, ctx.tenant_id, market_id)

@router.post("/ai/commerce/seller/proposals", status_code=201)
def seller_proposal(body: ProposalIn, ctx=Depends(get_context), db=Depends(get_session)):
    return create_commerce_proposal(db, ctx.tenant_id, ctx.user_id, body.goal, market_id=body.market_id)
