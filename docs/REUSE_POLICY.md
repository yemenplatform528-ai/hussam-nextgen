# Legacy Reuse Policy

Legacy projects are treated as source material, not as the architecture owner.

### Reuse freely when validated
- Security invariants and tenant-isolation lessons from platform-v2.
- Decimal monetary model and double-entry concepts.
- Membership model and production configuration gates.
- Core/engine/domain layering from prior NextGen prototypes.
- Idempotency, audit, workflow and registry primitives.
- Domain knowledge from prior grocery, dental-lab, mosque and clinic systems.
- HUS specification/compiler ideas after deterministic safety review.

### Do not import blindly
- Template remnants.
- Mock/demo initialization in production paths.
- Generic CRUD over financial records.
- Trusted tenant headers.
- Fake payment verification.
- Legacy routing/startup assumptions.
- UI-first architecture that bypasses domain contracts.
