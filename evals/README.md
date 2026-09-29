# Trigger evaluation

`uv run python -m scripts.trigger_eval --check` verifies that every skill has the required evaluation cases and that cases are limited to each skill's `supported_hosts` in `docs/trigger-registry.yml`. It is a completeness check, not evidence that a model or host discovered the correct skill. `--json` emits the cases and their supported hosts.

`evals/results/baseline.json` stores a fingerprint of the generated matrix. Regenerate it with `uv run python -m scripts.run_trigger_eval --output evals/results/baseline.json` after changing prompts, expected selections, or supported hosts.

Each skill has three positive, two nearest-neighbor negative, two ambiguous, one explicit, and one no-skill-negative case. Evaluate them in both an isolated environment containing only this marketplace and a superset environment containing commonly installed plugins. A generic third-party-review prompt must return `ask-provider`, not choose a provider implicitly.

`uv run python -m scripts.run_trigger_eval` records cases as `not_run`. Add `--command 'uv run python -m scripts.model_trigger_adapter'` for catalog-level model evaluation. The adapter receives JSON on stdin and returns `{"selected_skill":"<name-or-decision>"}`. Use `--sample` for a representative subset. Catalog evaluation does not prove actual host plugin discovery.

Skill-local `evals/evals.json` files use the Claude plugin evaluation shape: a `skill_name` and an `evals` array containing `id`, `prompt`, `expected_output`, optional `files`, and optional qualitative `assertions`. Host discovery results follow [result-schema.json](result-schema.json).
