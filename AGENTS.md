# Repository instructions

- Keep all published content reusable. Never add organization-specific names, personal email addresses, credentials, internal repository names, customer data, incident details, or absolute home-directory paths.
- Commit messages and pull-request titles and descriptions are published with this repository and follow the same rule. When work references other repositories (fleet migrations, deployed-config audits), describe them generically — "a deployed config", counts, dialect names — instead of naming the organization or repository.
- Write for a general public audience. Keep workflows broadly reusable, and describe organization- or repository-specific behavior as optional configuration only when it materially affects the workflow.
- Skill directory names use kebab-case and equal the frontmatter `name`.
- Skill frontmatter contains exactly `name` and `description`, except that an explicit-only skill also sets `disable-model-invocation: true`.
- An explicit-only skill pairs that key with a skill-local `agents/openai.yaml` containing only `policy.allow_implicit_invocation: false`, so neither host invokes it implicitly. Do not use `agents/openai.yaml` for anything else.
- Descriptions state purpose, positive triggers, and the negative boundary against the nearest skill.
- Keep `SKILL.md` under 500 lines and move optional detail into `references/`.
- Write public repository documentation in English. Skill instructions and user-facing templates use Japanese, with English technical terms where clearer.
- Preserve host-neutral behavior unless a skill explicitly documents a Claude Code- or Codex-only adapter.
- Before reporting completion, run `uv run ruff check .`, `uv run pytest`, and `uv run python -m scripts.validate`. This is required whenever tracked files changed, whether the change is still in the working tree or already committed on the branch: check both `git status --porcelain` and the branch's diff against its base, and run the commands on the final revision. If neither shows a change — the task wrote its output outside the repository and touched nothing tracked — there is nothing to validate: state that the gate was skipped and why, instead of running it.

## Delegated scope

This section is what `autopilot` reads as the delegated scope for this repository.

### May do without asking

- Edit skills, scripts, tests, and documentation in this repository, run the checks, and create branches and pull requests.
- Choose the means of implementation and wording, where the choice can be undone. Record choices that change what users see on the goal page.
- Remove worktrees, branches, and temporary files created for the current goal, except anything with uncommitted or unpushed work.

### Must ask

- Removing or renaming a plugin or a skill, and any other change that breaks compatibility for people who installed the plugins.
- Changing what a hook or a script does on users' machines beyond the stated goal.
- Publishing outside this repository, and anything that needs credentials.

### Checks and merge

- Checks: the three commands above. CI runs the same commands and is required for a merge.
- Changes that need a deeper look: skill instructions (`SKILL.md`), hooks, scripts that run on users' machines, CI workflows, and anything that could make a skill work on only one host. Do not report them complete until a second model has reviewed them (`second-opinion`).
- Always review: whether an instruction allows more than one reading, whether shell in Markdown actually runs (undefined names, macOS and Linux differences, quoting), whether host-specific behavior is stated as such, and whether the README, the skill descriptions, and `CHANGELOG.md` match the behavior.
- Merge: a human approves, unless the request delegates merging; then merge once the checks, CI, and the required review pass. A release follows the `plugin-release` skill.
