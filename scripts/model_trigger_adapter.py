#!/usr/bin/env python3
"""Adapt Claude Code or Codex CLI into the trigger-evaluator JSON protocol."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile

import yaml

from scripts.trigger_eval import ROOT


def main() -> int:
    payload = json.load(sys.stdin)
    skills = {}
    for path in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")):
        metadata = yaml.safe_load(path.read_text().split("---", 2)[1])
        skills[metadata["name"]] = metadata["description"]
    catalog = "\n".join(f"- {name}: {description}" for name, description in skills.items())
    if payload["environment"] == "superset":
        catalog += "\n- generic-writing: 一般文章を編集する。専門的な開発workflowには使わない。"
        catalog += "\n- task-planning: 単純な計画を作る。実行や品質ゲートには使わない。"
    prompt = (
        f"You are evaluating skill-trigger metadata for {payload['host']}. Select only from the catalog, "
        "or return none, disambiguate, or ask-provider. Return exactly one JSON object: "
        '{"selected_skill":"<value>"}\n\nCatalog:\n' + catalog + "\n\nUser prompt:\n" + payload["case"]["prompt"]
    )
    if payload["host"] == "claude-code":
        process = subprocess.run(["claude", "-p", prompt], text=True, capture_output=True, check=False)
        output = process.stdout
    else:
        with tempfile.NamedTemporaryFile() as target:
            process = subprocess.run(
                ["codex", "exec", "--sandbox", "read-only", "-o", target.name, prompt],
                text=True,
                capture_output=True,
                check=False,
            )
            with open(target.name) as output_file:
                output = output_file.read()
    if process.returncode:
        raise SystemExit(process.stderr or "model command failed")
    match = re.search(r'\{\s*"selected_skill"\s*:\s*"([^"]+)"\s*\}', output, re.DOTALL)
    if not match:
        raise SystemExit("model did not return selected_skill JSON")
    selected = match.group(1)
    # Hosts prepend the plugin namespace ("toolbox:codex-review"); the registry
    # and matrix use bare canonical names. Measured live: 11 of 14 failures in
    # the first real run were this prefix, not wrong selection.
    if ":" in selected and selected.split(":", 1)[1] in skills:
        selected = selected.split(":", 1)[1]
    print(json.dumps({"selected_skill": selected}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
