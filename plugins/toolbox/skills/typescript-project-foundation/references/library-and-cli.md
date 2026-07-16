# Library and CLI profiles

## Published TypeScript library

Decide public API stability before implementation:

- ESM-only by default. Add CommonJS only for verified consumer demand.
- Define `exports`, types, supported runtime versions, and side-effect metadata explicitly.
- Emit declarations and test the packed artifact in a clean consumer fixture.
- Keep implementation modules private; do not export internal types accidentally.
- Use semantic versioning and document compatibility/deprecation policy.
- Test the lowest supported runtime and dependency range as well as the current lockfile.
- Add release automation, provenance/SBOM, or signing when public distribution or assurance requirements justify them.

Do not use workspace protocol ranges in the published artifact. Verify the exact package tarball contents before release.

## CLI

- Define stdin/stdout/stderr contracts and stable exit codes.
- Separate human-readable output from machine-readable JSON output.
- Never prompt in non-interactive/CI mode; provide flags and fail with actionable errors.
- Validate configuration and arguments at the boundary.
- Handle signals and partial writes safely.
- Decide installation/distribution target: npm package, standalone binary, or internal workspace command.
- Test Windows path/process behavior if Windows is supported.
- Avoid telemetry unless explicitly required, disclosed, and configurable.

For both profiles, avoid application-only dependencies such as React, Hono, Drizzle, or Tailwind unless the package's actual responsibility requires them.

