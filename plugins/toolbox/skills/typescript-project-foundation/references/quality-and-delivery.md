# Quality and delivery foundation

## Tool ownership

Use one owner per concern:

- Type correctness: `tsc`
- Lint: oxlint by default
- Format: oxfmt by default
- Dead exports/files/dependencies: Knip
- Tests and coverage: Vitest plus runtime-specific harness
- Git hooks: Lefthook

Switch the lint/format pair to Biome when its integrated coverage better fits the repository. Do not keep Oxc, Biome, ESLint, and Prettier as overlapping authorities. Where a specialized plugin is still necessary, document its non-overlapping responsibility.

## TypeScript baseline

- `strict: true`
- Explicit runtime/global `types`
- `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes` unless a verified ecosystem conflict prevents them
- No broad `skipLibCheck`, `any`, or unchecked assertions as compatibility escape hatches
- Separate browser, Worker, Node, and test globals when runtime targets differ
- Project references only when package build/type boundaries benefit from them

## Test strategy

Design tests around behavior and boundaries:

- Unit tests for pure domain behavior and parsing
- Integration tests for database repositories, migrations, and external adapters
- Runtime-realistic tests for Workers/workerd behavior
- Contract tests for API schema/error behavior when clients are independent
- Negative authorization tests for cross-principal and cross-tenant access
- Build/deploy dry-run checks for runtime compatibility

Coverage is a diagnostic, not the goal. Require meaningful assertions on error, retry, rollback, and boundary behavior rather than maximizing line percentage.

## Hook split

Keep local feedback fast:

- Pre-commit: staged format/lint, secret scan, workflow SHA/Pinact consistency, frozen-lockfile policy
- Pre-push: typecheck, full lint, Knip, relevant tests, build
- CI: clean install, all checks, coverage/integration tests, history secret scan, dependency audit, Pinact min-age verification, runtime/deploy dry-run

Do not put network-heavy downloads or remote mutations in pre-commit.

## CI/CD

- Pin every external Action to a full SHA.
- Use concurrency groups that prevent conflicting deploys without cancelling a deployment midway.
- Build and test before deployment; apply migrations with an explicit compatibility strategy.
- Use preview/staging before production when the product has an operable UI/API.
- Smoke test the deployed endpoint and retain a precise rollback target.
- Report deploy, smoke, and rollback outcomes even when an earlier step fails.
- Keep remote deploy/database/secret operations outside the skill's blanket local-change approval.

For a single Cloudflare Worker release pipeline, use the dedicated Cloudflare Worker CD skill for deploy/smoke/rollback details. For a multi-service data pipeline, use the dedicated Cloudflare data-pipeline skill.

## Architecture checks

Convert foundation rules into project-specific checks, for example:

- raw DB client imports allowed only inside the database/repository package
- direct UUID generation forbidden outside the ID module
- all tenant-owned repositories require tenant scope
- all API ID fields use shared schemas
- no mutable GitHub Action reference
- migrations and generated schema are synchronized
- config bindings/types are regenerated and clean

Run generic checks with the bundled `check_invariants.py`, but do not mistake it for project-specific proof.

