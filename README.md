# Agent Toolbox

Agent Toolbox is a public collection of reusable engineering skills for Claude Code and Codex. It ships independently installable plugins for each host and shares host-neutral skill instructions where possible; host-specific skills document their supported hosts.

## Plugins

| Plugin | Skills | Purpose | Runtime dependency |
| --- | ---: | --- | --- |
| `toolbox` | 21 | Research, review, model selection, testing, visualization, and engineering decisions | Per-skill; see each `SKILL.md` |
| `plugin-release` | 1 | Codex Git marketplace release workflow | Git, GitHub CLI (`gh`), Codex CLI, Python 3.11+, `uv` |
| `done` | 1 | Repository-defined quality gate, with a Claude Code Stop adapter | Git, Bash, Python 3 |
| `gog` | 2 | Read-only Google Calendar and Chat workflows | [`gog`](https://github.com/steipete/gogcli) |
| `github-operations` | 2 | Guarded GitHub Project provisioning and Issue creation | Python 3.11+, `gh` |

### Skill catalog

- `toolbox` (21, Claude Code and Codex): `adr`, `ai-native-engineering`, `ascii-diagram`, `autopilot`, `behavioral-testing`, `browser-operations`, `claude-review`, `cloudflare-data-pipeline`, `cloudflare-worker-cd`, `codebase-audit`, `codex-review`, `context-handoff`, `e2e-capability-verification`, `git-worktrees`, `html-artifact`, `model-selection`, `owner-board`, `progress-report`, `structured-text-parsing`, `technical-research`, and `typescript-project-foundation`.
- `plugin-release` (1, Codex only): `plugin-release`.
- `done` (1, Claude Code and Codex): `done`.
- `gog` (2, Claude Code and Codex): `gog-calendar` and `gog-chat-readonly`.
- `github-operations` (2, Claude Code and Codex): `github-project-provisioning` and `github-issue-create`.

Autopilot delegates bounded work while the controller retains artifact review and shipping-quality responsibility. Model selection is shared by autopilot and both review skills; install the complete toolbox plugin rather than copying a review skill alone. Done accepts revision-bound evidence rather than repeating worker checks. Runtime servicing uses actual host task state, not a separate snapshot checker. No daemon or automatic host restart is installed; see the [runtime contract](plugins/toolbox/skills/autopilot/references/controller-runtime.md) for these limits.

## Install

### Progress report formats

`progress-report` accepts natural-language instructions to focus the report without requiring scope flags. Add `--ascii` for in-chat diagrams, `--html` for a saved visual HTML report, or both for an in-chat summary plus HTML. The report skill owns the facts and decision context; `ascii-diagram` and `html-artifact` own presentation. Install the complete toolbox plugin to use these integrations. HTML output does not authorize publishing or uploading it.

```text
progress-report --ascii Focus on blockers and dependencies
progress-report --html Focus on the release outlook
```

### Owner board

`owner-board` maintains a local owner communication board from JSON with fixed question IDs, decisions, human tasks, answer history, and pending follow-ups or relays. Its static HTML supports freely ordered text, tables, code, and offline SVG diagrams, including sequence and flow diagrams. Python 3.11+ is its only runtime dependency. Operational data stays outside public repositories; creating a board does not authorize publishing it or adding external messaging. General presentation uses `html-artifact`, progress context uses `progress-report`, and execution authority stays with `autopilot`.

### Claude Code

```text
/plugin marketplace add MasashiFukuzawa/agent-toolbox
/plugin install toolbox@agent-toolbox
/plugin install done@agent-toolbox
/plugin install gog@agent-toolbox
/plugin install github-operations@agent-toolbox
```

Use `/plugin` to update or uninstall a plugin. Claude Code discovers the marketplace from `.claude-plugin/marketplace.json`.

`plugin-release` is Codex-only. It was present in the shared toolbox package through 0.7.0 and is not available in Claude Code from 0.7.1 onward; there is no Claude Code replacement in this marketplace.

### Codex

Add this Git repository as a plugin marketplace in Codex, then install `toolbox`, `plugin-release`, `done`, `gog`, or `github-operations` from the `agent-toolbox` marketplace. Codex reads `.agents/plugins/marketplace.json`; the exact UI or CLI command depends on the installed Codex release. Since toolbox 0.7.1, `plugin-release` has been a separate Codex-only plugin and is not included in toolbox. Removing the skill from toolbox was a breaking package change, but shipped in 0.7.1 as a patch. Toolbox 0.8.0 marks the corrected policy and introduces no further breaking package change. Future skill removals or moves will ship in a minor version or higher. If you upgraded from toolbox 0.7.0 or earlier and relied on its bundled skill, install `plugin-release` separately from the `agent-toolbox` marketplace. In CLI versions whose `codex plugin --help` lists `add`, use `codex plugin add plugin-release@agent-toolbox`.

The `done` Stop hook is Claude Code-specific. In Codex, invoke the `done` skill before reporting repository changes complete.

## Security model

- Skills never include credentials, personal paths, organization-specific identifiers, or non-public operational details.
- Browser profiles and Google OAuth data remain outside the repository.
- `gog` skills permit read-only commands only and wrap untrusted Workspace content.
- Repository checks validate frontmatter, manifests, local links, trigger metadata, and common secret patterns. CI also runs gitleaks.
- Validation excludes untracked content ignored by repository `.gitignore` rules and local tool state. Tracked shared files remain subject to validation; personal Git excludes do not change the checks. Public symlinks must be relative, point directly to a regular file, and stay within the repository and, for plugin content, within the same plugin. Directory symlinks and chains are rejected. In copies without Git metadata, validation applies `.gitignore` rules and local-state exclusions, but cannot recover which ignored files were originally tracked. Validate the Git checkout before distributing such a copy.

Review a skill's guardrails before using it with authenticated services or write-capable tools.

## Development

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are required for repository tooling.

```bash
uv sync --dev
uv run ruff check .
uv run pytest
uv run python -m scripts.validate
uv run python -m scripts.trigger_eval --check
bash -n plugins/done/scripts/quality-gate-stop.sh
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution rules and [SECURITY.md](SECURITY.md) for vulnerability reporting.

## License

Apache-2.0. See [LICENSE](LICENSE).

`html-artifact` retains its standard mode and offers a visual-first mode for requests for simpler, diagram-heavy HTML. It keeps conclusions and decision-critical conditions visible, with optional supporting detail disclosed progressively. A fictional, self-contained sample is available in its templates directory.
