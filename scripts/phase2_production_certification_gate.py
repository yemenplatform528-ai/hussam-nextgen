#!/usr/bin/env python3
"""Fail-closed Phase 2 production certification gate.

This validator distinguishes engineering readiness from real external
certification. It never accepts configuration, mocks, screenshots, public
provider pages, or developer-declared PASS as production evidence.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

GATES = {
 "identity_oidc": ("G01", "Real IdP browser login/callback/session/tenant authorization/logout evidence"),
 "postgresql": ("G02", "Real PostgreSQL migration/backup/restore evidence with measured recovery"),
 "payments": ("G03", "Real payment-provider transaction/webhook/idempotency/reconciliation evidence"),
 "accounting": ("G04", "Real order/payment/COD/journal/settlement/reversal/reconciliation evidence"),
 "logistics": ("G05", "Real carrier shipment/tracking/delivery/COD collection evidence"),
 "browser_mobile_e2e": ("G06", "Real production-like browser/mobile journeys tied to release"),
 "security": ("G07", "Real deployment security/rate-limit/dependency/image/security-assessment evidence"),
 "backup_dr_observability": ("G08", "Real backup/restore/RPO/RTO/metrics/alert/recovery evidence"),
 "operations": ("G09", "Real owner/on-call/rollback/incident/recovery drill evidence"),
 "legal_compliance": ("G10", "Approved applicable legal/compliance wording and ownership evidence"),
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")

def valid_artifact(root: Path, item: dict) -> tuple[bool,str]:
    artifact=item.get("artifact") or {}
    p=artifact.get("path")
    h=str(artifact.get("sha256",""))
    if not p or not HEX64.fullmatch(h):
        return False,"artifact path + SHA-256 required"
    path=(root/p).resolve()
    if root not in path.parents or not path.is_file():
        return False,"artifact missing or escapes evidence root"
    import hashlib
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != h:
        return False,"artifact SHA-256 mismatch"
    return True,"ok"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--evidence-dir",type=Path,required=True)
    ap.add_argument("--release-sha",required=True)
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    root=args.evidence_dir.resolve()
    rows=[]
    for key,(code,requirement) in GATES.items():
        p=root/f"{key}.json"
        state="PENDING_EXTERNAL"; reason="evidence envelope missing"
        if p.is_file():
            try:
                data=json.loads(p.read_text(encoding="utf-8"))
                required=("gate","release_sha","environment","source","performed_at","result","reviewed_by","artifact","checks")
                missing=[x for x in required if not data.get(x)]
                if missing: reason="missing: "+", ".join(missing)
                elif data.get("gate") != key: reason="gate mismatch"
                elif data.get("release_sha") != args.release_sha: reason="release SHA mismatch"
                elif data.get("result") != "PASS": reason="result is not PASS"
                elif not isinstance(data.get("checks"),list) or not data["checks"]: reason="checks missing"
                else:
                    ok,detail=valid_artifact(root,data)
                    if ok: state="CLOSED"; reason=None
                    else: reason=detail
            except Exception as exc: reason=f"invalid envelope: {type(exc).__name__}"
        rows.append({"code":code,"gate":key,"state":state,"requirement":requirement,"reason":reason})
    payload={
      "format":"hussam-phase2-production-certification/v1",
      "release_sha":args.release_sha,
      "closed":sum(x["state"]=="CLOSED" for x in rows),
      "pending_external":sum(x["state"]!="CLOSED" for x in rows),
      "gates":rows,
      "fail_closed":True
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2))
    return 0 if payload["closed"]==10 else 1
if __name__=="__main__":
 raise SystemExit(main())
