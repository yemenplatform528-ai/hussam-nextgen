# Hussam NextGen — Production Gates

Engineering tests are necessary but do not alone constitute production readiness.

## External gates
1. Production identity/OIDC and secure secret management.
2. Production PostgreSQL with migrations and restore drill.
3. Certified payment providers, signed webhooks and reconciliation.
4. Real accounting integration/reconciliation.
5. Real logistics/carrier contracts and delivery operations.
6. Browser/mobile end-to-end journeys.
7. Security assessment, dependency/image scanning and rate limiting.
8. Backups, disaster recovery, observability and alerting.
9. Operational runbooks, support process and rollback procedure.
10. Legal/compliance and marketplace policy review.

Until every applicable gate is evidenced, the system remains a release candidate,
not a production-ready launch.

## Engineering evidence added in the unified platform
- `/ready` performs a real `SELECT 1` database reachability check by default in staging/production; `deep=false` remains available for configuration-only probes.
- `/metrics` exposes a dependency-light Prometheus-compatible request counter and duration total.
- HTTP request IDs are propagated into structured JSON logs without logging credentials or request bodies.
- The API has a process-local last-resort rate limiter with `X-RateLimit-*` and `Retry-After` headers; production must still enforce a shared/distributed edge limiter because process-local state is not sufficient across replicas.
- `scripts/artifact_manifest.py` creates deterministic SHA-256 file manifests for release provenance.
- CI performs Python dependency auditing and builds/scans the release container for HIGH/CRITICAL vulnerabilities (unfixed findings are ignored by policy).
- `scripts/postgres_backup_restore_drill.sh` provides the controlled PostgreSQL backup/restore drill. Its successful execution is still external production evidence and is not fabricated by repository tests.
