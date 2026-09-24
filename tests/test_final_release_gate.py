from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "final_release_gate.py"


def _write_case(tmp_path: Path, *, commit: str = "a" * 40, ci_hash: str = "b" * 64, manifest_hash: str = "b" * 64):
    evidence = tmp_path / "evidence.json"
    release = tmp_path / "release.json"
    ci = tmp_path / "ci.json"
    evidence.write_text(json.dumps({"closed": 10, "pending_external": 0}), encoding="utf-8")
    release.write_text(json.dumps({
        "format": "hussam-release-manifest/v1",
        "source_commit": commit,
        "source_manifest_hash": manifest_hash,
        "file_count": 1,
        "files": [{"path": "README.md", "sha256": "c" * 64, "bytes": 1}],
    }), encoding="utf-8")
    ci.write_text(json.dumps({
        "status": "passed",
        "commit_sha": commit,
        "run_id": "123",
        "source_manifest_hash": ci_hash,
    }), encoding="utf-8")
    return evidence, release, ci


def _run(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_final_gate_requires_trusted_ci(tmp_path: Path):
    evidence, release, _ci = _write_case(tmp_path)
    result = _run(
        "--evidence-manifest", str(evidence),
        "--release-manifest", str(release),
        "--expected-commit", "a" * 40,
    )
    assert result.returncode != 0
    assert "required" in result.stderr.lower()


def test_final_gate_binds_manifest_to_commit_and_ci_hash(tmp_path: Path):
    evidence, release, ci = _write_case(tmp_path, ci_hash="d" * 64)
    result = _run(
        "--evidence-manifest", str(evidence),
        "--release-manifest", str(release),
        "--expected-commit", "a" * 40,
        "--ci-evidence", str(ci),
    )
    assert result.returncode != 0
    assert "source manifest hash" in result.stderr.lower()


def test_final_gate_accepts_matching_provenance_inputs(tmp_path: Path):
    evidence, release, ci = _write_case(tmp_path)
    result = _run(
        "--evidence-manifest", str(evidence),
        "--release-manifest", str(release),
        "--expected-commit", "a" * 40,
        "--ci-evidence", str(ci),
    )
    assert result.returncode == 0
    assert "FINAL_RELEASE_GATE=PASS" in result.stdout
