from dataclasses import dataclass

@dataclass(frozen=True)
class IdempotencyResult:
    key: str
    fingerprint: str
    response_code: int
    response_body: dict

class IdempotencyConflict(ValueError):
    pass

def ensure_same_request(
    existing: IdempotencyResult | None,
    key: str,
    fingerprint: str,
) -> IdempotencyResult | None:
    if existing is None:
        return None
    if existing.key != key or existing.fingerprint != fingerprint:
        raise IdempotencyConflict("idempotency key was reused for a different request")
    return existing
