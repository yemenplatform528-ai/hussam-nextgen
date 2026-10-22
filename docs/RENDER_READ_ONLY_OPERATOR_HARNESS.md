# Render Read-Only Operator Harness

This harness adds a repeatable, auditable way to inventory the Render account from a GitHub Actions runner when the owner configures a secret. It is deliberately read-only: it does not deploy, mutate environment variables, create/delete resources, query database rows, or run model requests.

## Why this exists

The connected Render tools can inspect resources and some operational data, but they do not expose arbitrary shell execution or direct arbitrary HTTP requests. Render's official REST API covers most dashboard capabilities and requires an API key. The harness provides a controlled execution path for safe account-wide inventory, independently of Codespaces and Desktop Commander.

## Owner setup required (secret is never pasted into chat)

1. In Render Dashboard, open Account Settings and create a Render API key.
2. Treat the key as a high-impact secret: Render documents that API keys can access all workspaces the account belongs to. Do not put it in repository files, issues, logs, or chat.
3. In GitHub repository Settings → Secrets and variables → Actions, add a repository secret named `RENDER_API_KEY`. Prefer a dedicated environment with required reviewer approval if the repository has that capability configured.
4. Merge this change only after reviewing the workflow and the script; the workflow is manual-only and the script sends GET requests only.
5. Open Actions → “Render Read-Only Account Audit” → Run workflow. It produces a sanitized JSON artifact with resource names, IDs, status/plan/region/expiry and a SHA-256 checksum. It never includes environment variable values, database URLs, API response bodies, or the token.
6. Retrieve the artifact and use it as the latest evidence ledger. Remove/revoke the API key when no longer needed.

## Current capabilities and limits

- The Render MCP integration currently exposes workspace/resource inventory, service/deploy/event/log/metric inspection, limited environment-variable updates, resource creation and read-only SQL subject to network access.
- The harness extends repeatable account-wide inventory through the official REST API, but is not a general shell and is not a write-control plane.
- Do not use an account-wide key with untrusted workflows. Anyone who can change trusted workflow code on the default branch could potentially misuse the secret. Keep repository write access restricted and inspect changes before merging.
- No secret is configured by this code, no workflow run is triggered, and no Render resource is modified by adding this harness.
- This does not claim the Render account is fully controllable. Additional capabilities must be enabled one at a time with explicit least-risk tests.

## Official references

- Render API: https://render.com/docs/api
- API authentication: https://api-docs.render.com/reference/authentication
- List services: https://api-docs.render.com/reference/list-services
