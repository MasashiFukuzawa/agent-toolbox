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
    print(json.dumps({"selected_skill": match.group(1)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
