#!/usr/bin/env python3
"""Adapt Claude Code or Codex CLI into the trigger-evaluator JSON protocol."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile

import yaml

from scripts.plugin_paths import public_paths, require_public_file, require_safe_repository_paths
from scripts.trigger_eval import ROOT


def main() -> int:
    payload = json.load(sys.stdin)
    try:
        skills = load_skill_catalog(payload["host"])
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
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
    try:
        selected = parse_selected_skill(output)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    # Hosts prepend the plugin namespace ("toolbox:codex-review"); the registry
    # and matrix use bare canonical names. Measured live: 11 of 14 failures in
    # the first real run were this prefix, not wrong selection.
    if ":" in selected and selected.split(":", 1)[1] in skills:
        selected = selected.split(":", 1)[1]
    print(json.dumps({"selected_skill": selected}))
    return 0


def parse_selected_skill(output: str) -> str:
    try:
        response = json.loads(output)
    except json.JSONDecodeError as exc:
        raise ValueError("model did not return a standalone JSON object") from exc
    if not isinstance(response, dict) or not isinstance(response.get("selected_skill"), str):
        raise ValueError("model response must be a JSON object with a string selected_skill")
    return response["selected_skill"]


def load_skill_catalog(host: str) -> dict[str, str]:
    require_safe_repository_paths(ROOT)
    registry = yaml.safe_load(require_public_file(ROOT, ROOT / "docs/trigger-registry.yml").read_text())["skills"]
    skills = {}
    for path in sorted(public_paths(ROOT, list(ROOT.glob("plugins/*/skills/*/SKILL.md")))):
        metadata = yaml.safe_load(require_public_file(ROOT, path).read_text().split("---", 2)[1])
        name = metadata["name"]
        supported_hosts = registry[name]["supported_hosts"]
        if host in supported_hosts:
            skills[name] = metadata["description"]
    return skills


if __name__ == "__main__":
    raise SystemExit(main())
