# Repository instructions

- Keep all published content reusable. Never add organization-specific names, personal email addresses, credentials, internal repository names, customer data, incident details, or absolute home-directory paths.
- Write for a general public audience. Keep workflows broadly reusable, and describe organization- or repository-specific behavior as optional configuration only when it materially affects the workflow.
- Skill directory names use kebab-case and equal the frontmatter `name`.
- Skill frontmatter contains exactly `name` and `description`.
- Do not add skill-local `agents/openai.yaml`; this repository has not adopted that metadata format.
- Descriptions state purpose, positive triggers, and the negative boundary against the nearest skill.
- Keep `SKILL.md` under 500 lines and move optional detail into `references/`.
- Write public repository documentation in English. Skill instructions and user-facing templates use Japanese, with English technical terms where clearer.
- Preserve host-neutral behavior unless a skill explicitly documents a Claude Code- or Codex-only adapter.
- Run `uv run ruff check .`, `uv run pytest`, `uv run python -m scripts.validate`, and `uv run python -m scripts.trigger_eval --check` before reporting completion.
