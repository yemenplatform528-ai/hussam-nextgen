# HUS-01 Release Evidence

Artifact: HUS-01 Language Foundation

## Scope
- Formal HUS v1.0 lexical layer
- Recursive-descent parser
- Immutable source AST with spans
- Closed sovereign type vocabulary foundation
- Semantic validation against the existing capability registry
- Deterministic canonical AST and hash
- Pure AST-to-legacy-spec lowering
- Backward compatibility for existing `compile_spec(dict)`
- No database migration and no runtime side effects added

## Verification
- Focused HUS language + HUS + AI regression tests: **35 passed**
- Python compileall (`app`, `alembic`, `tests`): **passed**
- Baseline audit: **0 failures / 0 warnings**
- Full pytest: **not reported as passed**; the existing full-suite run timed out after reaching approximately 56% of the suite. This is preserved as an evidence limitation rather than masked.

## Security boundary
HUS source remains declarative data. The language front-end has no imports, shell, SQL, filesystem, network, provider calls, arbitrary code execution, or direct database authority.
