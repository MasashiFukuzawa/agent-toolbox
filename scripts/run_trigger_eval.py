#!/usr/bin/env python3
"""Run trigger cases through an optional JSON-lines evaluator command."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import UTC, datetime

from scripts.trigger_eval import ROOT, build_matrix


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evals/results/latest.json")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sample", type=int)
    parser.add_argument("--command")
    args = parser.parse_args()
    matrix = build_matrix()
    work = [(h, e, c) for h in matrix["hosts"] for e in matrix["environments"] for c in matrix["cases"]]
    if args.limit is not None:
        work = work[: args.limit]
    if args.sample is not None and args.sample < len(work):
        work = [work[int(index * len(work) / args.sample)] for index in range(args.sample)]
    results = [_evaluate(host, env, case, args.command) for host, env, case in work]
    counts = {status: sum(row["status"] == status for row in results) for status in ("passed", "failed", "not_run")}
    document = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {"total": len(results), **counts},
        "results": results,
    }
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
        actual = json.loads(process.stdout)["selected_skill"]
    except (json.JSONDecodeError, KeyError) as exc:
        return {**base, "status": "failed", "actual": None, "error": f"{exc}; stderr={process.stderr}"}
    passed = process.returncode == 0 and actual == case["expected"]
    return {**base, "status": "passed" if passed else "failed", "actual": actual, "error": process.stderr or None}


if __name__ == "__main__":
    raise SystemExit(main())
