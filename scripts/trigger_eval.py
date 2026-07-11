#!/usr/bin/env python3
"""Build and validate the cross-host trigger evaluation matrix."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_COUNTS = {
    "positive": 3,
    "nearest_negative": 2,
    "ambiguous": 2,
    "explicit": 1,
    "no_skill_negative": 1,
}


def build_matrix() -> dict:
    registry = yaml.safe_load((ROOT / "docs/trigger-registry.yml").read_text())["skills"]
    cases: list[dict] = []
    for name, entry in registry.items():
        triggers = entry.get("positive_triggers", [])
        base = triggers[0] if triggers else f"{name} を使って"
        positives = [base, f"{base}。判断理由も示して", f"{base}。安全条件を確認して進めて"]
        for index, prompt in enumerate(positives, 1):
            cases.append(_case(name, "positive", index, prompt, name))

        neighbors = entry.get("nearest_neighbors", [])
        neighbor = neighbors[0] if neighbors else None
        negatives = (
            [f"{neighbor} の対象として処理して。{name} は使わないで", f"{name} ではなく {neighbor} を使って"]
            if neighbor
            else [f"この依頼では {name} を使わないで", f"{name} の対象外として通常回答して"]
        )
        for index, prompt in enumerate(negatives, 1):
            cases.append(_case(name, "nearest_negative", index, prompt, neighbor or "none"))

        ambiguous = (
            [f"{name} と {neighbor} のどちらが適切か判断して", "両方に見える依頼なので適用範囲を確認して"]
            if neighbor
            else [f"この依頼に {name} が必要か判断して", "適用するスキルが曖昧なので確認して"]
        )
        for index, prompt in enumerate(ambiguous, 1):
            cases.append(_case(name, "ambiguous", index, prompt, "disambiguate"))
        cases.append(_case(name, "explicit", 1, f"${name} を使って対象を処理して", name))
        cases.append(_case(name, "no_skill_negative", 1, "短い挨拶だけ返して。専門スキルは使わないで", "none"))

    return {
        "schema_version": 1,
        "hosts": ["claude-code", "codex"],
        "environments": ["isolated", "superset"],
        "cases": cases,
    }


def _case(skill: str, kind: str, case_id: int, prompt: str, expected: str) -> dict:
    return {"skill": skill, "type": kind, "id": case_id, "prompt": prompt, "expected": expected}


def check_matrix(matrix: dict) -> list[str]:
    errors = []
    skills = yaml.safe_load((ROOT / "docs/trigger-registry.yml").read_text())["skills"]
    for skill in skills:
        for kind, expected in REQUIRED_COUNTS.items():
            actual = sum(c["skill"] == skill and c["type"] == kind for c in matrix["cases"])
            if actual != expected:
                errors.append(f"{skill}: {kind} expected {expected}, got {actual}")
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
        print(f"trigger-eval completeness: PASS ({len(matrix['cases'])} cases per host/environment)")
    else:
        parser.error("choose --check or --json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
