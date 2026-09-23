import subprocess
import sys
from pathlib import Path


def test_browser_ui_contract_desktop_and_mobile():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "scripts/browser_e2e.py"], cwd=root, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "BROWSER_E2E_OK desktop+mobile" in result.stdout
