from contextvars import ContextVar
from dataclasses import dataclass

_current: ContextVar["TenantContext | None"] = ContextVar("tenant_context", default=None)

@dataclass(frozen=True)
class TenantContext:
    tenant_id: int
    user_id: str
    role: str


def set_context(ctx: TenantContext):
    return _current.set(ctx)


def get_context() -> TenantContext:
    ctx = _current.get()
    if ctx is None:
        raise RuntimeError("tenant context is required")
    return ctx
