# HUS-01 — Language Foundation Lock

Status: **ENGINEERING LOCKED**

HUS-01 establishes the first formal HUS source language without opening an execution runtime.

## Pipeline

`HUS source → lexer → parser → AST → semantic validation → canonical AST → legacy declarative spec → existing deterministic compiler`

This separation is intentional: AST preserves syntax; semantic validation assigns language meaning; lowering produces the existing contract input. This keeps HUS-01 additive and preserves the HUS-00 seed compiler.

## Language v1.0

```text
module <identifier> version <string-or-identifier> {
  organization code = <value> name = <value>;

  domain <identifier> {
    engine = <identifier>;
    capabilities = [<identifier>, ...];
    name = <value>;
    enabled = true|false;
  }

  workflow <identifier> {
    trigger = <value>;
    name = <value>;
    enabled = true|false;
    step <identifier> {
      action = <engine.capability>;
      approval;
    }
  }

  policy approval_required = [<identifier>, ...];
  policy allowed_roles = [<identifier>, ...];
  metadata <identifier> = <scalar>;
}
```

Comments: `// ...` and `# ...`.

## Closed type foundation

The language reserves the sovereign type vocabulary: String, Boolean, Integer, Decimal, Money, Currency, Date, DateTime, Duration, UUID, Identifier, Enum, List, Map, Optional, EntityRef, SecretRef, ApprovalRef and CapabilityRef. HUS-01 only materializes scalar source literals; richer domain typing is intentionally deferred to later compiler locks.

## Security invariants

- Source is data, never executable code.
- No imports, Python, SQL, shell, filesystem or arbitrary network operations.
- Capability names resolve only through the existing allow-list registry.
- Unknown engines/capabilities are compile-time failures.
- AST identity excludes source whitespace and source spans.
- Canonical AST is deterministic and hashable.
- Existing dict-based `compile_spec()` remains compatible.

## Non-goals

HUS-01 does not add runtime execution, arbitrary expressions, loops, recursion, external modules, MCP, provider calls, financial side effects, or a second authorization system.

## Acceptance

The lock is accepted when focused HUS tests, AI/HUS regression tests, compileall, baseline audit and deterministic canonicalization checks pass. A full-suite timeout unrelated to HUS must not be represented as a passing full-suite result.
