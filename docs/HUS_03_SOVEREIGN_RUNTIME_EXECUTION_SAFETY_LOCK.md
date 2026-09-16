# HUS-03 — Sovereign Runtime & Execution Safety Lock

## Status
ENGINEERING LOCKED

HUS-03 establishes the runtime boundary after HUS-01 language validation and HUS-02 typed IR/planning.

## Runtime chain
`HUS Source -> AST -> Semantic Validation -> Typed IR -> Execution Plan -> Runtime Authorization -> Approval -> Idempotency -> Allow-listed Domain Handler -> Result -> Audit`

## Hard boundaries
- HUS source is never executed.
- No Python, shell, SQL, arbitrary HTTP, imports, filesystem access, or dynamic code evaluation.
- Tenant scope is checked when resolving the active compilation.
- Only steps present in the active compiled plan may execute.
- Capability names must remain registered in the Sovereign registry.
- Mutations require an approval reference, explicit approval, and an idempotency key.
- A registered capability without an installed runtime handler fails closed; it is never reported as executed.
- Repeated idempotency keys replay the existing execution record instead of creating a second execution.
- Runtime results carry plan/step/actor provenance.
- Domain services remain the authority for business invariants, accounting, inventory, payments, and fulfillment.
- AI may propose a HUS plan/action but cannot grant itself approval or bypass runtime authorization.

## Compatibility
`execute_compiled_action` remains as a compatibility facade. It now resolves a unique compiled-plan step and delegates to `SovereignRuntime`; it is not a second execution engine.

## Deliberate scope
HUS-03 does not invent fake handlers for domain mutations. The current implementation provides only the existing safe marketplace read adapter. Real mutations are enabled only when their corresponding domain-service handler is explicitly registered and tested.
