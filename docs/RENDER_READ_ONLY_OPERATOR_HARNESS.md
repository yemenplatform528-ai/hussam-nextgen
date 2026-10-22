# Render Read-Only Operator Harness

This adds a repeatable, audited path to run a read-only Render REST API inventory from GitHub Actions, independent of Codespaces and Desktop Commander. It targets the known Yemen workspace `tea-db0p6749v7es73ceig1g`, filters resources through Render's `ownerId` query parameter and again before reporting, and uses Render's documented `GET /v1/owners` endpoint. Pagination caps are marked `PARTIAL`, never silently presented as complete. The auditor also probes only HTTPS `*.onrender.com` service URLs without storing response bodies and flags PostgreSQL expiry windows (warning at 21 days, urgent at 7 days, expired after the expiry time).

## Owner setup (do not paste secrets into chat)

1. In Render Dashboard, open Account Settings and create a Render API key.
2. Render documents that the key can access all workspaces associated with the account. Treat it as a high-impact secret.
3. In GitHub repository Settings → Environments, create `render-readonly` and configure a required reviewer before adding any credential. Add `RENDER_API_KEY` only as an environment secret in that environment, never in a file, repository secret, issue, or chat. Do not configure the key if required-reviewer protection is unavailable.
4. Review and merge the workflow only after reviewing the script and its permissions.
5. Create or open a regular GitHub issue, then comment exactly `/render-audit` on a regular issue. The workflow accepts only comments from the repository owner account `yemenplatform528-ai`, ignores comments on pull requests, and references the protected `render-readonly` environment. Configure required-reviewer protection before adding the API key.
6. Retrieve the sanitized artifact from the resulting Actions run. It contains only the selected Yemen workspace, resource IDs/names, service URLs, plans/status/region and database expiry, plus a SHA-256 checksum.
7. Revoke the API key when no longer needed.

## What this unlocks

- Repeatable API-backed inventory through a runner even when Codespaces/Desktop Commander is offline.
- Evidence artifacts that can be fetched and analyzed after each run.
- A foundation to add more read-only Render REST API checks after validating the current workflow.

## Deliberate limits

- The job sends GET requests only. It does not deploy, restart, update settings, create/delete resources, read environment-variable values, run SQL, or call model providers.
- The Render API key is account-wide. Filtering limits the report, not the key's underlying permissions. Do not run unreviewed code with this key.
- A public repository means workflow logs and artifacts may be visible to repository visitors. The report contains Yemen workspace resource names and URLs. Before broadening the output or adding write actions, move the runner and artifacts to a private, tightly controlled repository or equivalent protected environment.
- This is not equivalent to arbitrary shell access. Render documents that SSH is unavailable for Free web services and static sites/datastores; current Hussam AI and YIB web services are on Free plans.
- No key is configured by this code, no workflow is triggered by these commits, and no Render resource is modified.

## Official references

- Render API: https://render.com/docs/api
- Workspace listing: https://api-docs.render.com/reference/list-owners
- Pagination: https://api-docs.render.com/reference/pagination
- API authentication: https://api-docs.render.com/reference/authentication
- Render MCP: https://render.com/docs/mcp-server
- Render CLI: https://render.com/docs/cli
- Render SSH restrictions: https://render.com/docs/ssh
