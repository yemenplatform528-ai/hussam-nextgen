# Render Read-Only Operator Harness

This adds a repeatable, audited path to run a read-only Render REST API inventory from GitHub Actions, independent of Codespaces and Desktop Commander. The job is deliberately restricted to the known Yemen workspace `tea-db0p6749v7es73ceig1g`; it filters resource results by owner/workspace before writing the artifact. It does not inventory other workspaces.

## Owner setup (do not paste secrets into chat)

1. In Render Dashboard, open Account Settings and create a Render API key.
2. Render documents that an API key can access all workspaces the account belongs to. Treat it as a high-impact secret.
3. In GitHub repository Settings → Environments, create `render-readonly`; add a required reviewer if available. Add `RENDER_API_KEY` as an environment secret in that environment, not in a file or issue.
4. Review and merge the workflow only after reviewing the script and its permissions.
5. Create or open a regular GitHub issue, then comment exactly `/render-audit` as the repository owner `yemenplatform528-ai`. The workflow ignores comments from other accounts and comments on pull requests.
6. Retrieve the sanitized artifact from the resulting Actions run. It includes only the configured Yemen workspace, with resource IDs/names, service URLs, plans/status/region and database expiry, plus a SHA-256 checksum.
7. Revoke the API key when no longer needed.

## What this unlocks

- Repeatable API-backed inventory through a runner even when Codespaces/Desktop Commander is offline.
- Evidence artifacts that can be fetched and analyzed after each run.
- A foundation to add more read-only Render REST API checks after validating the current workflow.

## Deliberate limits

- The job sends GET requests only. It does not deploy, restart, update settings, create/delete resources, read environment-variable values, run SQL, or call model providers.
- The Render API key is account-wide for all workspaces. Filtering reduces what the report publishes but does not reduce the key's underlying permissions. Do not use untrusted workflow code with this key.
- A public repository means workflow logs and artifacts can be visible to repository visitors. This report intentionally contains only the selected Yemen workspace. If the account later contains sensitive resource names or URLs, move the runner and artifacts to a private repository before widening the report.
- This is not equivalent to arbitrary shell access. Render documents that SSH is unavailable for Free web services and static sites/datastores; the current Hussam AI and YIB web services are on Free plans.
- No key is configured by this code, no workflow is triggered by these commits, and no Render resource is modified.

## Official references

- Render API: https://render.com/docs/api
- API authentication: https://api-docs.render.com/reference/authentication
- Render MCP: https://render.com/docs/mcp-server
- Render CLI: https://render.com/docs/cli
- Render SSH restrictions: https://render.com/docs/ssh
