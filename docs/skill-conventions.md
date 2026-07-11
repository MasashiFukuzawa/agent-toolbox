# Skill conventions

## Naming

Choose the shortest kebab-case name that identifies the user-visible capability. Use a verb-led name when the action is clearer; retain a well-known artifact or domain noun when it triggers more reliably. Runtime and directory names use the same canonical name.

Renames in this repository:

- `research-first` + `documentation-lookup` → `technical-research`
- `worktree-flow` → `git-worktrees`
- `write-meaningful-tests` → `behavioral-testing`

## Frontmatter

Shared skills use exactly two fields: `name` and `description`. The description is a folded YAML scalar (`>-`) and contains purpose, positive trigger, and nearest-neighbor negative boundary. Aim for 120–250 parsed characters; 300 is a warning and 500 is the hard limit.

Host-specific options do not belong in shared skill frontmatter. Put required commands, supported hosts, safety constraints, and side effects in the body and `docs/trigger-registry.yml`.

## Placement

- `toolbox`: general engineering workflows
- `done`: quality-gate core and host adapters
- `gog`: skills whose runtime dependency is `gog`

## Review provider precedence

Explicit provider names win: Claude requests use `claude-review`; Codex or OpenAI requests use `codex-review`. If a user only asks for a third-party review, ask which provider instead of selecting silently.
