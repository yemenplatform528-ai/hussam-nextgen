# YIB/WORLD — Independent Local Intelligence Kernel

## Contract
- Offline-first: no network calls, credentials, or paid provider required by this kernel.
- Truth labels are explicit: VERIFIED, OBSERVED, REPORTED, INFERRED, BLOCKED, UNKNOWN.
- No external side effects are performed by the kernel.
- Potentially high-risk requests are marked for a human approval gate.
- Deterministic rule routing is not a trained language model and must not be marketed as one.
- Memory is supplied through an injected local reader; persistence and access control remain the host application's responsibility.

## Current implementation
`app/ai/local_kernel.py` implements a dependency-free, deterministic rule kernel with status, resume, memory, and plan routes plus an offline regression self-test.

## Verification
Run:
`python -m app.ai.local_kernel`

The output reports the regression test results and confirms the kernel does not use the network. This test does not verify a deployed service, persistent database integration, or LLM-grade generation.

## Next integration boundary
The web server may import this kernel as a local fallback. Keep it separate from any optional model adapter. The default must remain offline and no-cost; never silently invoke a billable endpoint. A future on-device model runtime can implement the same interface if the deployment host has enough CPU/RAM/storage.
