# Node profile

Use the current supported Node LTS for production services. Select the latest Current line only for an explicitly short-lived experiment or a verified feature requirement.

## Node API/service

- Strict ESM with `module`/`moduleResolution` chosen for direct Node execution or the selected bundler
- Hono with the current official Node adapter for HTTP routing when its Web Standards model fits the service
- Zod at HTTP, configuration, queue, file, and external-service boundaries
- Drizzle for a relational database
- Graceful shutdown, readiness, health, timeouts, and bounded concurrency
- Structured logging with request/correlation IDs and redaction
- Container/serverless deployment contract selected explicitly

Do not assume a Node process is stateless if it owns scheduled work, local files, WebSockets, background tasks, or in-memory coordination. Decide process lifetime and shutdown semantics before implementation.

## Database choices

- PostgreSQL: use native UUID support and current native UUIDv7 generation when the supported server version provides it; otherwise use the shared application generator.
- SQLite: follow the exact `INTEGER PRIMARY KEY`, UUID text/binary, and JavaScript int64 rules.
- Add connection pool, transaction, migration, and retry policies appropriate to the deployment topology.
- PostgreSQL row-level security can provide defense in depth, but does not replace scoped application repositories and negative tests.

## Deployment

- Pin the Node LTS patch/minor through the chosen runtime manager/container base policy.
- Run clean install, typecheck, tests, build, migration validation, and package/container security scanning in CI.
- Prefer OIDC and immutable artifacts. Record SBOM/provenance requirements when publishing artifacts or meeting external assurance needs.
