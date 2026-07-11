# Setup — background and manual steps

This document describes a portable setup and does not depend on a repository-local script.

## What gets installed

1. `@playwright/cli` — global npm install (`npm install -g @playwright/cli@latest`). Not npx: npx re-resolves on every call, which defeats the CLI's latency/token advantage and pins nothing.
2. `~/.mcp/browser-profiles/` (chmod 700) — base dir for per-site auth profiles. Site dirs (`github`, `notion`, …) are created by the wrapper on first login.
3. `~/.local/bin/pwauth` — wrapper that injects, for `open` only: `-s=<key> --persistent --profile=$HOME/.mcp/browser-profiles/<key> --browser=chrome --headed`, and `-s=<key>` for every other command. Rationale: if the LLM must hand-type profile flags, one forgotten flag silently becomes an in-memory profile ("my session vanished"). The wrapper makes the auth path a single fixed name.

## Design decisions (short form)

- **MCP configs are untouched** (Claude and Codex). Baking a shared logged-in profile into an MCP server default would carry all cookies into every task including untrusted browsing, and would serialize parallel sessions on one profile lock. The CLI-side wrapper gives cross-repo persistence only when auth is actually needed.
- **Per-site profile keys** instead of one shared profile: minimal credential exposure per task, and different sites never contend for the same lock.
- **Fail closed**: verify the CLI exposes `--persistent/--profile/--headed/--browser` before installing a wrapper. If the flag surface changes, stop.

## Manual steps (no repo at hand)

```bash
npm install -g @playwright/cli@latest
mkdir -p ~/.mcp/browser-profiles && chmod 700 ~/.mcp ~/.mcp/browser-profiles
# then create a local wrapper only after verifying the installed CLI flags
```

Health check: `bin/doctor.sh` (browser checks run only when `pwauth` exists; machines without it show SKIP).

## Appendix (opt-in): cross-repo profile for Playwright MCP too

Not recommended (see design decisions), but if the per-repo fallback profile ever becomes a real pain:

1. `claude plugin uninstall playwright@claude-plugins-official` (that plugin is MCP-only, no skills are lost; do NOT uninstall chrome-devtools-mcp — it bundles skills).
2. `claude mcp add --scope user playwright -- npx @playwright/mcp@latest --user-data-dir=$HOME/.mcp/browser-profiles/playwright-mcp --browser chrome`
3. Codex: edit `[mcp_servers.playwright]` args in `~/.codex/config.toml` the same way.
4. **Verify the flag actually reaches the child process** — there are reports of npx-wrapped MCP args being dropped (claude-code #24586): after starting a session, `ps aux | grep mcp-server-playwright` must show `--user-data-dir=…`; or check the profile dir's mtime after use. If the arg is dropped, call the installed binary directly instead of via npx.
5. Accept the trade-offs this skill's default avoids: shared cookies in every MCP browsing task and cross-session lock contention.
