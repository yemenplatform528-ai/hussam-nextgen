"""Provider-neutral operational controls for rollback and incident response."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping


class IncidentState(str, Enum):
    DETECTED = "detected"
    TRIAGED = "triaged"
    CONTAINED = "contained"
    RECOVERED = "recovered"
    VALIDATED = "validated"
    CLOSED = "closed"


_INCIDENT_TRANSITIONS = {
    IncidentState.DETECTED: {IncidentState.TRIAGED},
    IncidentState.TRIAGED: {IncidentState.CONTAINED},
    IncidentState.CONTAINED: {IncidentState.RECOVERED},
    IncidentState.RECOVERED: {IncidentState.VALIDATED},
    IncidentState.VALIDATED: {IncidentState.CLOSED},
    IncidentState.CLOSED: set(),
}


class InvalidIncidentTransition(ValueError):
    pass


class RollbackError(ValueError):
    pass


@dataclass(frozen=True)
class OperationalObjective:
    service: str
    rto_minutes: int
    rpo_minutes: int

    def __post_init__(self) -> None:
        if not self.service.strip():
            raise ValueError("service is required")
        if self.rto_minutes <= 0 or self.rpo_minutes < 0:
            raise ValueError("invalid RTO/RPO")


@dataclass(frozen=True)
class ReleaseArtifact:
    version: str
    artifact_sha256: str
    migration_revision: str

    def __post_init__(self) -> None:
        if not self.version.strip() or not self.migration_revision.strip():
            raise ValueError("release version and migration revision are required")
        if len(self.artifact_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.artifact_sha256):
            raise ValueError("artifact_sha256 must be 64 lowercase hexadecimal characters")


@dataclass(frozen=True)
class IncidentAction:
    action: str
    actor: str
    outcome: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.action.strip() or not self.actor.strip() or not self.outcome.strip():
            raise ValueError("incident action fields are required")


@dataclass
class IncidentRecord:
    incident_id: str
    severity: str
    objective: OperationalObjective
    state: IncidentState = IncidentState.DETECTED
    actions: list[IncidentAction] = field(default_factory=list)

    def transition(self, target: IncidentState) -> IncidentState:
        if target not in _INCIDENT_TRANSITIONS[self.state]:
            raise InvalidIncidentTransition(f"{self.state.value} -> {target.value} is not allowed")
        self.state = target
        return self.state

    def record(self, action: IncidentAction) -> None:
        self.actions.append(action)

    def audit(self) -> tuple[Mapping[str, str], ...]:
        return tuple({
            "action": a.action,
            "actor": a.actor,
            "outcome": a.outcome,
            "occurred_at": a.occurred_at.isoformat(),
        } for a in self.actions)


def validate_rollback(previous: ReleaseArtifact, target: ReleaseArtifact, *, migration_compatible: bool) -> None:
    """Validate an application rollback without ever downgrading a database."""
    if previous.version == target.version and previous.artifact_sha256 == target.artifact_sha256:
        raise RollbackError("rollback target must be a different immutable artifact")
    if not migration_compatible:
        raise RollbackError("database migration is incompatible; restore a verified backup under incident approval")
    if target.migration_revision != previous.migration_revision:
        raise RollbackError("automatic database downgrade is prohibited")


def complete_incident(record: IncidentRecord) -> bool:
    return record.state is IncidentState.CLOSED and bool(record.actions)


def validate_operational_objectives(objectives: list[OperationalObjective]) -> None:
    if not objectives:
        raise ValueError("at least one service objective is required")
    if len({o.service for o in objectives}) != len(objectives):
        raise ValueError("duplicate service objective")
