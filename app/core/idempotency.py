from dataclasses import dataclass

@dataclass(frozen=True)
class IdempotencyKey:
    tenant_id: int
    key: str

class IdempotencyConflict(Exception):
    pass
