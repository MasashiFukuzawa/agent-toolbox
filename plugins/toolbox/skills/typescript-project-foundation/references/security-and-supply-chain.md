# Security and supply-chain foundation

Apply the boundary controls to every production-intent project. Use OWASP ASVS 5 and the OWASP API Security Top 10 as threat-model-driven references, not as a ceremonial checklist.

## Identity and authorization

- Normalize provider identities into an internal identity model; retain provider subject values as opaque strings.
- Decide secure cookie vs bearer credentials, domain/subdomain topology, SameSite, CSRF, and CORS together.
- Enforce ownership/tenant scope in a shared data-access boundary, not only HTTP middleware.
- Default deny when actor, tenant, resource ownership, or policy cannot be resolved.
- Add negative tests for cross-user, cross-tenant, role escalation, object-level, and property-level access.
- Treat background jobs and admin scripts as authorization callers with explicit principals and scopes.

References:

- https://owasp.org/www-project-application-security-verification-standard/
- https://owasp.org/API-Security/editions/2023/en/0x04-release-notes/

## Secrets and configuration

- Never commit real secrets, `.env`, `.dev.vars`, credentials, tokens, or copied production data.
- Keep non-secret configuration versioned and environment-specific. Store secrets in the deployment platform or CI secret store.
- Separate preview/staging/production credentials and grant least privilege.
- Prefer short-lived federation/OIDC to long-lived cloud credentials when supported.
- Run secret scanning on staged changes and full history in CI. Document narrowly justified false-positive allowlists.
- Redact tokens, cookies, authorization headers, personal data, and sensitive domain fields before logging.

## pnpm controls

For production-intent repositories, put project security settings in `pnpm-workspace.yaml`, including single-package repositories:

```yaml
minimumReleaseAge: 10080
minimumReleaseAgeStrict: true
blockExoticSubdeps: true
```

Define a narrow `allowBuilds` mapping for dependencies whose lifecycle scripts are required. Do not use a broad allow-all switch. Cooling-period exceptions must name the smallest package scope and include reason, expiry, and removal trigger in the foundation record.

## GitHub Actions and Pinact

Full commit SHA pinning is the baseline because tags and branches are mutable. GitHub Actions usage in a production-intent repository requires Pinact by default.

Required behavior:

1. Pin external actions and reusable workflows to a full commit SHA; keep the human-readable version comment.
2. Configure Pinact with a default 3-day minimum age for action updates.
3. Run an offline Pinact consistency check in a local hook and a verification/min-age check in CI.
4. Enable Dependabot updates for the `github-actions` ecosystem.
5. Pin Pinact itself and verify official release checksums, or acquire it through an equivalently verified tool manager.
6. Exclude local `uses: ./...` references. Document any other technically unpinnable reference.
7. Allow replacement only when organization policy and another tool enforce immutable references, verification, and automated updates at least as strongly.

Minimal configuration (verify the current schema before generating it):

```yaml
# .pinact.yaml
version: 3
files:
  - pattern: .github/workflows/*.yml
  - pattern: .github/workflows/*.yaml
min_age:
  value: 3
  always: false
```

Also:

- Set workflow/job permissions to the minimum required.
- Avoid interpolating untrusted event fields directly into shell scripts.
- Treat `pull_request_target`, self-hosted runners, cache writes, artifact consumption, and workflow changes as elevated-risk surfaces.
- Verify checksums/signatures for downloaded binaries.
- Use CODEOWNERS or equivalent review ownership for workflow and security-policy changes when the repository supports it.

Reference: https://docs.github.com/en/actions/reference/security/secure-use

## Dependency maintenance

- Enable Dependabot or an equivalent update service for package and Actions ecosystems.
- Run an audit gate at a documented severity and investigate reachable impact; do not auto-fix blindly.
- Keep the lockfile immutable in CI.
- Review newly introduced maintainers, install scripts, exotic sources, and transitive native binaries.
- Record every supply-chain exception in a machine-checkable or reviewable ledger with an expiry.
