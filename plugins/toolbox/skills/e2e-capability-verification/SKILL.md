---
name: e2e-capability-verification
description: >-
  staging や test 環境で認証付き E2E と機能可否を安全に検証する。破壊的操作や storageState が関わる検証に使う。アドホックなブラウザ操作には browser-operations を使う。「stagingで可能か確認」「認証付きE2Eを検証」を正のトリガーとし、日常的なサイト閲覧やログイン引き継ぎには使わない。
---
# E2E機能検証

UI automationやstagingでWeb appを検証する。機能が見当たらない、dataを変更し得る、または認証済みbrowser stateが必要な場合に特に適用する。

**振り分け**: repositoryのE2E wrapper、staging検証、破壊的flow gateには本Skillを使う。アドホック操作、tool選択、協調ログイン、repositoryをまたぐ個人sessionには `browser-operations` を使う。

## 必須ガードレール

- Do not conclude "not possible" from visible UI alone. Check at least one code/API source too: routes, shared schemas, generated OpenAPI, tests, DB schema, or network calls.
- Separate "no visible affordance" from "no capability". Say which one you have evidence for.
- Before destructive E2E, identify cleanup path first: UI delete, API delete, DB-safe fixture cleanup, or explicit user approval to leave data.
- Treat staging as real data unless the user explicitly says test data can be modified.
- Prefer dedicated staging/test users with minimum privileges; never use production or personal daily-use browser sessions for agent-driven E2E.
- Treat Playwright `storageState` files as credentials. Do not print, paste, summarize, commit, or inspect their cookie/localStorage/token contents.
- If authenticated browser state exists, reuse it only through an isolated context, and verify identity/tenant before actions.
- Do not ask the user to paste passwords, tokens, cookies, or storageState contents into the prompt. Ask them to run a local wrapper or auth setup if secrets are missing.
- If the repo provides an E2E wrapper, metadata precheck, auth-state validator, or runbook, treat that as canonical. Do not bypass it with raw Playwright CLI, raw Playwright MCP, ad hoc Browser sessions, or persistent personal Chrome profiles.
- If the repo standardizes 1Password Environments or another secret-injection wrapper for E2E auth setup, use only that wrapper for generating authenticated state. Do not manually export secret values, recreate the wrapper, or ask for the underlying username/password.
- Do not load authenticated staging state into Playwright CLI through raw state commands, CLI config, environment variables, persistent profiles, custom profiles, or stdout artifact modes unless the repo provides a wrapper with metadata precheck, private output handling, and policy guards.
- Treat Playwright CLI artifacts such as `.playwright-cli/`, snapshots, screenshots, traces, videos, network logs, and storage output from authenticated sessions as credential-like local-only artifacts.
- Do not run destructive or mutating flows unless the repo has both a cleanup path and an explicit gate runbook or user approval for the specific residual data risk.
- For unattended E2E, prefer the repo's CI-native secret store plus workload identity path over human-approved local secret access.
- If an E2E identity change crosses IAM, perimeter, secret-store, or deployment-stack boundaries, treat it as an infra change. Check the repo runbook for cross-stack apply order before changing app tests or workflows.

## token効率のよいworkflow

1. Define a small verification matrix: render, happy path, error path, persistence, cleanup, authorization if relevant.
2. Inspect code with `rg` before broad UI exploration: routes, mutation hooks, button labels, API client, tests.
3. Search repo docs and scripts for canonical wrappers before choosing a browser tool: `docs/agents/profile.md`, `AGENTS.md`, E2E runbooks, `package.json`, Playwright config, and scripts.
4. For authenticated staging E2E, run the authenticated preflight below before opening a browser.
5. Use UI tools narrowly:
   - Repo-provided Playwright MCP wrapper for normal authenticated staging E2E when available.
   - Repo-provided Playwright scripts or `@playwright/test` commands for repeatable flows, screenshots, traces, and assertions.
   - Playwright CLI only for non-authenticated or repo-wrapped exploratory checks; do not use raw CLI storage/profile/stdout paths for authenticated staging.
   - Raw Playwright MCP or raw Playwright scripts only when no repo wrapper exists; still use `--isolated` and explicit auth state if authenticated.
   - Chrome DevTools for focused console, network, performance, source-map, or memory debugging after a failure needs deeper inspection.
   - Computer Use only when human-mediated login, MFA, SSO, or a visual desktop-only condition makes browser automation impractical.
6. Prefer targeted selectors, network request summaries, and screenshots over dumping full accessibility trees or DOM.
7. Record only high-signal evidence: URL, user/tenant shown, action performed, request status, visible result, screenshot path if created.
8. For long E2E suites, codify the flow as a script and emit a compact JSON/Markdown report. Consider Webwright-style generated browser scripts when exploration must become repeatable.

## 認証付きE2Eのpreflight

Before authenticated staging/browser E2E:

1. Read the repo profile/runbook/script names, not secret-bearing files. Prefer a repo-standard metadata or precheck script if present.
2. Look for a repo-standard auth state path, commonly `playwright/.auth/staging-user.json`, without reading the file contents.
3. Confirm the auth state path is gitignored or otherwise outside version control.
4. If the repo has metadata such as `*.meta.json` or a validator script, run that precheck instead of inspecting `storageState`.
5. If the state file is missing, search package scripts and docs for an auth setup command such as `e2e:auth:staging`, `test:e2e:auth`, or `auth.setup`.
6. If the repo documents 1Password Environments for auth setup, first confirm non-secret prerequisites only: `op` CLI availability, required environment/item identifier variables, and the repo wrapper name. Never inspect or print 1Password secret values.
7. Run the repo-standard auth setup only through the documented wrapper. The wrapper may inject secrets into the child Playwright process, but the agent must not echo, log, persist, or pass those values outside the wrapper.
8. If auth setup cannot run because the secret store, 1Password Environment, local CLI, or access grant is unavailable, ask the user to configure that prerequisite or run the wrapper locally. Do not request raw credentials.
9. If an authenticated E2E attempt fails with redirects to login, 401/403 from expected authenticated APIs, missing identity UI, or expired-session symptoms, regenerate auth state once before treating it as an application bug.
10. After loading auth state, verify the displayed user/tenant or a safe identity endpoint before mutating data.

Use the repo wrapper for the normal path. If no wrapper exists, use Playwright MCP or Playwright scripts with an isolated browser context and explicit storage state, for example conceptually: `--isolated --storage-state=<repo-auth-state>`. Do not use a persistent personal Chrome profile as the default authenticated state. Do not use Playwright CLI config/env/profile mechanisms to inject auth state unless the repo has an explicit wrapper that runs the same auth-state precheck and keeps output local.

For repos with a 1Password-based staging auth setup, the preferred flow is:

1. Run the repo-provided auth setup script, commonly `pnpm e2e:auth:staging`, after confirming only non-secret prerequisites such as `op` CLI and the required 1Password Environment identifier.
2. Start the repo-provided Playwright MCP wrapper, commonly `pnpm mcp:staging:playwright`, so it can load storageState in an isolated context after metadata precheck.
3. If either command fails because `op` is missing, the Environment is unavailable, or access is denied, escalate that prerequisite to the human/credential owner and stop. Do not fall back to raw password prompts, `.env`, personal Chrome profiles, or manual secret exports.

## session永続化とprofile戦略

For ad-hoc (non-verification) browsing where the user's own login should persist across repos, use the per-site profile flow in `browser-operations` instead of the strategies below. For verification work, choose a persistence strategy before opening any browser tool. The decision order is:

1. **Repo provides a wrapper or runbook** → that is canonical; follow its method (storageState, MCP wrapper, auth script, etc.) and skip steps 2–4 below.
2. **Default: storageState file + dedicated minimum-privilege account**. Load it via `--isolated --storage-state=<repo-auth-state>`. This is the preferred baseline because:
   - An isolated context cannot leak cookies, localStorage, or tokens from the agent's regular environment.
   - The file is a well-scoped credential: gitignored, local-only, revocable, and compatible with repo wrappers that perform metadata precheck and TTL validation.
   - Re-generation is a single auth-setup command; no browser profile state accumulates across sessions.
3. **Persistent user-data-dir (dedicated profile)** — use *only* when all of the following hold:
   - storageState re-generation breaks frequently due to SSO, MFA, or IdP redirects that require a live browser session.
   - Manual login is unavoidable and frequent enough that storageState churn is a real workflow cost.
   - Alternatively: browser extensions or persistent device-trust are technically required.
   - **Required conditions when adopting**: use a **dedicated dir physically separate from your daily-use browser** (e.g. `~/.mcp/<agent>-profile`); treat the entire dir as a credential-equivalent artifact (do not print, commit, share, or sync it); if the repo defines a dedicated test account, bind the profile to that account only.
4. **Unattended quality gate** → prefer CI-native secret injection + workload identity (see *Unattended E2E and infra-boundary changes* below). Do not carry a local storageState file or user-data-dir into CI; generate state inside the job from the CI secret store.

**Human-login tolerance axis** — how much human involvement is acceptable:
- Human-present local check: use a local wrapper (macOS Keychain, 1Password Environment, etc.) to generate storageState, then hand off to the agent via `--storage-state`.
- SSO/MFA flows that cannot be automated: use Computer Use for the manual login step; after the human completes auth, capture storageState or the persistent profile for subsequent automated interactions within the same session.
- Unattended CI gate: no human involvement; use workload identity to fetch secrets and generate state inside the job.

**Profile boundary rule** (reinforcing the Non-negotiable above): agent profiles and human daily-use browser profiles must always be physically separate. Never mount your personal Chrome profile as an agent's browser context, even temporarily.

## 無人E2Eとinfra境界の変更

Use local secret wrappers for human-present development checks. For unattended quality gates, prefer CI-native secret injection and workload identity so agents can continue without a human approval prompt while still avoiding raw credentials in prompts, logs, or repositories.

When modifying E2E credentials, browser test workflow identity, secret access, network perimeters, or deployment-stack trust rules:

1. Read the repo's E2E runbook and infra dependency guide first.
2. Identify which stack owns the identity, which stack grants access, and which stack consumes it.
3. If a trust rule references an identity created by another stack, verify the required land/apply order before merging related PRs.
4. Do not treat the change as app-only just because the failing symptom appears in a browser E2E job.
5. If the correct apply order is unclear, ask for infra review before implementation.

## 機能切り分けchecklist

When a feature seems absent:

- UI: Is there a visible button/menu/dialog? Is it hidden by role, state, viewport, or selected item?
- API: Is there a route or mutation endpoint? What status codes and authz apply?
- Schema/DB: Is the operation safe with existing FKs, cascades, soft delete, audit retention, and tenant isolation?
- Tests: Are there existing tests proving the path or intentionally excluding it?
- Product boundary: Is this an MVP cleanup/admin action or user-facing workflow?

Only after this checklist say one of:

- "UI affordance exists and works."
- "Capability exists in API/code but UI affordance is missing."
- "No evidence of capability in UI/API/schema/tests."
- "Capability is intentionally blocked by product/security/data-integrity boundary."

## 破壊的flowのガードレール

Before create/update/delete on staging:

1. Prefer non-mutating checks first.
2. Find the repo's mutating-flow gate runbook or equivalent policy. If none exists, do not run the flow unless the user explicitly accepts the residual data risk.
3. If creating data, use an obvious synthetic test marker and verify a cleanup path.
4. If deleting data, verify the exact target and dependency behavior.
5. Confirm postcondition through UI and network/API, not just a toast.
6. If cleanup fails, document only safe residual metadata and the escalation path immediately.

## 証跡の扱い

- Do not share artifacts, traces, screenshots, network logs, cookies, tokens, `storageState` contents, request/response bodies with raw PII, provider raw payloads, OCR full text, private object keys, or presigned URLs.
- When evidence is needed, summarize sanitized facts: route path, status code, visible state, safe object type/id, marker, and failure category.
- Keep sensitive artifacts local and out of Issues, PRs, Slack, GitHub Actions artifacts, and final reports unless the repo runbook explicitly allows a sanitized artifact class.

## 失敗の切り分け

When authenticated E2E fails:

- Auth/session: retry once after regenerating auth state; if still failing, report that the staging E2E user, grants, tenant mapping, or auth setup needs human verification.
- UI: capture a screenshot and concise visible state; prefer selectors and visible labels over full DOM dumps.
- Console/network: summarize status codes, route paths, and error types without request bodies, tokens, cookies, or raw PII.
- Authorization/API: inspect routes, shared schemas, authz policy, generated OpenAPI, tests, and network status before concluding the UI is wrong.
- Performance/source-map/memory: use Chrome DevTools only for deeper debugging after Playwright evidence points there.
