#!/usr/bin/env python3
"""Deterministic, secret-free engineering incident/rollback drill harness."""
from __future__ import annotations
import argparse, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.operations import (
    IncidentAction, IncidentRecord, IncidentState, OperationalObjective,
    ReleaseArtifact, complete_incident, validate_operational_objectives, validate_rollback,
)

OBJECTIVES = [
    OperationalObjective("api", rto_minutes=30, rpo_minutes=15),
    OperationalObjective("worker", rto_minutes=30, rpo_minutes=15),
]


def run() -> dict:
    validate_operational_objectives(OBJECTIVES)
    previous = ReleaseArtifact("release-previous", "1" * 64, "0004_carrier_lifecycle")
    target = ReleaseArtifact("release-rollback", "2" * 64, "0004_carrier_lifecycle")
    validate_rollback(previous, target, migration_compatible=True)
    incident = IncidentRecord("DRILL-OPS-001", "SEV-2", OBJECTIVES[0])
    steps = [
        (IncidentState.TRIAGED, "triage", "operator-placeholder", "impact scoped"),
        (IncidentState.CONTAINED, "contain", "operator-placeholder", "rollout stopped"),
        (IncidentState.RECOVERED, "rollback", "operator-placeholder", "immutable application artifact restored"),
        (IncidentState.VALIDATED, "validate", "operator-placeholder", "health readiness and smoke checks pass"),
        (IncidentState.CLOSED, "close", "reviewer-placeholder", "incident review recorded"),
    ]
    for state, action, actor, outcome in steps:
        incident.transition(state)
        incident.record(IncidentAction(action, actor, outcome))
    assert complete_incident(incident)
    return {
        "format": "hussam-operations-incident-drill/v1",
        "result": "PASS",
        "environment": "engineering-drill",
        "incident_id": incident.incident_id,
        "severity": incident.severity,
        "final_state": incident.state.value,
        "objectives": [o.__dict__ for o in OBJECTIVES],
        "rollback": {
            "previous_version": previous.version,
            "target_version": target.version,
            "target_artifact_sha256": target.artifact_sha256,
            "database_downgrade": False,
            "migration_revision": target.migration_revision,
        },
        "audit": list(incident.audit()),
        "secrets_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = run()
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"INCIDENT_DRILL_OK sha256={hashlib.sha256(text.encode()).hexdigest()}")
    else:
        print(text, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
