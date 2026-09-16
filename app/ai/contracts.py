"""Provider-neutral contracts for the governed intelligence plane."""
from __future__ import annotations
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field


class ActionClass(StrEnum):
    READ = "read"
    ANALYZE = "analyze"
    PROPOSE = "propose"
    CONFIRM = "confirm"
    EXECUTE = "execute"


class MemoryType(StrEnum):
    CONVERSATION = "conversation"
    USER_PREFERENCE = "user_preference"
    BUSINESS = "business"
    OPERATIONAL = "operational"
    ORGANIZATIONAL = "organizational"
    AGENT_WORKING = "agent_working"


class DataClass(StrEnum):
    PUBLIC = "public"
    TENANT = "tenant"
    PERSONAL = "personal"
    FINANCIAL = "financial"
    SECURITY = "security"
    SECRET = "secret"


class ContextItem(BaseModel):
    source: str
    kind: str
    data_class: DataClass = DataClass.TENANT
    trusted: bool = False
    content: Any


class ToolContract(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    description: str
    action_class: ActionClass
    risk_class: str = "low"
    data_classes: list[DataClass] = Field(default_factory=list)
    requires_approval: bool = True
    idempotent: bool = False
    input_schema: dict[str, Any] = Field(default_factory=dict)


class AgentContract(BaseModel):
    code: str
    role: str
    scopes: list[str] = Field(default_factory=list)
    tool_codes: list[str] = Field(default_factory=list)
    data_classes: list[DataClass] = Field(default_factory=list)
    risk_class: str = "low"
    approval_mode: str = "human_required"


class ModelRouteRequest(BaseModel):
    task_class: str
    required_data_classes: list[DataClass] = Field(default_factory=list)
    requires_structured_output: bool = False
    requires_tool_calling: bool = False


class ModelRouteDecision(BaseModel):
    provider_code: str
    model_code: str
    route_code: str
    reason: str
