# Skill conventions

## Naming

Choose the shortest kebab-case name that identifies the user-visible capability. Use a verb-led name when the action is clearer; retain a well-known artifact or domain noun when it triggers more reliably. Runtime and directory names use the same canonical name.

Renames in this repository:

- `research-first` + `documentation-lookup` → `technical-research` (removed; see below)
- `worktree-flow` → `git-worktrees`
- `write-meaningful-tests` → `behavioral-testing`
- `html-thinking` → `html-artifact`
- `claude-review` + `codex-review` → `second-opinion`
- `daily-plan` + `owner-board` → `autopilot` (folded into its goal page: the agreement, the current position, what is left to the human, and results with evidence live on one page per goal)

Removed, with the one rule each still carried moved into `global-instructions/AGENTS.md`: `technical-research` (confirm APIs, versions, limits, and recommended procedures against primary sources) and `structured-text-parsing` (process input with a defined format by deterministic means). `cloudflare-worker-cd` was removed because `typescript-project-foundation` carries the same deploy-safety sequence. Validation rejects references to removed names.

## Frontmatter

Shared skills use exactly two fields: `name` and `description`. The description is a folded YAML scalar (`>-`) and contains purpose, positive trigger, and nearest-neighbor negative boundary. Aim for 120–250 parsed characters; 300 is a warning and 500 is the hard limit.

### Description budget

Per-skill bounds are the only enforced budget. A catalog-wide 4,500-character
total cap existed until 2026-08 and was removed: it duplicated the per-skill
bounds, and because descriptions grow with skill count while the cap stayed
fixed, adding one skill forced trimming another's description — coupling
unrelated skills. Catalog residency cost is governed by the per-skill bound
times the deliberate decision to add a skill; that decision is where the cost
is weighed, not in a shared character pool.

Quoted trigger phrases (「…して」) in the description are what hosts match
against most reliably. Write one trigger per distinct case the skill handles;
synonyms for the same case are one case written twice.

Host-specific options do not belong in shared skill frontmatter. Put required commands, supported hosts, safety constraints, and side effects in the body.

The one exception is an explicit-only skill: one that must run only when the user names it, because running it unprompted costs time, tokens, or an outside call. Such a skill opts out of implicit invocation on both hosts at once:

- `disable-model-invocation: true` in the frontmatter (Claude Code; the description then stays out of context until the skill is invoked);
- `agents/openai.yaml` next to `SKILL.md` containing only `policy: {allow_implicit_invocation: false}` (Codex).

Validation rejects either half without the other and any other content in `agents/openai.yaml`. Users invoke such a skill as `/<plugin>:<name>` in Claude Code and `$<name>` in Codex. Choose it when unprompted runs would do harm, or when the skill is only ever invoked by hand and no other skill needs to reach it; its description then costs no context. A skill that merely triggers rarely does not need it.

## Writing the body

- Delete a sentence that does not change behavior versus what the model does by default. Two people who disagree about a sentence disagree about the default; settle it by running the skill.
- Keep each meaning in one place. When several skills need the same rule, one skill owns it and the others point to it (`human-briefing` owns how to write to a human; `html-artifact` owns visual design; `model-selection` owns model IDs).
- State the wanted behavior instead of a prohibition. Keep a prohibition only for a guardrail that cannot be phrased positively, and pair it with what to do.
- Write the host-neutral rule first. Name a host-specific tool, command, or flag only as an example for each host, so the skill reads correctly from Claude Code and from Codex.
- Leave what the environment already states (scripts, config, `--help` output) to the environment; record what cannot be found by looking: the convention, the reason, the pitfall.

## Skill evaluation files

A skill-local `evals/evals.json` uses the Claude plugin evaluation shape: a `skill_name` and an `evals` array whose cases have `id`, `prompt`, `expected_output`, optional `files`, and optional qualitative `assertions`. Validation checks the shape only; nothing in this repository runs the cases. An optional `evals/semantic-results.json` records a run of those cases and is bound to the hashes of `SKILL.md` and `evals.json`, so a record that no longer matches the skill fails validation: rerun it, or remove it when the skill was rewritten.

## Placement

- `toolbox`: general engineering workflows
- `gog`: skills whose runtime dependency is `gog`
- `github-operations`: guarded GitHub Project and Issue operations that share one script library

## Review provider precedence

`second-opinion` launches either provider. Explicit provider names win: Claude, Anthropic, Sonnet, Opus, or Fable requests launch the Claude CLI; Codex, OpenAI, sol, or astra requests launch the Codex CLI. If a user only asks for a third-party review and has not delegated the choice, ask which provider instead of selecting silently.
