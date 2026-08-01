# Skill conventions

## Naming

Choose the shortest kebab-case name that identifies the user-visible capability. Use a verb-led name when the action is clearer; retain a well-known artifact or domain noun when it triggers more reliably. Runtime and directory names use the same canonical name.

Renames in this repository:

- `research-first` + `documentation-lookup` → `technical-research`
- `worktree-flow` → `git-worktrees`
- `write-meaningful-tests` → `behavioral-testing`
- `html-thinking` → `html-artifact`

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
against most reliably; keep them aligned with `docs/trigger-registry.yml`,
whose `positive_triggers[0]` and `nearest_neighbors[0]` drive the evaluation
matrix.

Host-specific options do not belong in shared skill frontmatter. Put required commands, supported hosts, safety constraints, and side effects in the body and `docs/trigger-registry.yml`.

## Placement

- `toolbox`: general engineering workflows
- `done`: quality-gate core and host adapters
- `gog`: skills whose runtime dependency is `gog`

## Review provider precedence

Explicit provider names win: Claude requests use `claude-review`; Codex or OpenAI requests use `codex-review`. If a user only asks for a third-party review, ask which provider instead of selecting silently.
