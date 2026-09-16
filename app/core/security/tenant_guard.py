from sqlalchemy import Select

from app.core.security.context import TenantAccessDenied, RequestContext

def require_tenant(ctx: RequestContext, tenant_id: int) -> None:
    if ctx.tenant_id != tenant_id:
        raise TenantAccessDenied("cross-tenant access denied")

def scope_statement(statement: Select, tenant_column, ctx: RequestContext) -> Select:
    return statement.where(tenant_column == ctx.tenant_id)
