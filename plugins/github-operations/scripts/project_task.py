#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def plugin_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "lib/github_operations/project_task.py").is_file():
            return candidate
    raise SystemExit("github-operations plugin runtime not found")


root = plugin_root()
sys.path.insert(0, str(root / "lib"))

from github_operations.github import run_gh  # noqa: E402
from github_operations.project_task import claim_project_task  # noqa: E402
from github_operations.safety import SafetyError  # noqa: E402


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("command", choices=("claim",))
    result.add_argument("--repo", required=True)
    result.add_argument("--owner", required=True)
    result.add_argument("--project-number", type=int, required=True)
    result.add_argument("--in-progress", default="In Progress")
    result.add_argument("--item-id")
    result.add_argument("--issue-url")
    result.add_argument("--issue-number", type=int)
    result.add_argument("--expected-status")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "claim":
            if (
                not args.item_id
                or not args.issue_url
                or args.issue_number is None
                or not args.expected_status
            ):
                raise SafetyError(
                    "claim requires --item-id, --issue-url, --issue-number, and --expected-status"
                )
            output = claim_project_task(
                run_gh,
                repo=args.repo,
                owner=args.owner,
                project_number=args.project_number,
                item_id=args.item_id,
                issue_url=args.issue_url,
                issue_number=args.issue_number,
                expected_status=args.expected_status,
                in_progress=args.in_progress,
            )
    except SafetyError as exc:
        print(f"github-operations: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
