# Yemen Intelligence — Multi-Capability Verification Matrix

Status: order-9
Date: 2026-10-01
Mission: Yemen is the purpose; AI is a capability layer.

## Verification rule
CAPABILITY → HEALTH → EVIDENCE → FAILURE MODE → SUBSTITUTE → VERIFY → CONTINUE

| Capability | Health | Evidence | Failure mode | Substitute | Verify | Continue |
|---|---|---|---|---|---|---|
| Tiniest Cloud | verified | External bridge v3, durable state, checkpoints, heartbeat, recovery snapshot | bridge unavailable | GitHub recovery pointer + alternate execution surface | probe bridge and read recovery state | resume from last checkpoint |
| GitHub | verified | recovery pointer branch + main continuity workflow + routing registry | repository/workflow unavailable | independent durable artifact copy | fetch recovery artifact and integrity-check it | resume from last confirmed state |
| Basic Memory | verified | durable capability/operating notes | memory surface unavailable | exported markdown knowledge bundle | verify exported bundle/checksum | restore knowledge context |
| Neon | available | connected database capability recorded in routing registry | database unavailable | portable Postgres backup / alternate database | restore into substitute and verify schema/data | continue database-dependent work |
| ChatGPT | available | current intelligence capability in this session | model/provider unavailable | another model/provider or local/open model | run a bounded verification task and compare required outputs | continue from durable state |
| Open/local models | route-defined | substitution route recorded in registry | selected model unavailable | another model surface | bounded capability test | continue without rebuilding the system |

## Substitution protocol
1. Preserve durable state.
2. Select an available replacement.
3. Verify the replacement for the required capability.
4. Continue from the last checkpoint.
5. Record the substitution.

## Safety
- No secrets in this matrix.
- No destructive automatic restoration.
- Irreversible, legal, financial, identity-sensitive, or destructive actions require the appropriate approval.
- Verification status means evidence available at the time of recording; it is not a claim that every external service is continuously healthy.
