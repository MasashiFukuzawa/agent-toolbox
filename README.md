# Agent Toolbox

Agent Toolbox is a public collection of reusable engineering skills for Claude Code and Codex. It ships independently installable plugins for each host and shares host-neutral skill instructions where possible; host-specific skills document their supported hosts.

## Plugins

| Plugin | Skills | Purpose | Runtime dependency |
| --- | ---: | --- | --- |
| `toolbox` | 22 | Human-facing reporting, autonomous execution and quality, and design and implementation decisions | Per-skill; see each `SKILL.md` |
| `done` | 1 | Repository-defined quality gate, with a Claude Code Stop adapter | Git, Bash, Python 3 |
| `gog` | 2 | Read-only Google Calendar and Chat workflows | [`gog`](https://github.com/steipete/gogcli) |
| `github-operations` | 2 | Guarded GitHub Project provisioning and Issue creation | Python 3.11+, `gh` |

### Skill catalog

- `toolbox` (22, Claude Code and Codex), in three groups:
  - Reporting to a human (9): `human-briefing`, `html-artifact`, `owner-board`, `daily-plan`, `progress-report`, `context-handoff`, `human-notify`, `ascii-diagram`, and `rephrase`.
  - Autonomous execution and quality (5): `autopilot`, `second-opinion`, `model-selection`, `git-worktrees`, and `step-back`.
  - Design and implementation (8): `ai-native-engineering`, `behavioral-testing`, `adr`, `codebase-audit`, `browser-operations`, `e2e-capability-verification`, `typescript-project-foundation`, and `cloudflare-data-pipeline`.
- `done` (1, Claude Code and Codex): `done`.
- `gog` (2, Claude Code and Codex): `gog-calendar` and `gog-chat-readonly`.
- `github-operations` (2, Claude Code and Codex): `github-project-provisioning` and `github-issue-create`.

`step-back` and `rephrase` run only when named: `/toolbox:<name>` in Claude Code, `$<name>` in Codex. `rephrase` restates the previous message from its background in the `human-briefing` rows when an explanation did not land.

Autopilot delegates bounded work while the controller retains artifact review and shipping-quality responsibility. Model selection is shared by autopilot and `second-opinion`; install the complete toolbox plugin rather than copying one skill alone. Done accepts revision-bound evidence rather than repeating worker checks. Runtime servicing uses actual host task state, not a separate snapshot checker. No daemon or automatic host restart is installed; see the [runtime contract](plugins/toolbox/skills/autopilot/references/controller-runtime.md) for these limits.

`second-opinion` launches the Claude or Codex CLI as an independent instance, from either host. It reviews a diff or a design against named viewpoints (missing, not asked for, implemented wrongly, documented-rule violations) and asks for a failure scenario with every finding. For a change whose behavior is visible from outside and whose gate tier is the deepest, the third party first runs the change on a fixed snapshot and checks the acceptance criteria. The caller acts only on findings that were reproduced or would be costly to miss.

## Install

### Progress report formats

`progress-report` accepts natural-language instructions to focus the report without requiring scope flags. Add `--ascii` for in-chat diagrams, `--html` for a saved visual HTML report, or both for an in-chat summary plus HTML. The report skill owns the facts and decision context; `ascii-diagram` and `html-artifact` own presentation. Install the complete toolbox plugin to use these integrations. HTML output does not authorize publishing or uploading it.

Human-facing HTML from `html-artifact`, `progress-report`, `owner-board`, and `daily-plan` is saved under `~/Documents/agent-artifacts/<project>/` (override with `AGENT_ARTIFACTS_DIR`), named `YYYY-MM-DD_<kind>_<slug>`, so Finder or Explorer can find output from either host in one place. `<project>` is the main repository name, also from a worktree. Sandboxed hosts need that directory allowed for writing: Codex `sandbox_workspace_write.writable_roots`, Claude Code `permissions.additionalDirectories`. Machine-read records such as review runs and handoffs stay in each skill's state directory.

```text
progress-report --ascii Focus on blockers and dependencies
progress-report --html Focus on the release outlook
```

### Human briefing

`human-briefing` is the single definition of how the skills write to a human, in chat or in a saved page. A request or report has four rows: background, problem, goal, and the ask (or what was done, when nothing is asked). A request carries one decision with one recommendation and its deciding reason, a figure placed before the options, and the checks an owner asks before replying: how large the change is, whether daily work changes, whether it can be undone, and why any waiting period exists. `html-artifact`, `owner-board`, `progress-report`, `context-handoff`, `daily-plan`, and `autopilot` point to it instead of restating the format.

### Owner board

`owner-board` keeps one continuously updated local HTML board of decisions and tasks for a human owner. It opens with the current milestone and what is blocked, lists open requests, and writes each request in the `human-briefing` format — background, problem, goal, and the ask, with a figure before the options of every decision — with fixed question IDs and an archive page for answers, follow-ups, and relays. Agents edit the HTML directly from a self-contained example; there is no runtime dependency. Operational boards stay outside public repositories; creating a board does not authorize publishing it or adding external messaging. General presentation and the save location use `html-artifact`, progress context uses `progress-report`, and execution authority stays with `autopilot`.

### Human notifications

`human-notify` delivers urgent local requests through a macOS dialog and speech routed to a configured audio device. Every notification identifies its repository. It runs asynchronously, suppresses duplicate requests, and serializes delivery across repositories. Dialog dismissal is never approval. Device configuration and delivery state stay in user-local directories; remote delivery and unattended reminders are not provided.

### Daily plan


`daily-plan` agrees on up to 24 hours of work with a human — a working day, or an overnight run — and tracks it on one local HTML page per plan. The page shows overall and per-task progress with each task's next step, time windows to protect, changes to the plan, each task's steps, and the gap to the period's goals. A bundled standard-library Python script renders the page from a JSON plan, judges step states from GitHub (`gh`) or a watched file, and with `--watch` re-renders on an interval until the plan ends. Agreeing to a plan does not approve merges, applies, or production jobs inside it; requests to humans stay on the `owner-board` and are linked by question ID.

### Step back

`step-back` re-examines the decision an agent has just made when its view has narrowed, for example a recommendation to revert a change made for a purpose, or to act before the cause is known. It splits the goal into constraints to keep, the function to restore and its deadline, and the chosen means; checks cause hypotheses against primary sources read-only; and rebuilds the options with reversibility, impact, and fit with the goal before stating a recommendation. It starts one read-only third-party review from the opposite provider through `second-opinion` (a Claude host launches Codex, a Codex host launches Claude) and reports any disagreement with the observation that would settle it. It runs only when invoked explicitly and does not delay an approved emergency rollback.

### Claude Code

```text
/plugin marketplace add MasashiFukuzawa/agent-toolbox
/plugin install toolbox@agent-toolbox
/plugin install done@agent-toolbox
/plugin install gog@agent-toolbox
/plugin install github-operations@agent-toolbox
```

Use `/plugin` to update or uninstall a plugin. Claude Code discovers the marketplace from `.claude-plugin/marketplace.json`.

### Codex

Add this Git repository as a plugin marketplace in Codex, then install `toolbox`, `done`, `gog`, or `github-operations` from the `agent-toolbox` marketplace. Codex reads `.agents/plugins/marketplace.json`; the exact UI or CLI command depends on the installed Codex release.

The `done` Stop hook is Claude Code-specific. In Codex, invoke the `done` skill before reporting repository changes complete.

### Global instructions (optional)

`global-instructions/AGENTS.md` is a Japanese-language set of cross-project principles for Claude Code, Codex, and Cursor.

Clone this repository to a location you only update with `git pull --ff-only`, then run the installer from that clone:

```bash
python3 global-instructions/install.py
```

It links `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, and `~/.cursor/AGENTS.md` to the clone's file for each host whose configuration directory exists (Claude Code reads a project's `AGENTS.md` but not a user-level one), and schedules a job that fast-forwards the clone every six hours: launchd on macOS, a systemd user timer on Linux. It never replaces a real file; back that file up, remove it, and re-run. Pass `--scheduler none` to skip the job, and `--uninstall` to remove the links into this clone and the job. Do not run it from a working checkout where you switch branches, because a branch without the file silently removes the instructions from every session.

### Recommended third-party skills (optional)

`recommended-skills/skills.toml` lists skills from other repositories that complement the toolbox plugin. Install them at user scope for Claude Code and Codex with [GitHub CLI](https://cli.github.com/) and [uv](https://docs.astral.sh/uv/):

```bash
python3 recommended-skills/install.py
```

The installer fetches each skill from its upstream repository and scans it with the [SkillSpector](https://github.com/NVIDIA/skillspector) release pinned in `tooling/skillspector`. A skill is installed only if the scan passes; a rejected skill leaves any installed copy unchanged. Re-run the installer to pick up upstream changes instead of `gh skill update`, which skips the scan. `--scan-only` scans without installing; CI runs it on every change. A passing static scan lowers the risk but does not prove a skill is safe, so still read a skill before relying on it.

## Security model

- Skills never include credentials, personal paths, organization-specific identifiers, or non-public operational details.
- Browser profiles and Google OAuth data remain outside the repository.
- `gog` skills permit read-only commands only and wrap untrusted Workspace content.
- Repository checks validate frontmatter, manifests, local links, skill evaluation files, and common secret patterns. CI also runs gitleaks.
- Validation excludes untracked content ignored by repository `.gitignore` rules and local tool state. Tracked shared files remain subject to validation; personal Git excludes do not change the checks. Public symlinks must be relative, point directly to a regular file, and stay within the repository and, for plugin content, within the same plugin. Directory symlinks and chains are rejected. In copies without Git metadata, validation applies `.gitignore` rules and local-state exclusions, but cannot recover which ignored files were originally tracked. Validate the Git checkout before distributing such a copy.

Review a skill's guardrails before using it with authenticated services or write-capable tools.

## Development

Python 3.15+ and [uv](https://docs.astral.sh/uv/) are required for repository tooling.

```bash
uv sync --dev
uv run ruff check .
uv run pytest
uv run python -m scripts.validate
bash -n plugins/done/scripts/quality-gate-stop.sh
```

Maintainer-only skills live in this repository instead of a plugin. Each is a file under `.agents/skills/<name>/` (read by Codex) with a `.claude/skills/<name>/SKILL.md` symlink to it (read by Claude Code), so both hosts load it when working in this repository. `plugin-release` releases these plugins to both marketplaces; it is no longer distributed as a Codex plugin, so uninstall `plugin-release@agent-toolbox` if you installed it.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution rules and [SECURITY.md](SECURITY.md) for vulnerability reporting.

## License

Apache-2.0. See [LICENSE](LICENSE).
