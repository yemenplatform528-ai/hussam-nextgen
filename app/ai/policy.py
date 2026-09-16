"""Deterministic AI policy boundary.

The model is never the security boundary. This module is deliberately free of
provider SDKs and prompt interpretation.
"""
from __future__ import annotations
from dataclasses import dataclass
from .contracts import ActionClass, DataClass, ToolContract, AgentContract


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    reason: str


MUTATING_CLASSES = {ActionClass.CONFIRM, ActionClass.EXECUTE}


def authorize_tool(agent: AgentContract, tool: ToolContract) -> PolicyDecision:
    if tool.code not in agent.tool_codes:
        return PolicyDecision(False, True, "tool_not_granted_to_agent")
    if any(cls not in agent.data_classes for cls in tool.data_classes):
        return PolicyDecision(False, True, "data_class_not_granted_to_agent")
    if tool.action_class in MUTATING_CLASSES and agent.approval_mode != "autonomous_allowed":
        return PolicyDecision(True, True, "human_approval_required_for_mutation")
    if tool.risk_class in {"high", "critical"}:
        return PolicyDecision(True, True, "high_risk_requires_approval")
    return PolicyDecision(True, tool.requires_approval, "policy_allowed")


def sanitize_external_context(items: list) -> list:
    """Mark external/tool output as data, never instructions."""
    sanitized = []
    for item in items:
        if isinstance(item, dict):
            x = dict(item)
            x["trusted"] = False
            x["kind"] = x.get("kind", "external_data")
            sanitized.append(x)
        else:
            sanitized.append({"source": "external", "kind": "external_data", "trusted": False, "content": item})
    return sanitized
