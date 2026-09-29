#!/usr/bin/env python3
"""Build and validate the cross-host trigger evaluation matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
KNOWN_HOSTS = ("claude-code", "codex")
REQUIRED_COUNTS = {
    "positive": 3,
    "explicit": 1,
    "no_skill_negative": 1,
}
NEUTRAL_DECISIONS = {"none", "disambiguate", "ask-provider"}


def build_matrix() -> dict:
    registry = yaml.safe_load((ROOT / "docs/trigger-registry.yml").read_text())["skills"]
    cases: list[dict] = []
    for name, entry in registry.items():
        supported_hosts = entry["supported_hosts"]
        triggers = entry.get("positive_triggers", [])
        base = triggers[0] if triggers else f"{name} を使って"
        positives = [base, f"{base}。判断理由も示して", f"{base}。安全条件を確認して進めて"]
        for index, prompt in enumerate(positives, 1):
            cases.append(_case(name, "positive", index, prompt, name, supported_hosts))

        neighbors = entry["nearest_neighbors"]
        if neighbors:
            for neighbor_index, neighbor in enumerate(neighbors):
                prompts = [
                    f"{neighbor} の対象として処理して。{name} は使わないで",
                    f"{name} ではなく {neighbor} を使って",
                ]
                for prompt_index, prompt in enumerate(prompts):
                    case_id = neighbor_index * len(prompts) + prompt_index + 1
                    cases.append(_case(name, "nearest_negative", case_id, prompt, neighbor, supported_hosts))
        else:
            for index, prompt in enumerate(
                [f"この依頼では {name} を使わないで", f"{name} の対象外として通常回答して"], 1
            ):
                cases.append(_case(name, "nearest_negative", index, prompt, "none", supported_hosts))

        if neighbors:
            for neighbor_index, neighbor in enumerate(neighbors):
                prompts = [
                    f"{name} と {neighbor} のどちらが適切か判断して",
                    f"{name} と {neighbor} の両方に見える依頼なので適用範囲を確認して",
                ]
                for prompt_index, prompt in enumerate(prompts):
                    case_id = neighbor_index * len(prompts) + prompt_index + 1
                    cases.append(_case(name, "ambiguous", case_id, prompt, "disambiguate", supported_hosts))
        else:
            for index, prompt in enumerate(
                [f"この依頼に {name} が必要か判断して", "適用するスキルが曖昧なので確認して"], 1
            ):
                cases.append(_case(name, "ambiguous", index, prompt, "disambiguate", supported_hosts))
        cases.append(_case(name, "explicit", 1, f"${name} を使って対象を処理して", name, supported_hosts))
        cases.append(
            _case(name, "no_skill_negative", 1, "短い挨拶だけ返して。専門スキルは使わないで", "none", supported_hosts)
        )
        for index, phrase in enumerate(entry["negative_triggers"], 1):
            cases.append(_case(name, "negative_trigger", index, phrase, f"not:{name}", supported_hosts))

    skill_descriptions = {}
    for path in sorted(ROOT.glob("plugins/*/skills/*/SKILL.md")):
        metadata = yaml.safe_load(path.read_text().split("---", 2)[1])
        skill_descriptions[metadata["name"]] = metadata["description"]

    return {
        "schema_version": 1,
        "hosts": list(KNOWN_HOSTS),
        "environments": ["isolated", "superset"],
        "skill_descriptions": skill_descriptions,
        "cases": cases,
    }


def _case(skill: str, kind: str, case_id: int, prompt: str, expected: str, supported_hosts: list[str]) -> dict:
    return {
        "skill": skill,
        "type": kind,
        "id": case_id,
        "prompt": prompt,
        "expected": expected,
        "supported_hosts": supported_hosts,
    }


def matrix_sha256(matrix: dict) -> str:
    canonical = json.dumps(matrix, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def is_valid_selection(host: str, selected: str) -> bool:
    if selected in NEUTRAL_DECISIONS:
        return True
    registry = yaml.safe_load((ROOT / "docs/trigger-registry.yml").read_text())["skills"]
    return selected in registry and host in registry[selected]["supported_hosts"]


def check_matrix(matrix: dict) -> list[str]:
    errors = []
    skills = yaml.safe_load((ROOT / "docs/trigger-registry.yml").read_text())["skills"]
    for skill, entry in skills.items():
        supported_hosts = set(entry["supported_hosts"])
        if not supported_hosts or not supported_hosts <= set(KNOWN_HOSTS):
            errors.append(f"{skill}: unsupported host declaration {sorted(supported_hosts)}")
        for kind, expected in REQUIRED_COUNTS.items():
            actual = sum(c["skill"] == skill and c["type"] == kind for c in matrix["cases"])
            if actual != expected:
                errors.append(f"{skill}: {kind} expected {expected}, got {actual}")
        nearest_expected = max(len(entry["nearest_neighbors"]), 1) * 2
        nearest_actual = sum(c["skill"] == skill and c["type"] == "nearest_negative" for c in matrix["cases"])
        if nearest_actual != nearest_expected:
            errors.append(f"{skill}: nearest_negative expected {nearest_expected}, got {nearest_actual}")
        ambiguous_expected = max(len(entry["nearest_neighbors"]), 1) * 2
        ambiguous_actual = sum(c["skill"] == skill and c["type"] == "ambiguous" for c in matrix["cases"])
        if ambiguous_actual != ambiguous_expected:
            errors.append(f"{skill}: ambiguous expected {ambiguous_expected}, got {ambiguous_actual}")
        negative_expected = len(entry["negative_triggers"])
        negative_actual = sum(c["skill"] == skill and c["type"] == "negative_trigger" for c in matrix["cases"])
        if negative_actual != negative_expected:
            errors.append(f"{skill}: negative_trigger expected {negative_expected}, got {negative_actual}")
        for case in (c for c in matrix["cases"] if c["skill"] == skill):
            if set(case.get("supported_hosts", [])) != supported_hosts:
                errors.append(f"{skill}: case {case['type']}:{case['id']} host support does not match registry")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    matrix = build_matrix()
    errors = check_matrix(matrix)
    if errors:
        parser.error("\n".join(errors))
    if args.json:
        print(json.dumps(matrix, ensure_ascii=False, indent=2))
    elif args.check:
        host_cases = sum(len(case["supported_hosts"]) for case in matrix["cases"])
        print(f"trigger-eval completeness: PASS ({host_cases} supported skill/case pairs per environment)")
    else:
        parser.error("choose --check or --json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
