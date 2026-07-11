# Trigger evaluation

`ruby scripts/trigger_eval.rb --check` verifies only that every skill has the required evaluation matrix. It is a dry/completeness check and is not evidence that a model selected the right skill. `--json` emits host-neutral cases.

Required cases per skill: positive 3, nearest-neighbor negative 2, ambiguous 2, explicit 1, and no-skill negative 1. Run the emitted cases in both an isolated environment containing only this marketplace and a superset environment containing commonly installed plugins. Generic third-party review prompts must result in `ask-provider`, not an implicit reviewer choice.

`ruby scripts/run_trigger_eval.rb` records every case as `not_run`. Supply `--command '<adapter>'` to perform actual evaluations; the adapter receives one case as JSON on stdin and returns `{"selected_skill":"<name-or-decision>"}`. Use `--sample` for a representative sample across the matrix. `scripts/model_trigger_adapter.rb` is a catalog-level Claude/Codex adapter; it evaluates metadata selection but does not prove host plugin discovery. Results follow `evals/result-schema.json`. A completeness PASS must never be reported as an actual evaluation PASS.
