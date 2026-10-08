# YIB WORLD Operational Runbook

## Canonical rule
Use the YIB portal as the single operating surface. Do not create a new portal merely to solve a capability gap.

## Architecture
WORLD → YIB → Capability → Execution → Verification → Evidence → Recovery

## Truth states
VERIFIED / OBSERVED / REPORTED / INFERRED / BLOCKED / UNKNOWN

## Continuity
1. Read Current Truth.
2. Read checkpoint.
3. Preserve working state.
4. Substitute unavailable capability.
5. Execute only permitted low-risk actions.
6. Verify by fresh readback.
7. Record evidence.
8. Continue from checkpoint.

## Model policy
The model is a replaceable capability, not the authority. If a provider is unavailable, do not fabricate a response as if it came from that provider. Local deterministic operational commands may continue without an LLM.

## External integrations
Connection slots may exist without credentials. A slot is not a live integration. Credentials must be entered through the provider/platform connection UI and must never be placed in chat, source control, or evidence records.

## Human approval
For identity, money, secrets, irreversible writes, ownership changes, or other high-risk effects: present the action, scope, risk, and exact approval request to the human. After approval, execute through the real authorized channel, verify the result, and record evidence.

## Deployment
Canonical Tiniest portal: https://yemen-intelligence-bridge--hosam.tiniestcloud.app
Current live version: 62
Rollback: use the Tiniest version history; never delete the prior baseline until a later baseline is verified.

## Current external webhooks
A GitHub webhook exists on the canonical portal with GitHub signature verification configured. Its signing secret is intentionally not set from chat. The owner should set it in the Tiniest Webhooks panel before relying on authenticated GitHub deliveries.

## Current platform boundaries
Vercel projects exist as historical/alternative infrastructure, but the canonical portal is not dependent on Vercel. Render also exists as an alternative deployment surface, but no Render workspace was selected or modified in this run because the connector requires explicit workspace selection before any resource operation.

## Final acceptance
Do not declare the system complete because the UI looks complete. Completion requires fresh evidence for the intended capabilities, successful recovery, private-data checks, and explicit closure of every remaining BLOCKED/UNKNOWN gate.
