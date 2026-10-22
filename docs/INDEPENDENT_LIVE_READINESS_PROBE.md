# Independent live readiness probe

This workflow provides a repeatable execution path that does not depend on Codespaces or Desktop Commander.

## What it does
- Runs on GitHub-hosted Actions runners on a daily schedule, or when manually dispatched from the Actions tab.
- Sends only bounded public HTTP `GET` requests to the Hussam backend health endpoint, Hussam portal, and YIB health endpoint.
- Records UTC observation times, HTTP status/reachability, and a strict allowlist of non-secret health fields.
- Uploads a JSON artifact retained for 30 days.

## What it deliberately does not do
- No login, chat/model generation, API key, secret, write request, database connection, backup, restore, deployment, environment change, billing action, or allowlist mutation.
- It does not infer that a model is live from an HTTP 200 alone. The model is considered evidenced only if the returned safe health fields explicitly report that state; even then, this probe does not issue a generation request.
- GitHub-hosted runner egress is not a stable authorized route to a protected Render PostgreSQL instance. This workflow cannot replace an independently authorized database backup/restore path.

## Interpreting results
- `reachable` means the HTTP endpoint returned a status in the 200–399 range; it is not a full product acceptance test.
- `HTTPError` means the server returned a non-success HTTP response; DNS, TLS, timeout, or connection failures are recorded by exception class.
- Missing fields remain missing and must be treated as unknown, not false or verified.
- Artifacts contain only endpoint names, URLs, status metadata, and allowlisted health fields. Never add response bodies, request headers, tokens, or environment values to the report.

## Activation
After review and merge, open GitHub Actions → **Independent live readiness probe** → **Run workflow** to trigger an immediate read-only run. The scheduled run is daily.
