# Tool selection — details

## The three tools

| | @playwright/cli | Playwright MCP | Chrome DevTools MCP |
|---|---|---|---|
| Role | **act** (first choice) | act (fallback) | **observe** (debug/perf) |
| Invocation | Bash: `playwright-cli` / `pwauth` | MCP tools `browser_*` | MCP tools (snapshot, trace, …) |
| Token cost | Lowest — results go to `.playwright-cli/` on disk, read selectively | High — snapshot returned into context after most actions | Medium — event-driven, fetch on demand |
| Auth session | Per-site persistent profile via `pwauth` (shared across repos) | Persistent profile **per repo** (workspace hash) | One shared persistent profile |
| Headless default | Yes (`--headed` to show; `pwauth open` is always headed) | No (headed) | No (headed) |
| Cross-browser | chromium/firefox/webkit/chrome/msedge | same | Chrome only |

## When to pick what

- **Act tasks** — navigate, click, fill forms, scrape content, verify a UI flow, upload/download: `@playwright/cli`. Fall back to Playwright MCP only when Bash/CLI is unavailable (e.g. a sandboxed host without shell).
- **Observe tasks** — "why is this slow", "what is erroring", Core Web Vitals, request waterfalls, console errors, memory: Chrome DevTools MCP (`performance_start_trace`, `list_network_requests`, `list_console_messages`, `lighthouse_audit`, emulation).
- **Mixed**: operate with the CLI first; if a failure needs deeper inspection, reproduce it under Chrome DevTools MCP.

## @playwright/cli command map (v0.1.x)

Core loop:

```
playwright-cli open <url>            # or: pwauth <key> open <url>  (auth)
playwright-cli snapshot              # page snapshot → .playwright-cli/*.yml, elements get refs (e15…)
playwright-cli click e15             # act on refs from the snapshot
playwright-cli fill e20 "text"
playwright-cli eval "document.title"
playwright-cli screenshot [target]   # file path is printed, read only if needed
playwright-cli close
```

Useful extras:

- Sessions: `-s=<name>` runs several browsers in parallel (`pwauth` sets this to the profile key automatically).
- `console [min-level]`, `requests`, `request <n>` — lightweight debugging without switching tools.
- `state-save` / `state-load` — storageState files; treat as credentials, only use when a repo runbook calls for it (that flow belongs to e2e-capability-verification).
- `install-browser [browser]` if a browser binary is missing.
- Artifacts land in `.playwright-cli/` under the CWD — credential-like when the page was authenticated; never commit (gitignore it in repos where you use the CLI).

Boolean flags take no value (`--headed`, not `--headed=true`; `cookie-set --secure=true` crashes).

## Playwright MCP fallback notes

- Tools are `mcp__…playwright__browser_*` (navigate, click, fill_form, snapshot, …).
- Its persistent profile is per repo — logins do not carry across repos. If auth is needed here, run the cooperative login protocol inside this browser; the session persists for this repo only.
- Do not try to point it at the pwauth profiles; profile formats/locks are not shared between lanes.

## Chrome DevTools MCP notes

- Strengths: `performance_start_trace` → `performance_analyze_insight`, `lighthouse_audit`, network/console listing, CPU & network emulation, heap snapshots.
- Its profile is shared across repos and persists logins by itself — but it is a *different* profile from the pwauth lane: first authenticated debug of a site needs one extra login there.
- Treat its profile and captured artifacts as credential-like (see SKILL.md guardrails).
