#!/usr/bin/env python3
"""Deterministic plumbing for the autopilot skill.

The skill owns judgement: what to build, whether it is good enough, when to stop.
This owns the parts with no judgement in them -- resolving GitHub Project field
and option ids, picking the next task, deriving a branch name, moving the board,
and refusing to run when the repository identity or the merge gate does not check
out. Those are deterministic, so they belong in something that can be tested
rather than in prose an agent re-derives every run.

Subcommands print JSON on stdout and diagnostics on stderr. A non-zero exit means
the caller must stop: every failure here is a precondition for a write.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from typing import Any

BRANCH_PREFIX = "autopilot/"
BRANCH_MAX = 50


class Failure(Exception):
    """A precondition that must stop the run."""


def run_gh(args: list[str]) -> str:
    """Run a gh command and return stdout. Seam for tests."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise Failure(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def branch_name(title: str, issue_number: str | int | None) -> str:
    """Derive a branch name, falling back to the issue number for non-ASCII titles.

    A title that survives slugification only as a handful of characters is worse
    than no title at all, so anything under three characters also falls back.
    """
    normalized = unicodedata.normalize("NFKC", title)
    slug = re.sub(r"[^a-z0-9-]", "", re.sub(r"[\s/_]+", "-", normalized.lower()))
    slug = re.sub(r"-{2,}", "-", slug).strip("-")[:BRANCH_MAX].rstrip("-")
    if len(slug) < 3:
        if issue_number in (None, ""):
            raise Failure(
                f"cannot derive a branch name from {title!r} and no issue number is available"
            )
        return f"{BRANCH_PREFIX}issue-{issue_number}"
    return f"{BRANCH_PREFIX}{slug}"


def resolve_option_id(field_data: dict[str, Any], field: str, option: str) -> tuple[str, str]:
    """Return (field_id, option_id) for a single-select field, or fail loudly."""
    for entry in field_data.get("fields", []):
        if entry.get("name") != field:
            continue
        for candidate in entry.get("options", []):
            if candidate.get("name") == option:
                return entry["id"], candidate["id"]
        available = ", ".join(c.get("name", "?") for c in entry.get("options", []))
        raise Failure(f"field {field!r} has no option {option!r} (has: {available})")
    raise Failure(f"project has no field named {field!r}")


def pick_item(items: list[dict[str, Any]], pick_from: list[str]) -> dict[str, Any] | None:
    """Pick the highest-priority item, honouring the order of pick_from.

    Earlier entries in pick_from outrank later ones. Within one status, `priority`
    is a best-effort tiebreak: its type is repository-defined (often a string like
    "P1: next"), so it is compared as text and missing values sort last.
    """
    eligible = [item for item in items if item.get("status") in pick_from]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda item: (
            pick_from.index(item["status"]),
            item.get("priority") is None,
            str(item.get("priority", "")),
        ),
    )


def gate_allows(config: dict[str, Any], gate: str) -> bool:
    """True for the string "auto" or boolean true. Anything else means a human decides.

    Fail closed on anything ambiguous -- an unset gate, a typo, "yes", 1, "Auto" --
    because reading leniently here means an unattended run merges on a misspelling.
    Both accepted forms are unmistakable affirmatives, and deployed configs use the
    boolean, so rejecting it would leave a config that says merge automatically
    quietly never doing so.
    """
    value = config.get("gates", {}).get(gate)
    return value == "auto" or value is True


def protection_is_enforced(protection: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check that branch protection can actually stop a bad automated merge.

    Returned reasons name what is missing. Declaring `gates.merge: auto` without
    these means nothing but the agent's own care stands between a task and the
    default branch.
    """
    reasons = []
    checks = protection.get("required_status_checks") or {}
    if not (checks.get("contexts") or checks.get("checks")):
        reasons.append("no required status checks")
    if not (protection.get("enforce_admins") or {}).get("enabled"):
        reasons.append("enforce_admins is off, so protection does not apply to admins")
    if (protection.get("allow_force_pushes") or {}).get("enabled"):
        reasons.append("force pushes are allowed")
    return not reasons, reasons


def load_config(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise Failure(f"{path} not found; autopilot will not write without a config") from exc
    except json.JSONDecodeError as exc:
        raise Failure(f"{path} is not valid JSON: {exc}") from exc


def cmd_preflight(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(args.config)
    expected = config.get("repo")
    if not expected:
        raise Failure(f"{args.config} has no 'repo'; refusing to guess which repository this is")

    actual = json.loads(run_gh(["repo", "view", "--json", "nameWithOwner"]))["nameWithOwner"]
    if actual != expected:
        raise Failure(
            f"repository mismatch: config says {expected}, this directory is {actual}. "
            "Refusing every write."
        )

    base = config.get("baseBranch", "main")
    result: dict[str, Any] = {"repo": expected, "baseBranch": base, "mergeGate": "human"}

    if gate_allows(config, "merge"):
        raw = run_gh(["api", f"repos/{expected}/branches/{base}/protection"])
        enforced, reasons = protection_is_enforced(json.loads(raw))
        if not enforced:
            raise Failure(
                f"gates.merge is 'auto' but {base} is not protected enough to merge unattended: "
                + "; ".join(reasons)
            )
        result["mergeGate"] = "auto"
    return result


def cmd_next_task(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(args.config)
    source = config.get("taskSource", {}).get("githubProjects", {})
    owner, number = source.get("owner"), source.get("projectNumber")
    if not owner or number is None:
        raise Failure("taskSource.githubProjects needs both 'owner' and 'projectNumber'")

    number = str(number)
    project = json.loads(run_gh(["project", "view", number, "--owner", owner, "--format", "json"]))
    fields = json.loads(
        run_gh(["project", "field-list", number, "--owner", owner, "--format", "json"])
    )
    items = json.loads(
        run_gh(["project", "item-list", number, "--owner", owner, "--format", "json"])
    ).get("items", [])

    resumable = pick_item(items, ["In Progress"])
    picked = resumable or pick_item(items, source.get("pickFrom", ["Ready"]))
    if picked is None:
        return {"task": None}

    field_id, option_id = resolve_option_id(fields, "Status", "In Progress")
    if resumable is None:
        run_gh(
            [
                "project", "item-edit",
                "--project-id", project["id"],
                "--id", picked["id"],
                "--field-id", field_id,
                "--single-select-option-id", option_id,
            ]
        )
    content = picked.get("content") or {}
    return {
        "task": {
            "itemId": picked["id"],
            "title": picked.get("title", ""),
            "issueUrl": content.get("url"),
            "issueNumber": content.get("number"),
            "branch": branch_name(picked.get("title", ""), content.get("number")),
            "resumed": resumable is not None,
            "projectId": project["id"],
        }
    }


def cmd_set_status(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(args.config)
    source = config.get("taskSource", {}).get("githubProjects", {})
    owner, number = source.get("owner"), str(source.get("projectNumber"))
    fields = json.loads(
        run_gh(["project", "field-list", number, "--owner", owner, "--format", "json"])
    )
    field_id, option_id = resolve_option_id(fields, "Status", args.status)
    run_gh(
        [
            "project", "item-edit",
            "--project-id", args.project_id,
            "--id", args.item_id,
            "--field-id", field_id,
            "--single-select-option-id", option_id,
        ]
    )
    return {"itemId": args.item_id, "status": args.status}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=".agents/autopilot.json")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("preflight", help="verify repository identity and the merge gate")
    sub.add_parser("next-task", help="resume or claim the next task, and move it to In Progress")

    status = sub.add_parser("set-status", help="move a board item to a status")
    status.add_argument("--project-id", required=True)
    status.add_argument("--item-id", required=True)
    status.add_argument("--status", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "preflight": cmd_preflight,
        "next-task": cmd_next_task,
        "set-status": cmd_set_status,
    }
    try:
        print(json.dumps(handlers[args.command](args), ensure_ascii=False, indent=2))
    except Failure as exc:
        print(f"autopilot: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
