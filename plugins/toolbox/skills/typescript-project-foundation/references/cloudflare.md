# Cloudflare profile

Choose Workers when edge deployment, low operational overhead, global request handling, and Cloudflare-native bindings fit the product. Do not choose it silently when the product needs long CPU-bound work, unrestricted Node/native dependencies, arbitrary long-lived connections, unsupported protocols, or limits that would force an imminent re-platform.

Verify current limits and compatibility from official documentation at execution time. Do not copy numeric platform limits or a remembered `compatibility_date` into a new repository.

## Presets

### Worker API

- Hono + Zod
- Drizzle only when relational D1/PostgreSQL data exists
- Wrangler-generated binding types
- Vitest with the current official Cloudflare Workers pool/harness
- structured logs, request IDs, and a health/readiness contract

### Full-stack SPA + Worker

Prefer the current official Cloudflare Vite plugin and a single package when Vite/Workers Assets can build and deploy the SPA and API as one unit. Use a workspace when UI/API deploy independently, share a genuine package boundary, or require different runtime/type environments.

Add React + Vite. Add TanStack Router/Query and Tailwind only under their general decision rules.

## Configuration and bindings

- Treat `wrangler.jsonc` (or the current official equivalent) as source of truth; avoid dashboard drift.
- Set the compatibility date to the current date at creation only after verifying current runtime behavior and flags.
- Generate binding types with Wrangler and fail CI when generated types drift.
- Define local, preview/staging, and production explicitly.
- Put secrets in Cloudflare secret storage, never plaintext `vars` or committed `.dev.vars`.
- Use separate resources or clearly isolated identifiers for non-production environments.

## D1

- Apply the SQLite identifier and integer rules from the data reference.
- Generate UUIDv7 application-side.
- Add versioned migrations from day zero and test them locally/runtime-realistically.
- Add indexes for tenant filters, foreign keys, lookup fields, and cursor ordering; inspect query plans for critical paths.
- Define migration/deploy ordering and expand/contract compatibility.
- Avoid binding JavaScript `BigInt` unless current D1 documentation and tests prove support; preserve int64 boundaries explicitly.

## Queues and Durable Objects

- Queue delivery is retryable and may be duplicated. Require idempotency, retry classification, bounded attempts, and dead-letter/recovery behavior before enabling it.
- Use Durable Objects only for state that needs a single coordination point, strongly ordered mutation, alarms, or connection ownership. Do not add them for generic CRUD.
- For D1 + Queues + Vectorize or other multi-service consistency, use the dedicated data-pipeline skill.

## Observability and delivery

- Emit structured JSON objects with service, environment, severity, request/correlation ID, operation, outcome, and sanitized error information.
- Enable Workers Logs/traces deliberately with environment-specific sampling and retention/cost awareness.
- Never log authorization headers, cookies, secrets, or raw personal/domain-sensitive payloads.
- Run runtime-realistic tests and `wrangler deploy --dry-run` in CI.
- Keep deployment, remote D1 changes, and secret writes behind explicit confirmation.

Primary sources:

- https://developers.cloudflare.com/workers/best-practices/workers-best-practices/
- https://developers.cloudflare.com/workers/get-started/guide/
- https://developers.cloudflare.com/workers/testing/vitest-integration/
- https://developers.cloudflare.com/workers/observability/logs/workers-logs/
- https://developers.cloudflare.com/d1/
- https://hono.dev/docs/getting-started/cloudflare-workers
- https://orm.drizzle.team/docs/sqlite/connect-cloudflare-d1
