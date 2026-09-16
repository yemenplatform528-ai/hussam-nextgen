"""HUS-02 typed intermediate representation. Data only; never executable code."""
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass(frozen=True)
class CapabilityRef:
    engine: str
    capability: str
    contract_version: str = "1.0"

@dataclass(frozen=True)
class IRStep:
    id: str
    action: CapabilityRef
    depends_on: tuple[str, ...] = ()
    requires_approval: bool = False
    risk: str = "read"
    timeout_seconds: int = 30
    retry_limit: int = 0
    idempotency_required: bool = False
    compensation: Optional[str] = None

@dataclass(frozen=True)
class IRWorkflow:
    code: str
    trigger: str
    steps: tuple[IRStep, ...]

@dataclass(frozen=True)
class HUSIR:
    ir_version: str
    language_version: str
    compiler_version: str
    capabilities: tuple[CapabilityRef, ...]
    workflows: tuple[IRWorkflow, ...]


def ir_dict(ir: HUSIR) -> dict:
    return asdict(ir)
