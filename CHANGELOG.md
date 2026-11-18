# Changelog

Changes that people who installed the plugins need to know about. Each plugin (`toolbox`, `done`, `gog`, `github-operations`) has its own version. Below 1.0.0 a minor version may break compatibility; such releases are marked **Breaking** and say how to migrate.

After updating a plugin, restart running sessions: a session keeps the plugin version it started with.

## toolbox 0.22.1 (2026-11-18)

- `model-selection` now resolves Sol and Astra requests to GPT-6.2 Sol and GPT-6.2 Astra, respectively. Both start at low effort. When a request explicitly requires an older version, resolve the version requirement with the user before launch.

## toolbox 0.22.0 (2026-11-15)

- **A write outside the project is a person's decision.** `autopilot`, the delegated-scope template, and the global instructions define it as creating, changing, or deleting something in a place other people can see, other than the repository being worked on and its product's deployment targets (another repository, a public venue, an external service, mail or chat, a shared document or setting). Reading, queries to another model, and unshared local files are not affected. A session does it without asking only when the person asked for that operation directly, or the delegated scope, the agreement for the goal, or the project configuration names the destination and the operation; a configured task source delegates status updates and notes on the session's own tasks.
- A session no longer asks about, or recommends, an outside write that the goal does not need. It leaves a draft and records on the goal page that it did not go out.
- `human-briefing` has a form for asking approval of an outside or irreversible operation: the heading and the first sentence name the operation itself (what is created, changed, or deleted, where, under whose name, who can see it, whether it can be undone), a recommendation to do it must say what cannot be achieved otherwise, and one request covers one destination and one text.
- A complaint about being asked is not treated as permission. A rule that relaxes a must-ask item is recorded only after the person stated it or agreed to the exact line, and it does not cover the operation that prompted it.
- If your delegated scope listed only "sending or publishing outside" under must-ask, review it: changing settings and deleting things in outside services are now covered too. A delegation under "may do without asking" that names the destination and the operation takes precedence over the broad must-ask line.

## toolbox 0.21.0 (2026-11-15)

- `autopilot` preflight now recognizes repository and organization rulesets as well as classic branch protection. Automatic merge stays on when either one provides all three: a required status check, no force pushes, and no bypass. For a classic rule that means `enforce_admins`. For rulesets it means that the account about to merge cannot bypass the ruleset that requires the check or the one that blocks force pushes (`current_user_can_bypass: never`); other accounts are not examined. A ruleset the account can bypass or that cannot be read, and a rule in an unexpected shape, do not count. This removes the limit noted under 0.20.2.
- To make automatic merge take effect in a repository: run the real check on pull requests, require it on the base branch, block force pushes, and remove the bypass for the accounts that merge.

## toolbox 0.20.2 (2026-11-15)

- `autopilot` now says to act on the gates that `preflight` returns (`mergeGate`, `deployGate`), not on the values in the configuration file. `preflight` returns a human merge gate when the base branch has no branch protection with required status checks, enforcement for administrators, and force pushes disabled, even if the configuration asks for automatic merge. A review of a repository's instructions had found a merge condition written from the configured value alone.
- Known limit: `preflight` reads classic branch protection only. A base branch protected only by repository rulesets, without classic branch protection, is reported as unprotected, so automatic merge stays off there.

## toolbox 0.20.1 (2026-11-15)

- `autopilot` and the delegated-scope template now describe per-person gates (`actorOverrides` in `.agents/autopilot.json`): the default `gates` apply to everyone, and named GitHub accounts can be given a different value. Setting the default to a person's approval and granting automatic merge or deploy to named accounts keeps unlisted accounts on the safe side. The feature already existed; the rewritten instructions had stopped mentioning it.

## toolbox 0.20.0 (2026-11-15) — Breaking

**Breaking**

- The `done` plugin is retired. In local session records it almost never failed a change, and its one rule that mattered (a change that needs a deeper look is not complete until a second model has reviewed it) duplicated what `autopilot` and `second-opinion` already do. The rule now lives in the project's delegated scope, and the Stop hook and the `quality-gate` signature are gone.

**Changed**

- `autopilot` owns completion: checks bound to the revision, reuse of a result from CI or a helper on the same revision, reading the diff itself, and reporting what is unfinished as unfinished.
- The delegated-scope template has two new lines under checks and merge: which changes need a deeper look, and what a review must always look at.
- The example goal page shows overall progress as a percentage with a stacked bar, each acceptance condition with its own bar and next step, and where the goal sits in the larger objective. A detail that would crowd the goal page goes to a child page in the same design.

**Migrating from 0.19**

1. Uninstall the `done` plugin on each host (`/plugin` in Claude Code, the plugin list in Codex) and restart running sessions.
2. In each repository that has `.agents/done.yml`, move its content into the delegated-scope section of the project instruction file, then delete the file. Both spellings that the gate accepted are listed:

   | In `done.yml` | Goes to |
   |---|---|
   | `verify` commands | "Checks". A command with `when_changed` becomes a conditional line, for example "also run `<command>` when `<paths>` change" |
   | `verify` given per tier (`quick`, `standard`, `full`) | "Checks", written as conditions: what always runs, and what also runs for the changes that need a deeper look |
   | `tier_floors.full`, `full_conditions` | "Changes that need a deeper look" |
   | `tier_floors.quick` | Drop it, or say which changes need only the basic checks |
   | `review_criteria` or `review.criteria`, `docs_checks` or `docs.checks` | "Always review" |
   | `external_review` or `review.external` | Name the provider in the deeper-look line, or leave the choice to the session |

3. Remove every instruction that tells an agent to run the `done` skill or to emit a `quality-gate:` line, and replace it with "run the checks in the delegated scope on the final revision".

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
