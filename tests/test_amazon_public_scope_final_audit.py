import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_amazon_public_scope_manifest_is_frozen_and_complete():
    manifest = json.loads((ROOT / "docs/AMAZON_PUBLIC_SCOPE_MANIFEST.json").read_text())
    assert manifest["status"] == "scope-finalized"
    assert len(manifest["families"]) == 30
    assert manifest["represented"] == 30
    assert manifest["private-amazon-equivalence_claimed"] is False
    assert manifest["production-certification"] == "pending-external"
    assert manifest["yemenization"] == "next-phase"
    assert len(manifest["families"]) == 30
    assert len(set(manifest["families"])) == 30


def test_amazon_public_scope_final_audit_has_required_boundaries():
    text = (ROOT / "docs/AMAZON_PUBLIC_SCOPE_FINAL_AUDIT.md").read_text()
    for phrase in (
        "30/30 represented",
        "private Amazon/internal equivalence: **not claimed**",
        "Production launch remains gated",
        "Yemenization remains the next product phase",
    ):
        assert phrase in text
