"""Fail-closed audit for the Yemen payment-provider evidence register."""
from pathlib import Path

MATRIX = Path(__file__).resolve().parents[1] / "docs" / "YEMEN_PAYMENT_PROVIDER_CERTIFICATION_MATRIX.md"
REQUIRED = [
    "Al-Kuraimi / Kuraimi Jawal",
    "Al-Kuraimi / Haseb",
    "Al-Qutaibi / Qutaibi Mobile",
    "Al-Qutaibi / Shalan (Shln)",
    "Yemen Payments & Clearing Company (YPCC)",
    "Al-Najm",
]
FORBIDDEN_CERTIFICATION_WORDING = [
    "certified integration",
    "production integration",
    "live integration",
]
ALLOWED_STATES = {
    "discovered",
    "public_capability_evidence",
    "contract_required",
    "api_pending",
    "testing",
    "certified",
    "production",
}

def main() -> int:
    text = MATRIX.read_text(encoding="utf-8")
    missing = [item for item in REQUIRED if item not in text]
    if missing:
        print("FAIL: missing providers:", ", ".join(missing))
        return 1
    # The register may contain the words in definitions, but provider rows must
    # carry an explicit, machine-checkable integration state and may not claim
    # certification merely from public capability evidence.
    rows = [line for line in text.splitlines() if line.startswith("|") and "Provider / product" not in line and "---" not in line]
    for line in rows:
        if any(word in line.lower() for word in FORBIDDEN_CERTIFICATION_WORDING):
            print("FAIL: provider row contains unverified certification wording:", line)
            return 1
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 5 and cells[4].strip("`") not in ALLOWED_STATES:
            print("FAIL: provider row has invalid integration status:", line)
            return 1
        if len(cells) >= 5 and cells[4].strip("`") in {"certified", "production"}:
            print("FAIL: matrix must not self-certify a provider:", line)
            return 1
    required_sections = ["## Acceptance states", "## Regulatory gate", "## Integration rule"]
    missing_sections = [s for s in required_sections if s not in text]
    if missing_sections:
        print("FAIL: missing sections:", ", ".join(missing_sections))
        return 1
    print("PASS: Yemen payment-provider evidence matrix is present and fail-closed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
