import json, subprocess, sys
from pathlib import Path
import pytest
from app.core.operations import (
    IncidentRecord, IncidentState, InvalidIncidentTransition, OperationalObjective,
    ReleaseArtifact, RollbackError, validate_operational_objectives, validate_rollback,
)


def artifact(version, digest="a" * 64, rev="0004_carrier_lifecycle"):
    return ReleaseArtifact(version, digest, rev)


def test_incident_lifecycle_is_ordered_and_auditable():
    i = IncidentRecord("I-1", "SEV-2", OperationalObjective("api", 30, 15))
    for state in [IncidentState.TRIAGED, IncidentState.CONTAINED, IncidentState.RECOVERED, IncidentState.VALIDATED, IncidentState.CLOSED]:
        i.transition(state)
    assert i.state is IncidentState.CLOSED
    assert i.audit() == ()


def test_incident_rejects_skip():
    i = IncidentRecord("I-1", "SEV-1", OperationalObjective("api", 30, 15))
    with pytest.raises(InvalidIncidentTransition):
        i.transition(IncidentState.RECOVERED)


def test_rollback_requires_immutable_target_and_same_db_revision():
    validate_rollback(artifact("old"), artifact("new", "b" * 64), migration_compatible=True)
    with pytest.raises(RollbackError):
        validate_rollback(artifact("old"), artifact("new", "b" * 64, "0003_accounting_integrity"), migration_compatible=True)
    with pytest.raises(RollbackError):
        validate_rollback(artifact("old"), artifact("new", "b" * 64), migration_compatible=False)


def test_objectives_reject_duplicates():
    with pytest.raises(ValueError):
        validate_operational_objectives([OperationalObjective("api", 30, 15), OperationalObjective("api", 60, 30)])


def test_drill_script_is_secret_free_and_passes(tmp_path):
    out = tmp_path / "drill.json"
    result = subprocess.run([sys.executable, "scripts/incident_drill.py", "--output", str(out)], text=True, capture_output=True, check=True)
    payload = json.loads(out.read_text())
    assert payload["result"] == "PASS"
    assert payload["final_state"] == "closed"
    assert payload["secrets_included"] is False
    assert "INCIDENT_DRILL_OK" in result.stdout
    assert "secret" not in out.read_text().lower() or payload["secrets_included"] is False
