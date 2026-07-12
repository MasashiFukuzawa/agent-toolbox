from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .github import (
    project_fields,
    project_structure,
    require_project,
    resolve_field,
    resolve_option,
    resolve_project,
    run_gh,
)
from .planning import (
    find_config,
    load_config,
    make_issue_plan,
    make_project_plan,
    observe_issue,
    observe_project,
    project_verification_errors,
)
from .safety import SafetyError, digest
from .state import (
    cleanup_old_journals,
    clear_stale_lock,
    exclusive_lock,
    load_journal,
    load_plan,
    save_journal,
    save_plan,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="github-operations")
    parser.add_argument("domain", choices=("project", "issue"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("inspect", "plan", "verify"):
        child = subparsers.add_parser(command)
        child.add_argument("--config")

    project_apply = subparsers.add_parser("apply")
    project_apply.add_argument("--plan-id", required=True)
    project_apply.add_argument("--confirm-target", required=True)

    issue_plan = subparsers.choices["plan"]
    issue_plan.add_argument("--repo")
    issue_plan.add_argument("--title")
    issue_plan.add_argument("--body")
    issue_plan.add_argument("--body-file")
    issue_plan.add_argument("--label", action="append", default=[])
    issue_plan.add_argument("--assignee")
    issue_plan.add_argument("--priority")

    resume = subparsers.add_parser("resume")
    resume.add_argument("--plan-id", required=True)
    resume.add_argument("--confirm-target", required=True)
    unlock = subparsers.add_parser("unlock")
    unlock.add_argument("--target", required=True)
    unlock.add_argument("--confirm-target", required=True)
    return parser


def _issue_request(args: argparse.Namespace) -> dict:
    if not args.repo or not args.title:
        raise SafetyError("issue plan requires --repo and --title")
    if args.body and args.body_file:
        raise SafetyError("use only one of --body or --body-file")
    body = Path(args.body_file).read_text() if args.body_file else (args.body or "")
    return {
        "repo": args.repo,
        "title": args.title,
        "body": body,
        "labels": args.label,
        "assignee": args.assignee,
        "priority": args.priority,
    }


def _load_current(plan: dict) -> tuple[Path, dict]:
    path = Path(plan["config_path"])
    config = load_config(path)
    if digest(config) != plan["config_digest"]:
        raise SafetyError("config changed after planning; create and approve a new plan")
    return path, config


def _verify_identity(plan: dict, config: dict) -> None:
    from .github import identity

    current = identity(run_gh, config.get("host", "github.com"))
    if current.__dict__ != plan["identity"]:
        raise SafetyError("GitHub identity changed after planning; create and approve a new plan")


def _verify_observed(plan: dict, config: dict) -> None:
    current = (
        observe_project(run_gh, config)
        if plan["domain"] == "project"
        else observe_issue(run_gh, config, plan["request"])
    )
    if digest(current) != plan["observed_digest"]:
        raise SafetyError("GitHub state changed after planning; create and approve a new plan")


def _apply_project(plan: dict, config: dict, journal: dict, *, allow_reconcile: bool) -> dict:
    owner = config["owner"]
    project_cfg = config["project"]
    template = plan["observed"]["template"]
    planned_project = plan["observed"]["existing"]
    if plan["observed"].get("drift"):
        raise SafetyError("Project contract drift requires manual remediation; apply was not attempted")
    recovery_steps = {"copy-attempted", "project-copied"} & set(journal.get("steps", []))
    if allow_reconcile and planned_project is None and not recovery_steps:
        raise SafetyError("Project resume requires a journal proving that this plan attempted the copy")
    project = resolve_project(run_gh, owner, project_cfg["title"])
    if planned_project is not None:
        if project is None or project["id"] != planned_project["id"]:
            raise SafetyError("target Project identity changed after planning")
    elif project is not None and not recovery_steps:
        raise SafetyError("target Project appeared after planning; create and approve a new plan")
    if project is not None and journal.get("project_id") and journal["project_id"] != project["id"]:
        raise SafetyError("journal Project ID does not match the current target Project")
    if project is None:
        journal.setdefault("steps", [])
        if "copy-attempted" not in journal["steps"]:
            journal["steps"].append("copy-attempted")
            save_journal(plan["plan_id"], journal)
        try:
            run_gh(
                [
                    "project",
                    "copy",
                    str(template["number"]),
                    "--source-owner",
                    project_cfg["template"]["owner"],
                    "--target-owner",
                    owner,
                    "--title",
                    project_cfg["title"],
                ],
                retries=0,
            )
        except SafetyError:
            project = resolve_project(run_gh, owner, project_cfg["title"])
            if project is None:
                raise
        else:
            project = require_project(run_gh, owner, project_cfg["title"])
    journal["project_id"] = project["id"]
    journal["project_number"] = project["number"]
    journal.setdefault("steps", [])
    if "project-copied" not in journal["steps"] and planned_project is None:
        journal["steps"].append("project-copied")
    save_journal(plan["plan_id"], journal)
    linked = set(project_structure(run_gh, project["id"])["repositories"])
    for repo in config.get("repositories", []):
        full_name = f"{owner}/{repo}"
        if full_name not in linked:
            try:
                run_gh(
                    ["project", "link", str(project["number"]), "--owner", owner, "--repo", full_name], retries=0
                )
            except SafetyError:
                linked = set(project_structure(run_gh, project["id"])["repositories"])
                if full_name not in linked:
                    raise
            journal["steps"].append(f"repository-linked:{full_name}")
            save_journal(plan["plan_id"], journal)
    current = observe_project(run_gh, config)
    verification_errors = project_verification_errors(current, config)
    if verification_errors:
        raise SafetyError("post-apply verification failed: " + "; ".join(verification_errors))
    journal["steps"].append("verified")
    save_journal(plan["plan_id"], journal)
    return {
        "project": current["existing"],
        "verified": True,
        "browser_required": bool(config.get("auto_add")),
        "journal": journal,
    }


def _find_issue_by_fingerprint(plan: dict, repository_name: str) -> list[str]:
    output = json.loads(
        run_gh(
            [
                "api",
                "--paginate",
                "--slurp",
                "--method",
                "GET",
                f"repos/{repository_name}/issues",
                "-f",
                "state=all",
                "-f",
                "per_page=100",
                "-f",
                f"since={plan['created_at']}",
            ]
        )
    )
    marker = f"github-operations:fingerprint={plan['request']['fingerprint']}"
    issues = [issue for page in output for issue in page]
    return [issue["html_url"] for issue in issues if marker in (issue.get("body") or "")]


def _find_project_item(project: dict, owner: str, issue_url: str) -> dict | None:
    output = json.loads(
        run_gh(
            [
                "project",
                "item-list",
                str(project["number"]),
                "--owner",
                owner,
                "--limit",
                "10000",
                "--format",
                "json",
            ]
        )
    )
    matches = [item for item in output.get("items", []) if (item.get("content") or {}).get("url") == issue_url]
    if len(matches) > 1:
        raise SafetyError("multiple Project items reference the same Issue")
    return matches[0] if matches else None


def _verify_journal_issue(plan: dict, repository_name: str, issue_url: str) -> None:
    expected_prefix = f"https://github.com/{repository_name}/issues/"
    if not issue_url.startswith(expected_prefix):
        raise SafetyError("journal Issue URL is outside the planned repository")
    issue = json.loads(run_gh(["issue", "view", issue_url, "--json", "url,body"]))
    marker = f"github-operations:fingerprint={plan['request']['fingerprint']}"
    if issue.get("url") != issue_url or marker not in (issue.get("body") or ""):
        raise SafetyError("journal Issue does not match the planned fingerprint")


def _create_issue(plan: dict, config: dict, journal: dict) -> dict:
    request = plan["request"]
    observed = plan["observed"]
    if not journal.get("issue_url"):
        matches = _find_issue_by_fingerprint(plan, observed["repository"]["nameWithOwner"])
        if len(matches) > 1:
            raise SafetyError("multiple existing Issues have the operation fingerprint")
        if matches:
            journal["issue_url"] = matches[0]
            journal["steps"] = ["issue-created"]
            save_journal(plan["plan_id"], journal)
    if not journal.get("issue_url"):
        args = [
            "issue",
            "create",
            "--repo",
            observed["repository"]["nameWithOwner"],
            "--title",
            request["title"],
            "--body",
            request["body"],
        ]
        for label in request.get("labels", []):
            args.extend(("--label", label))
        if request.get("assignee"):
            args.extend(("--assignee", request["assignee"]))
        journal["issue_url"] = run_gh(args, retries=0).strip()
        journal["steps"] = ["issue-created"]
        save_journal(plan["plan_id"], journal)
    _verify_journal_issue(plan, observed["repository"]["nameWithOwner"], journal["issue_url"])
    project = observed["project"]
    output = _find_project_item(project, config["owner"], journal["issue_url"])
    if journal.get("item_id") and (output is None or journal["item_id"] != output["id"]):
        raise SafetyError("journal Project item does not reference the planned Issue")
    if output is None:
        if "project-item-added" in journal.get("steps", []):
            raise SafetyError("journal claims a Project item that GitHub does not contain")
        try:
            output = json.loads(
                run_gh(
                    [
                        "project",
                        "item-add",
                        str(project["number"]),
                        "--owner",
                        config["owner"],
                        "--url",
                        journal["issue_url"],
                        "--format",
                        "json",
                    ],
                    retries=0,
                )
            )
        except SafetyError:
            output = _find_project_item(project, config["owner"], journal["issue_url"])
            if output is None:
                raise
    journal["item_id"] = output["id"]
    if "project-item-added" not in journal.setdefault("steps", []):
        journal["steps"].append("project-item-added")
    save_journal(plan["plan_id"], journal)
    fields = project_fields(run_gh, config["owner"], int(observed["project"]["number"]))
    status = resolve_field(fields, config["project"].get("status_field", "Status"))
    inbox = resolve_option(status, config["project"].get("inbox_option", "Inbox"))
    _edit_item(observed["project"]["id"], journal["item_id"], status["id"], inbox["id"])
    if "status-set" not in journal["steps"]:
        journal["steps"].append("status-set")
    save_journal(plan["plan_id"], journal)
    if request.get("priority"):
        priority = resolve_field(fields, config["project"].get("priority_field", "Priority"))
        option = resolve_option(priority, request["priority"])
        _edit_item(observed["project"]["id"], journal["item_id"], priority["id"], option["id"])
        if "priority-set" not in journal["steps"]:
            journal["steps"].append("priority-set")
        save_journal(plan["plan_id"], journal)
    return journal


def _edit_item(project_id: str, item_id: str, field_id: str, option_id: str) -> None:
    run_gh(
        [
            "project",
            "item-edit",
            "--id",
            item_id,
            "--project-id",
            project_id,
            "--field-id",
            field_id,
            "--single-select-option-id",
            option_id,
        ],
        retries=0,
    )


def main(default_domain: str | None = None) -> int:
    argv = sys.argv[1:]
    if default_domain:
        if argv and argv[0] in {"project", "issue"} and argv[0] != default_domain:
            raise SystemExit(f"this launcher only supports the {default_domain} domain")
        if not argv or argv[0] not in {"project", "issue"}:
            argv.insert(0, default_domain)
    args = build_parser().parse_args(argv)
    try:
        cleanup_old_journals()
        if args.command == "unlock":
            if args.target != args.confirm_target:
                raise SafetyError("target confirmation mismatch")
            cleared = clear_stale_lock(args.target)
            print(json.dumps({"cleared": str(cleared)}, ensure_ascii=False, indent=2))
            return 0
        if args.command in {"inspect", "plan", "verify"}:
            path = find_config(args.config, Path.cwd())
            config = load_config(path)
            if args.command == "inspect":
                observed = observe_project(run_gh, config) if args.domain == "project" else {"config": str(path)}
                print(json.dumps(observed, ensure_ascii=False, indent=2))
                return 0
            if args.command == "verify":
                if args.domain == "project":
                    observed = observe_project(run_gh, config)
                    errors = project_verification_errors(observed, config)
                    result = {"verified": not errors, "errors": errors, "observed": observed}
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    return int(bool(errors))
                print(json.dumps({"verified": True, "config": str(path)}, ensure_ascii=False, indent=2))
                return 0
            plan = (
                make_project_plan(run_gh, path, config)
                if args.domain == "project"
                else make_issue_plan(run_gh, path, config, _issue_request(args))
            )
            save_plan(plan)
            print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
            return 0

        plan = load_plan(args.plan_id)
        if args.confirm_target != plan["target"]:
            raise SafetyError(f"target confirmation mismatch; expected {plan['target']!r}")
        _, config = _load_current(plan)
        _verify_identity(plan, config)
        journal = load_journal(plan["plan_id"])
        if not (plan["domain"] == "project" and args.command == "resume"):
            _verify_observed(plan, config)
        with exclusive_lock(plan["target"]):
            result = (
                _apply_project(plan, config, journal, allow_reconcile=args.command == "resume")
                if plan["domain"] == "project"
                else _create_issue(plan, config, journal)
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except SafetyError as exc:
        print(f"github-operations: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
