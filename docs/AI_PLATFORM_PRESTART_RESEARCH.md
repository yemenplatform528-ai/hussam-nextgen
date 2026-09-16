# Hussam NextGen — AI Platform Pre-Start Research & Architecture Readiness

## Executive decision

The Yemen Marketplace is engineering-locked and should remain the immutable product baseline. The next phase should **not** begin by adding a chatbot, a single agent, or model-provider-specific code. It should begin with an **AI Foundation Lock**: provider-neutral AI contracts, governed execution, memory boundaries, model routing, tool authorization, approvals, auditability, evaluation, and observability.

The AI layer must sit above the existing Sovereign Core and Marketplace contracts. AI can observe, reason, retrieve, propose, and request actions through governed contracts; it must never bypass identity, tenant/market isolation, accounting invariants, payment controls, fulfillment controls, or audit requirements.

## 1. What was reviewed

The current locked repository was reviewed at architecture, capability, marketplace, security, governance, and implementation levels. The canonical documents include:

- `docs/PLATFORM_BLUEPRINT.md`
- `docs/ARCHITECTURE.md`
- `docs/CAPABILITY_MAP.md`
- `docs/PLATFORM_CONSTITUTION.md`
- `docs/ENGINEERING_COMPLETE_G01_G10.md`
- `docs/AMAZON_PUBLIC_SCOPE_FINAL_AUDIT.md`
- `docs/Y2_FINAL_LOCK_REVIEW.md`
- all Yemen Marketplace locks: Market Isolation, Product Core, Commerce Transaction, Fulfillment & Settlement, and Lifecycle & Financial
- production gates/evidence documents
- current application, domain, engine, API, UI and test structure

The repository currently has no mature AI runtime that should be treated as the starting point. Existing AI/HUS references are architectural targets rather than a reason to graft an agent framework onto the marketplace.

## 2. Canonical dependency decision

The platform's existing architecture states:

`Clients → API → Identity/Tenant Context → Domain Services → Shared Engines → Sovereign Core → Persistence`

The AI layer should therefore become a **governed intelligence plane**, not a replacement application layer:

`Client → AI API → AI Gateway/Run Manager → Policy + Identity Context → Context/Memory → Model Router → Tool Gateway → Domain Contracts → Existing Engines/Core`

The AI layer may call domain contracts. It may not call persistence directly and may not bypass domain services.

## 3. AI platform boundaries

### AI owns

- AI requests/runs
- model/provider registry
- model routing and fallback policy
- prompt/instruction versions
- context assembly
- retrieval and grounding
- memory lifecycle and provenance
- agent identity and capability scopes
- tool registry and tool schemas
- action proposals
- approval workflows
- safety/validation gates
- AI audit/trace records
- evaluation datasets and results
- usage, latency and cost telemetry

### Existing platform owns

- identity and tenant membership
- authorization authority
- market isolation
- money and immutable financial records
- inventory truth
- orders and fulfillment truth
- payment and settlement truth
- logistics truth
- compliance/policy authority
- persistence and transactional integrity

### AI must never directly own

- ledger mutation
- payment execution
- payout execution
- seller privilege elevation
- tenant/market reassignment
- destructive production operations
- arbitrary SQL
- arbitrary shell execution

## 4. Memory architecture

Memory must be typed, scoped and revocable. Do not create one unrestricted `memory` table or one vector store containing everything.

Required classes:

1. Conversation memory — current/previous conversation context.
2. User preference memory — explicit user preferences and controllable personalization.
3. Business memory — durable business facts that have an authoritative source.
4. Operational memory — workflow state, observations and task history.
5. Organizational memory — policies, procedures, knowledge and approved institutional context.
6. Agent working memory — temporary plan/state for a single run.

Every durable memory item needs provenance, owner/scope, sensitivity, creation/update source, confidence/authority, retention policy and deletion/revocation semantics.

Memory is **context**, not authority. If memory conflicts with a live domain record, the authoritative domain record wins.

## 5. Agent architecture

Agents are identities with explicit contracts, not merely prompts.

Each agent definition should contain:

- stable agent ID/version
- role
- allowed tenants/markets/scopes
- permitted tools
- read/write capability class
- maximum autonomy level
- approval requirements
- model policy
- context policy
- memory policy
- budget/rate limits
- audit requirements
- kill/disable state

Initial agents should be few and domain-oriented. Recommended first family:

- Customer Commerce Assistant — read/search/propose only.
- Seller Operations Assistant — seller-scoped operational assistance.
- Marketplace Operations Assistant — controlled operational proposals.
- Finance Assistant — read/analysis only; no ledger mutation.
- Risk/Trust Assistant — signals, triage and recommendations.
- Platform Orchestrator — coordinates agents but inherits the strictest authorization of the underlying action.

Do not begin with autonomous swarms. Multi-agent delegation is a later capability after the identity, policy, tool and evaluation foundations are proven.

## 6. Tool/action model

Every AI tool must be a typed contract with:

- input schema
- output schema
- authorization scope
- data classification
- side-effect class
- idempotency requirements
- approval requirement
- timeout/retry policy
- audit event
- rate/cost limits
- rollback or compensation semantics where applicable

Actions should be classified:

`READ → ANALYZE → PROPOSE → CONFIRM → EXECUTE`

The default AI posture is read/analyze/propose. Sensitive execution requires deterministic policy checks and, where configured, explicit human approval.

This is essential because current agentic-security guidance identifies excessive functionality, permissions and autonomy as core sources of dangerous agent behavior. OWASP's 2026 agentic guidance also highlights goal hijacking, tool misuse, identity/privilege abuse, supply-chain issues and cascading failures.

## 7. Model gateway

The platform should not couple business code to a single LLM vendor.

Required contracts:

`AIProvider → Model → Capability → Policy → Router → Run`

The router should consider:

- task type
- required capabilities
- quality tier
- latency budget
- cost budget
- context window
- structured-output capability
- tool-calling capability
- availability
- data/privacy policy
- geographic/provider restrictions when applicable

Fallback must be policy-driven. A fallback model must not silently receive data or permissions that the primary model was not allowed to receive.

## 8. Context and retrieval

Context assembly must be deterministic before it reaches the model.

The context pipeline should distinguish:

- system policy
- agent policy
- user instruction
- trusted domain facts
- retrieved knowledge
- memory
- tool output
- external/untrusted content

External documents, web content and tool output are **data, not instructions**. They must never be promoted into the instruction hierarchy.

RAG/vector retrieval should be an implementation detail behind a retrieval contract. The first design should not assume one vector database or one embedding provider.

## 9. Safety and governance

NIST AI RMF and its Generative AI Profile identify trustworthy AI as a lifecycle concern and specifically cover risks including confabulation and data privacy. The framework's Govern/Map/Measure/Manage structure is a useful governance backbone.

For Hussam, this becomes:

`Govern → Map → Measure → Manage`

with hard runtime controls:

- authorization before tools
- policy validation before side effects
- output/schema validation
- source/provenance tracking
- sensitive-data controls
- approval gates
- budgets and rate limits
- immutable AI audit events
- run cancellation/kill switch
- evaluation gates before promotion

## 10. MCP and external tool ecosystems

MCP should not become the internal architecture. Hussam should first define its own internal Tool Contract and Tool Gateway. MCP can later be an adapter for external tool ecosystems.

This prevents external protocol semantics from becoming the authority for Hussam permissions. Current MCP revisions continue to evolve authorization/security details, reinforcing the need to keep Hussam's policy authority above protocol adapters.

## 11. Evaluation is a first-class subsystem

The AI platform cannot be declared production-ready by passing ordinary unit tests alone.

Required evaluation families:

- factuality/grounding
- task success
- tool selection correctness
- authorization correctness
- prompt-injection resistance
- data-isolation tests
- memory poisoning tests
- refusal/safety tests
- structured-output validity
- regression tests
- latency/cost budgets
- human approval compliance

Every model/prompt/agent version should have a reproducible evaluation record before promotion.

## 12. Observability

An AI run should be traceable end-to-end:

`request → policy decision → context → model call(s) → tool proposal → tool authorization → tool execution → output validation → response`

Telemetry should expose operational metrics without turning sensitive prompts or personal data into unrestricted logs. Redaction and retention policy are required.

## 13. Security threats that must shape the architecture

The 2026 OWASP agentic guidance and recent incident reporting make the following architectural requirements non-negotiable:

- prompt/goal hijacking protection
- tool misuse protection
- identity and privilege isolation
- memory poisoning resistance
- inter-agent communication controls
- cascading-failure limits
- rogue-agent detection/disablement
- human-agent trust controls
- supply-chain validation for tools/skills
- strict schema validation and sandboxing for code-capable operations

The practical rule is simple: **the model never becomes the security boundary.** Deterministic platform policy remains the security boundary.

## 14. First implementation sequence

The AI phase should be intentionally compressed into a small number of large engineering locks:

### AI-01 — AI Foundation Lock

- AI contracts
- provider/model registry
- AI run lifecycle
- model router
- context contract
- memory contract
- agent registry
- tool registry
- policy/approval boundary
- audit/trace contract
- cost/usage telemetry
- initial evaluation harness

### AI-02 — Governed Commerce Intelligence

- customer commerce assistant
- seller assistant
- marketplace search/recommendation intelligence
- grounded product/order context
- proposals without uncontrolled side effects
- controlled actions through existing marketplace contracts

### AI-03 — Multi-Agent Operations

- orchestrator
- specialized agents
- delegation contracts
- cross-agent authorization
- shared-but-scoped context
- failure isolation
- human escalation

### AI-04 — AI Product Lock

- full security/evaluation audit
- model/provider failover tests
- memory isolation tests
- tool authorization tests
- production observability
- AI-specific release gates
- final Marketplace + AI integration lock

HUS Compiler remains separate and later. It must not be smuggled into the first AI implementation.

## 15. What must not happen

- No single global unrestricted AI agent.
- No direct database access from agents.
- No model-specific business logic in Marketplace services.
- No AI-written ledger entries.
- No automatic payment/payout execution from model output.
- No hidden long-term memory.
- No memory writes merely because a prompt requested them.
- No uncontrolled external web/tool access.
- No MCP-first architecture.
- No autonomous multi-agent swarm before the foundation is locked.
- No production claim based only on local AI tests.

## 16. Readiness decision

**Architecture study: READY.**

**Implementation: NOT STARTED — intentionally.**

The correct next action is to begin **AI-01 — AI Foundation Lock**, not an AI feature demo. The Marketplace baseline should remain frozen as the dependency below it.

## Sources

1. NIST, *AI Risk Management Framework 1.0* and current AI RMF resources: https://www.nist.gov/itl/ai-risk-management-framework
2. NIST, *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile (NIST AI 600-1)*: https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
3. NIST AI Resource Center / AI RMF Playbook: https://airc.nist.gov/
4. OWASP GenAI Security Project, *Top 10 for Agentic Applications 2026*: https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
5. OWASP GenAI Security Project, *Top 10 for Agentic Applications*: https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/
6. OWASP, *LLM06:2025 Excessive Agency*: https://genai.owasp.org/llmrisk/llm062025-excessive-agency/
7. Model Context Protocol, July 2026 specification update: https://blog.modelcontextprotocol.io/posts/2026-07-28/
8. OpenAI Platform documentation, Agents SDK overview: https://platform.openai.com/docs/quickstart/make-your-first-api-request
