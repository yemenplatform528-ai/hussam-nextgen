# AI-01 — AI Foundation Lock

**Status: ENGINEERING LOCKED**

AI-01 establishes the governed Intelligence Plane above the Sovereign Core. It is not a chatbot release and does not authorize autonomous production mutation.

## Authority rule

`AI -> Context/Model -> Proposal -> Deterministic Policy -> Tool Contract -> Domain Service -> Persistence`

The model, prompt, memory store, vector store, provider SDK, or MCP adapter is **never** an authorization boundary. Tenant isolation, authorization, accounting invariants, lifecycle rules, idempotency and financial truth remain owned by Core/domain services.

## Locked contracts

- Provider registry stores only provider references/configuration; credentials are external references, never AI prompts or model output.
- Model routes are provider-neutral and selected by task class plus deterministic capability/privacy policy.
- Agents are identities with explicit scopes, tools, data classes, risk class and approval mode.
- Tools are typed contracts with action class, risk, data classification, approval and idempotency requirements.
- Action progression is `READ -> ANALYZE -> PROPOSE -> CONFIRM -> EXECUTE`.
- Memory is typed and scoped: conversation, user preference, business, operational, organizational, agent working.
- Memory is revocable/expirable where applicable and is context, not authority. Live domain facts outrank memory.
- External/tool output is untrusted data, never executable instruction.
- Trace and usage telemetry are first-class and tenant-scoped.
- No AI direct SQL, shell, ledger mutation, payout, payment capture, tenant reassignment, privilege elevation or destructive production command.

## Initial agent set

The foundation supports the later bounded agents: Customer Commerce Assistant, Seller Operations Assistant, Marketplace Operations Assistant, Finance Assistant (read-only), Risk/Trust Assistant and Platform Orchestrator. They are not activated as autonomous agents by AI-01.

## Control Center relationship

The future AI Control Center is part of the same platform. It configures already-designed capabilities through authenticated APIs and policy contracts. It does not bypass domain services or write production SQL directly.

**Configuration changes behavior within an existing capability; code creates new capability.**

## Verification gate

AI-01 is considered locked only when:

1. Fresh migration reaches `0010_ai_foundation_lock`.
2. `alembic check` is clean.
3. Downgrade to `0009`, re-upgrade to `0010`, and `alembic check` are clean.
4. Provider/route selection is tenant-scoped and capability-aware.
5. Agent/tool policy rejects ungranted tools and requires approval for mutation.
6. Memory isolation, revocation and context precedence are tested.
7. Trace/usage records are tenant-scoped and redaction is deterministic.
8. Existing Marketplace test suite remains green.

AI-01 does **not** claim production AI evidence. Provider credentials, live model quality, production latency/cost, external integrations and autonomous-agent behavior remain later release evidence.
