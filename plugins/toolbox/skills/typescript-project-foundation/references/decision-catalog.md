# Day-zero decision catalog

Use this catalog to prevent expensive cross-cutting retrofits. Decide an item now when its expected later cost is material: likelihood of survival multiplied by change cost. A `disposable-spike` may defer delivery automation, but it does not get to create ambiguous data or security contracts that could be mistaken for production-ready work.

## Runtime and repository shape

| Decision | Default | Change cost / rule |
|---|---|---|
| Runtime target | Match actual deployment, not local Node convenience | Re-platform. Confirm runtime limits and unavailable APIs. |
| Module model | Strict ESM | Code migration. Do not create dual ESM/CJS unless publishing requires it. |
| Single package vs workspace | Single package until a real boundary exists | Code migration. Use a workspace for 2+ deployables, a published package, or mixed runtime targets. |
| Task runner | None for a single simple package | Config change. Add Turborepo only for a real cross-package task graph/cache benefit. |
| Runtime configuration | Versioned config is source of truth; secrets remain external | Re-platform/security. Separate local, preview, staging, and production explicitly. |

## Product and identity model

Decide before schema or route design:

- Is the product single-tenant, shared-schema multi-tenant, or database-per-tenant?
- Can one user belong to multiple tenants? Can one identity map to multiple accounts?
- Which identifier is internal user identity, and which values are provider-owned opaque subjects?
- Where is authorization enforced for HTTP handlers, jobs, scripts, and tests?

For shared-schema multi-tenancy, every tenant-owned row needs an explicit tenant key and every access path needs a mechanically enforced scope. HTTP middleware alone is not an authorization boundary.

## Data semantics

| Topic | Required decision |
|---|---|
| Identifier | Classify every ID as UUIDv7 entity, internal integer, composite relationship, external principal, natural key, digest, or capability. |
| UUID storage | Choose text or binary representation once per database profile. Do not mix casually. |
| Time | Store an explicit timestamp independent of UUIDv7. Define UTC storage, business timezone, precision, and event-time vs processing-time. |
| Money | Use integer minor units or an exact decimal contract. Never binary floating point. Define currency alongside amount. |
| Deletion | Choose physical deletion, soft deletion, archival, and retention/erasure rules. Avoid adding `deleted_at` without query enforcement. |
| Migration | Use versioned migrations and expand/contract changes when old and new code can overlap. Define rollback/recovery before production. |
| Idempotency | Define retry and duplicate-delivery semantics for mutations, webhooks, queues, and scheduled jobs. |
| Data location | Confirm jurisdiction/region requirements before selecting storage placement. |

## API and client contracts

- Error representation and safe disclosure
- Authentication transport: secure cookie, bearer token, service credential, or a deliberate combination
- Domain/cookie/CORS/CSRF topology
- Pagination: cursor by default for mutable ordered collections; offset only when its instability is acceptable
- Stable sort keys and tie-breakers
- API evolution and deprecation policy
- Request and idempotency identifiers
- External vs internal contracts
- i18n, accessibility, and public message ownership when a UI exists

## Delivery and operations

- Preview/staging/production topology
- Migration and deploy ordering
- Smoke checks, rollback target, and concurrency policy
- Log redaction and retention
- Observability sampling and cost bounds
- Backup/export/recovery requirements
- Ownership of dependency and security updates

## Decision record

Record each material choice with:

```text
Decision:
Chosen option:
Alternatives considered:
Evidence/source:
Later-change cost: trivial | config-change | code-migration | data-migration | api-break | re-platform
Enforcement mechanism:
Reconsideration trigger:
```

Do not create one ADR per obvious default. Keep the complete snapshot in the foundation document and use ADRs for contested, exceptional, or long-lived alternatives.

