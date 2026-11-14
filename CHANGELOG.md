# Changelog

Changes that people who installed the plugins need to know about. Each plugin (`toolbox`, `done`, `gog`, `github-operations`) has its own version. Below 1.0.0 a minor version may break compatibility; such releases are marked **Breaking** and say how to migrate.

After updating a plugin, restart running sessions: a session keeps the plugin version it started with.

## toolbox 0.19.2 (2026-11-15)

- The example goal page that `autopilot` copies now leads with figures: a progress track, a time band against the limit, before/after tiles, option cards, and evidence shown as before/after. The page rules ask for a figure, table, or card as the main element of every section.
- Added this changelog and `docs/design.md`.

## toolbox 0.19.1 (2026-11-15)

- `autopilot` records what a goal creates (worktrees, branches, containers, images, volumes, servers, temporary files) and removes it when the goal ends. Anything with uncommitted or unpushed work, data, or an unknown owner is listed for the human instead.
- At the end of a goal, questions that a written rule would have made unnecessary become a proposed one-line rule for the delegated scope.

## toolbox 0.19.0, done 0.4.1 (2026-11-15) — Breaking

`autopilot` was rebuilt around one rule: one goal is carried by one session at a time, on one page, until it is accepted.

**Breaking**

- `owner-board` and `daily-plan` are removed. The goal page of `autopilot` replaces both.
- The controller/worker runtime of `autopilot` and its journal conventions are removed.
- The toolbox plugin now ships hooks (`Stop`, `PermissionRequest`, and `StopFailure` on Claude Code). They do nothing unless a session marks its worktree as carrying a goal.

**Added**

- Goal page: one self-contained HTML page per goal, with the agreement, the current position, what is left to the human, decisions made inside the delegated scope, and results with evidence.
- Delegated scope: a section in the project instruction file that says what may be done without asking and what must always be asked. A template is in `plugins/toolbox/skills/autopilot/references/delegation.md`.
- Stop notice: a desktop notice when the session that carries a goal stops, fails on an API error, or waits for permission (`human-notify/scripts/waiting_notify.py`).
- `done` no longer proposes creating its configuration unasked.

**Migrating from 0.18**

1. Update the plugins on each host and restart running sessions.
2. Existing owner-board and daily-plan pages are not converted. Finish the work they track, or agree on it again as a goal; `autopilot` then creates a goal page.
3. Add a delegated-scope section to each project's instruction file from the template. Without it, `autopilot` uses the template's must-ask list and waits for a human to approve merges.
4. `.agents/autopilot.json` is still read as before; no change is required.
5. On Codex, review and trust the toolbox hooks with `/hooks`. In a sandboxed host, allow writing to `~/Documents/agent-artifacts` (goal pages) and `~/.local/state` (goal marks and other state); Codex's default sandbox also keeps the Git directory read-only.
6. On macOS, allow notifications for the script runner to see the stop notice.
7. If you copied `global-instructions/AGENTS.md` instead of installing it with the script, copy it again.

## toolbox 0.18.1 (2026-11-15)

- `daily-plan` dropped its timeline. (The skill itself was removed in 0.19.0.)

## toolbox 0.18.0, done 0.4.0, github-operations 0.4.0 (2026-11-15) — Breaking

**Breaking**

- `claude-review` and `codex-review` are merged into `second-opinion`. Name the provider in the request as before.
- `technical-research`, `structured-text-parsing`, and `cloudflare-worker-cd` are removed. The rule each one carried moved to `global-instructions/AGENTS.md` or to `typescript-project-foundation`.

**Added and changed**

- `human-briefing`: the single format for requests and reports to a human (background, problem, goal, the ask).
- `rephrase` (runs only when named): restates the previous message in that format.
- `second-opinion`: runs the change on a fixed snapshot for the deepest tier, asks for a failure scenario with every finding, and acts only on findings that were reproduced or would be costly to miss.
- `behavioral-testing`: guidance on whether a test is needed, on test reliability, and on a scoped test inventory. `codebase-audit` checks whether tests are meaningful.
- `typescript-project-foundation`: day-zero items for a repository that agents will work in.

## Earlier releases

See the Git history.
