# Data and API foundation

## API boundaries

Validate untrusted input once at the boundary and carry typed values inward. Reuse Zod schemas for runtime validation and inferred TypeScript types; do not define a second handwritten interface for the same contract.

Use RFC 9457 Problem Details for HTTP errors:

```json
{
  "type": "https://example.invalid/problems/validation",
  "title": "Validation failed",
  "status": 400,
  "detail": "One or more fields are invalid.",
  "instance": "/requests/request-id"
}
```

- Return `application/problem+json`.
- Keep `type` stable and machine-readable.
- Do not expose stack traces, SQL, provider errors, secrets, or internal topology.
- Add extension members only for stable client needs, such as structured validation issues or a request ID.
- Map domain errors centrally; do not construct inconsistent response shapes in each route.

Reference: https://www.rfc-editor.org/rfc/rfc9457.html

## OpenAPI decision

Generate OpenAPI when the API has external or multiple clients, generated SDKs, public/internal documentation, or contract-testing needs. Prefer generation from the runtime schema/route definition. Verify which OpenAPI version the chosen generator actually supports; do not claim the latest specification version if the tool emits an older dialect.

For a small private API with one co-located TypeScript client, Hono RPC or shared Zod contracts may be sufficient. Record the trigger for adding OpenAPI later.

## Identifier classification

Classify every primary identifier:

| Meaning | Default |
|---|---|
| Persistent domain entity | UUIDv7 |
| Relationship/join | Meaningful composite primary key |
| Internal SQLite row/join key | `INTEGER PRIMARY KEY` |
| External identity principal | Provider-owned opaque string |
| Content identity | SHA-256 or appropriate digest |
| Capability/session/reset token | CSPRNG random token; hash at rest |
| Local human-facing sequence | Separate explicit sequence |

UUIDv7 is time ordered but is not business time, audit time, causal order, or a gap-free sequence. Store `created_at` separately and sort by `created_at, id`. UUIDv7 can reveal approximate generation time; do not use it where that disclosure is unacceptable.

Centralize generators and schemas:

```ts
newEntityId()        // UUIDv7
newCapabilityToken() // CSPRNG, separate contract
```

Use branded identifiers where domain mix-ups are plausible. Fixtures must use contract-valid values rather than placeholders such as `entity-1`.

Reference: https://www.rfc-editor.org/rfc/rfc9562.html

## SQLite and D1

- Only the exact declaration `INTEGER PRIMARY KEY` aliases SQLite ROWID.
- `INT PRIMARY KEY` and `BIGINT PRIMARY KEY` do not have the same behavior.
- Do not add `AUTOINCREMENT` unless committed IDs must never be reused. It does not create gap-free sequences and adds overhead.
- Keep internal signed-64-bit integers inside the database where possible. JavaScript `number` cannot safely represent every int64; expose a UUID string or an explicit string/BigInt contract.
- Generate UUIDv7 in a shared application module, not a complex SQLite trigger/default.
- Add indexes for foreign keys, tenant scopes, filters, and ordering demonstrated by query plans.
- Test migrations against a realistic database copy or disposable environment before remote apply.

References:

- https://sqlite.org/rowidtable.html
- https://sqlite.org/autoinc.html
- https://developers.cloudflare.com/d1/best-practices/use-indexes/

## Authorization-aware query design

Do not export an unrestricted raw database client to route, job, or feature code. Provide a narrow repository/session boundary that requires actor and tenant scope. Enforce the same boundary for HTTP handlers, queues, scheduled jobs, scripts, and tests.

- PostgreSQL may add row-level security as defense in depth.
- SQLite/D1 has no equivalent application-independent RLS; scoped query APIs and negative cross-tenant tests are mandatory for shared-schema multi-tenancy.
- Avoid optional tenant parameters and hand-written `WHERE tenant_id = ?` scattered across features.
- Test object-level and property-level authorization, not only authentication.

## Time, money, pagination, and retries

- Store UTC timestamps using one documented physical representation and precision. Convert only at presentation/business-rule boundaries.
- Use integer minor units or an exact decimal representation for money and always include currency.
- Prefer cursor pagination for mutable collections. The cursor must include a stable order key and unique tie-breaker.
- Define idempotency keys and duplicate delivery behavior before enabling queues, webhooks, retried mutations, or scheduled jobs.
- Use expand/contract migrations when two application versions may overlap. A migration being syntactically reversible does not prove data rollback safety.

