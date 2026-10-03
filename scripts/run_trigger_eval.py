#!/usr/bin/env python3
"""Run trigger cases through an optional JSON-lines evaluator command."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import UTC, datetime

from scripts.trigger_eval import ROOT, build_matrix, is_valid_selection, matrix_sha256


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evals/results/latest.json")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sample", type=int)
    parser.add_argument("--command")
    parser.add_argument(
        "--deterministic", action="store_true", help="omit the run timestamp for reproducible baseline files"
    )
    args = parser.parse_args()
    for option, value in (("--limit", args.limit), ("--sample", args.sample)):
        if value is not None and value < 1:
            parser.error(f"{option} must be a positive integer")
    try:
        matrix = build_matrix()
    except ValueError as exc:
        parser.error(str(exc))
    work = [
        (host, environment, case)
        for host in matrix["hosts"]
        for environment in matrix["environments"]
        for case in matrix["cases"]
        if host in case["supported_hosts"]
    ]
    if args.limit is not None:
        work = work[: args.limit]
    if args.sample is not None and args.sample < len(work):
        if args.sample == 1:
            indices = [len(work) // 2]
        else:
            intervals = args.sample - 1
            indices = [index * (len(work) - 1) // intervals for index in range(args.sample)]
        work = [work[index] for index in indices]
    results = [_evaluate(host, env, case, args.command) for host, env, case in work]
    counts = {status: sum(row["status"] == status for row in results) for status in ("passed", "failed", "not_run")}
    document = {
        "schema_version": 1,
        "matrix_sha256": matrix_sha256(matrix),
        "summary": {"total": len(results), **counts},
        "results": results,
    }
    if not args.deterministic:
        document["generated_at"] = datetime.now(UTC).isoformat()
    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    print(f"actual trigger evaluation: {counts} ({len(results)} total)")
    return int(counts["failed"] > 0)


def _evaluate(host: str, env: str, case: dict, command: str | None) -> dict:
    base = {"host": host, "environment": env, "skill": case["skill"], "type": case["type"], "case_id": case["id"]}
    if not command:
        return {**base, "status": "not_run", "actual": None, "error": "no evaluator command supplied"}
    process = subprocess.run(
        shlex.split(command),
        input=json.dumps({"host": host, "environment": env, "case": case}),
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        response = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        return {**base, "status": "failed", "actual": None, "error": f"{exc}; stderr={process.stderr}"}
    if not isinstance(response, dict) or "selected_skill" not in response:
        return {
            **base,
            "status": "failed",
            "actual": None,
            "error": f"evaluator response must be an object with selected_skill; stderr={process.stderr}",
        }
    actual = response["selected_skill"]
    if not isinstance(actual, str):
        return {
            **base,
            "status": "failed",
            "actual": None,
            "error": f"selected_skill must be a string, got {type(actual).__name__}",
        }
    expected = case["expected"]
    passed = process.returncode == 0 and is_valid_selection(host, actual) and (
        actual != expected.removeprefix("not:") if expected.startswith("not:") else actual == expected
    )
    return {**base, "status": "passed" if passed else "failed", "actual": actual, "error": process.stderr or None}


if __name__ == "__main__":
    raise SystemExit(main())
