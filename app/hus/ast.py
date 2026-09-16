"""HUS-01 immutable source AST. Syntax only; no authority or execution semantics."""
from dataclasses import dataclass, field
from typing import Any, Tuple

@dataclass(frozen=True)
class Span:
    start: int
    end: int
    line: int
    column: int

@dataclass(frozen=True)
class HUSValue:
    kind: str
    value: Any
    span: Span

@dataclass(frozen=True)
class OrganizationDecl:
    code: str
    name: str
    span: Span

@dataclass(frozen=True)
class DomainDecl:
    code: str
    engine: str
    capabilities: Tuple[str, ...]
    name: str | None = None
    enabled: bool = True
    span: Span | None = None

@dataclass(frozen=True)
class StepDecl:
    code: str
    action: str
    requires_approval: bool = False
    span: Span | None = None

@dataclass(frozen=True)
class WorkflowDecl:
    code: str
    trigger: str
    steps: Tuple[StepDecl, ...]
    name: str | None = None
    enabled: bool = True
    span: Span | None = None

@dataclass(frozen=True)
class PolicyDecl:
    name: str
    values: Tuple[str, ...]
    span: Span | None = None

@dataclass(frozen=True)
class ModuleAST:
    name: str
    version: str
    organization: OrganizationDecl
    domains: Tuple[DomainDecl, ...] = field(default_factory=tuple)
    workflows: Tuple[WorkflowDecl, ...] = field(default_factory=tuple)
    policies: Tuple[PolicyDecl, ...] = field(default_factory=tuple)
    metadata: Tuple[tuple[str, HUSValue], ...] = field(default_factory=tuple)
    span: Span | None = None
