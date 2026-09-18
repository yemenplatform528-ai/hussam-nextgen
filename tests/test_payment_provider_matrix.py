from pathlib import Path
import runpy


def test_yemen_payment_provider_matrix_audit_passes():
    path = Path(__file__).resolve().parents[1] / "scripts" / "payment_provider_matrix_audit.py"
    result = runpy.run_path(str(path), run_name="__test__")
    assert result["MATRIX"].exists()
    assert result["REQUIRED"]
