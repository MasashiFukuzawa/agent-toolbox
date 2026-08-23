from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .github import (
    create_project,
    create_project_view,
    create_single_select_field,
    project_fields,
    project_structure,
    repository,
    repository_labels,
    require_project,
    resolve_field,
    resolve_option,
    resolve_project,
    run_gh,
    update_project,
    update_project_view,
    update_single_select_field,
)
from .planning import (
    find_config,
    load_config,
    load_issue_manifest,
    make_issue_manifest_plan,
    make_issue_plan,
    make_project_plan,
    observe_issue,
    observe_project,
    project_verification_errors,
)
from .safety import PartialApplyError, SafetyError, digest
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
    issue_plan.add_argument("--manifest")

    resume = subparsers.add_parser("resume")
    resume.add_argument("--plan-id", required=True)
    resume.add_argument("--confirm-target", required=True)
    unlock = subparsers.add_parser("unlock")
    unlock.add_argument("--target", required=True)
    unlock.add_argument("--confirm-target", required=True)
    return parser


def _issue_request(args: argparse.Namespace) -> dict:
    if args.manifest:
        if any((args.repo, args.title, args.body, args.body_file, args.label, args.assignee, args.priority)):
            raise SafetyError("--manifest cannot be combined with single-Issue options")
        return {"manifest_path": args.manifest}
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
    if plan["domain"] == "issue" and isinstance(plan.get("request", {}).get("issues"), list):
        project = require_project(run_gh, config["owner"], config["project"]["title"])
        if project["id"] != plan["observed"]["project"]["id"]:
            raise SafetyError("target Project identity changed after planning")
        fields = project_fields(run_gh, config["owner"], int(project["number"]))
        status = resolve_field(fields, config["project"].get("status_field", "Status"))
        inbox = resolve_option(status, config["project"].get("inbox_option", "Inbox"))
        expected = plan["observed"]["status"]
        if (status["id"], inbox["id"], inbox["name"]) != (
            expected["field"]["id"],
            expected["option"]["id"],
            expected["option"]["name"],
        ):
            raise SafetyError("Status field or option changed after planning")
        priorities = {request.get("priority") for request in plan["request"]["issues"] if request.get("priority")}
        if priorities:
            priority = resolve_field(fields, config["project"].get("priority_field", "Priority"))
            expected_priority = plan["observed"].get("priority_field")
            if not expected_priority or priority["id"] != expected_priority["id"]:
                raise SafetyError("Priority field changed after planning")
            for name in priorities:
                current = resolve_option(priority, name)
                previous = resolve_option(expected_priority, name)
                if (current["id"], current["name"]) != (previous["id"], previous["name"]):
                    raise SafetyError(f"Priority option changed after planning: {name}")
        requests_by_repo: dict[str, set[str]] = {}
        for request in plan["request"]["issues"]:
            requests_by_repo.setdefault(request["repo"], set()).update(request.get("labels", []))
        for repo_name, selected in requests_by_repo.items():
            current_repo = repository(run_gh, repo_name)
            expected_repo = plan["observed"]["repositories"][repo_name]["repository"]
            if current_repo["id"] != expected_repo["id"]:
                raise SafetyError(f"repository identity changed after planning: {repo_name}")
            missing = selected - set(repository_labels(run_gh, repo_name))
            if missing:
                raise SafetyError(f"labels no longer exist in {repo_name}: {', '.join(sorted(missing))}")
        return
    current = (
        observe_project(run_gh, config)
        if plan["domain"] == "project"
        else observe_issue(run_gh, config, plan["request"])
    )
    if digest(current) != plan["observed_digest"]:
        raise SafetyError("GitHub state changed after planning; create and approve a new plan")


def _option_specs(expected: list, existing: list[dict] | None = None) -> list[dict[str, str]]:
    existing_by_name = {item.get("name"): item for item in (existing or [])}
    colors = ["GRAY", "GREEN", "YELLOW", "ORANGE", "PURPLE"]
    specs = []
    for index, value in enumerate(expected):
        if isinstance(value, str):
            spec = {"name": value, "description": "", "color": colors[min(index, len(colors) - 1)]}
        elif isinstance(value, dict) and isinstance(value.get("name"), str) and value["name"]:
            spec = {
                "name": value["name"],
                "description": str(value.get("description", "")),
                "color": str(value.get("color", colors[min(index, len(colors) - 1)])).upper(),
            }
        else:
            raise SafetyError("single-select options must be strings or objects with a non-empty name")
        previous = existing_by_name.get(spec["name"])
        if previous and previous.get("id"):
            spec["id"] = previous["id"]
        specs.append(spec)
    return specs


def _ensure_single_select_field(owner: str, project: dict, name: str, expected: list) -> None:
    fields = project_fields(run_gh, owner, int(project["number"]))
    field = next((item for item in fields if item.get("name") == name), None)
    if field is None and name == "Status":
        raise SafetyError("new Projects must expose GitHub's built-in Status field")
    specs = _option_specs(expected, field.get("options", []) if field else None)
    actual_names = [item.get("name") for item in field.get("options", [])] if field else []
    expected_names = [item["name"] for item in specs]
    if field is None:
        create_single_select_field(run_gh, project["id"], name, specs)
    elif actual_names != expected_names:
        update_single_select_field(run_gh, field["id"], name, specs)


def _view_field_ids(owner: str, project: dict, view: dict) -> list[str]:
    fields = {field["name"]: field["id"] for field in project_fields(run_gh, owner, int(project["number"]))}
    missing = [name for name in view.get("fields", []) if name not in fields]
    if missing:
        raise SafetyError(f"view {view.get('name')!r} references unknown fields: {', '.join(missing)}")
    return [fields[name] for name in view.get("fields", [])]


def _ensure_view(owner: str, project: dict, structure: dict, view: dict) -> None:
    name = view.get("name")
    layout = view.get("layout")
    if not isinstance(name, str) or not name or layout not in {"BOARD_LAYOUT", "TABLE_LAYOUT", "ROADMAP_LAYOUT"}:
        raise SafetyError("view requires a name and a supported ProjectV2 layout")
    field_ids = _view_field_ids(owner, project, view)
    existing = next((item for item in structure.get("views", []) if item.get("name") == name), None)
    if existing:
        update_project_view(
            run_gh,
            existing["id"],
            name=name,
            layout=layout,
            visible_field_ids=field_ids,
            filter_value=view.get("filter", ""),
        )
    else:
        created = create_project_view(run_gh, project["id"], name, layout, field_ids)
        if view.get("filter", ""):
            update_project_view(
                run_gh,
                created["id"],
                name=name,
                layout=layout,
                visible_field_ids=field_ids,
                filter_value=view["filter"],
            )


def _apply_project(plan: dict, config: dict, journal: dict, *, allow_reconcile: bool) -> dict:
    owner = config["owner"]
    project_cfg = config["project"]
    template = plan["observed"]["template"]
    planned_project = plan["observed"]["existing"]
    bootstrap = template is None and planned_project is None
    if plan["observed"].get("drift") and not bootstrap:
        raise SafetyError("Project contract drift requires manual remediation; apply was not attempted")
    recovery_steps = {"copy-attempted", "project-copied", "create-attempted", "project-created"} & set(
        journal.get("steps", [])
    )
    if allow_reconcile and planned_project is None and not recovery_steps:
        action = "creation" if bootstrap else "copy"
        raise SafetyError(f"Project resume requires a journal proving that this plan attempted the {action}")
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
        attempt_step = "create-attempted" if bootstrap else "copy-attempted"
        if attempt_step not in journal["steps"]:
            journal["steps"].append(attempt_step)
            save_journal(plan["plan_id"], journal)
        try:
            if bootstrap:
                default_repository = config.get("default_repository")
                repository_id = next(
                    (
                        repository["id"]
                        for repository in plan["observed"].get("repositories", [])
                        if repository["nameWithOwner"] == f"{owner}/{default_repository}"
                    ),
                    None,
                )
                project = create_project(
                    run_gh,
                    plan["observed"]["preflight"]["organization"]["id"],
                    project_cfg["title"],
                    repository_id,
                )
                visibility = project_cfg.get("visibility", "PRIVATE")
                update_project(
                    run_gh,
                    project["id"],
                    public=visibility == "PUBLIC",
                    short_description=project_cfg.get("short_description"),
                    readme=project_cfg.get("readme"),
                )
            else:
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
            if project is None:
                project = require_project(run_gh, owner, project_cfg["title"])
        journal["project_id"] = project["id"]
        journal["project_number"] = project["number"]
        journal.setdefault("steps", [])
        journal["steps"].append("project-created" if bootstrap else "project-copied")
        save_journal(plan["plan_id"], journal)
    journal["project_id"] = project["id"]
    journal["project_number"] = project["number"]
    journal.setdefault("steps", [])
    save_journal(plan["plan_id"], journal)

    if bootstrap:
        contract = project_cfg.get("contract", {})
        status_options = contract.get("statuses", [])
        if status_options:
            _ensure_single_select_field(owner, project, project_cfg.get("status_field", "Status"), status_options)
        priority_options = contract.get("priorities", [])
        if priority_options:
            _ensure_single_select_field(owner, project, project_cfg.get("priority_field", "Priority"), priority_options)
        structure = project_structure(run_gh, project["id"])
        for view in contract.get("views", []):
            _ensure_view(owner, project, structure, view)

    linked = set(project_structure(run_gh, project["id"])["repositories"])
    for repo in config.get("repositories", []):
        full_name = f"{owner}/{repo}"
        if full_name not in linked:
            try:
                run_gh(["project", "link", str(project["number"]), "--owner", owner, "--repo", full_name], retries=0)
            except SafetyError:
                linked = set(project_structure(run_gh, project["id"])["repositories"])
                if full_name not in linked:
                    raise
            journal["steps"].append(f"repository-linked:{full_name}")
            save_journal(plan["plan_id"], journal)
    current = (
        observe_project(run_gh, config) if not bootstrap else observe_project(run_gh, config, include_browser=False)
    )
    verification_errors = (
        project_verification_errors(current, config)
        if not bootstrap
        else project_verification_errors(current, config, include_browser=False)
    )
    if verification_errors:
        raise SafetyError("post-apply verification failed: " + "; ".join(verification_errors))
    journal["steps"].append("verified")
    save_journal(plan["plan_id"], journal)
    return {
        "project": current["existing"],
        "verified": True,
        "browser_required": bool(
            config.get("auto_add")
            or (
                bootstrap
                and (
                    current["drift"]
                    or config["project"].get("contract", {}).get("workflows")
                    or any(
                        view.get("group_by") or view.get("vertical_group_by")
                        for view in config["project"].get("contract", {}).get("views", [])
                    )
                )
            )
        ),
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


def _find_project_item_for_issue(project_id: str, issue_url: str) -> dict | None:
    issue = json.loads(run_gh(["issue", "view", issue_url, "--json", "id,url"]))
    query = """
    query($id: ID!) {
      node(id: $id) {
        ... on Issue {
          projectItems(first: 100) { nodes { id project { id } } pageInfo { hasNextPage } }
        }
      }
    }
    """
    document = json.loads(run_gh(["api", "graphql", "-f", f"query={query}", "-F", f"id={issue['id']}"]))
    errors = document.get("errors")
    if errors:
        raise SafetyError("GitHub GraphQL Issue Project lookup failed: " + "; ".join(str(error) for error in errors))
    connection = document.get("data", {}).get("node", {}).get("projectItems")
    if not connection:
        raise SafetyError("GitHub did not return Issue Project items")
    if connection.get("pageInfo", {}).get("hasNextPage"):
        raise SafetyError("Issue belongs to more than 100 Project items; safe reconciliation is unsupported")
    matches = [item for item in connection.get("nodes", []) if item.get("project", {}).get("id") == project_id]
    if len(matches) > 1:
        raise SafetyError("multiple Project items reference the same Issue")
    return matches[0] if matches else None


def _batch_result(plan: dict, journal: dict) -> dict:
    entries = journal.get("entries", {})
    return {
        "plan_id": plan["plan_id"],
        "target": plan["target"],
        "completed": sum(value.get("state") == "verified" for value in entries.values()),
        "total": len(plan["request"]["issues"]),
        "entries": entries,
    }


def _apply_issue_manifest(plan: dict, config: dict, journal: dict) -> dict:
    from datetime import UTC, datetime

    journal.setdefault("entries", {})
    journal.setdefault("started_at", datetime.now(UTC).isoformat())
    save_journal(plan["plan_id"], journal)
    observed = plan["observed"]
    project = observed["project"]
    status = observed["status"]
    priority_field = observed.get("priority_field")
    try:
        for request in plan["request"]["issues"]:
            key = request["key"]
            entry = journal["entries"].setdefault(key, {"state": "pending"})
            if entry.get("state") == "verified":
                continue
            repo_name = request["repo"]
            recovered_issue = False
            if not entry.get("issue_url"):
                matches = _find_issue_by_fingerprint({"created_at": plan["created_at"], "request": request}, repo_name)
                if len(matches) > 1:
                    raise SafetyError(f"entry {key}: multiple existing Issues have the operation fingerprint")
                if matches:
                    entry["issue_url"] = matches[0]
                    recovered_issue = True
                else:
                    entry.update(state="issue-create-attempted")
                    save_journal(plan["plan_id"], journal)
                    args = [
                        "issue",
                        "create",
                        "--repo",
                        repo_name,
                        "--title",
                        request["title"],
                        "--body",
                        request["body"],
                    ]
                    for label in request.get("labels", []):
                        args.extend(("--label", label))
                    if request.get("assignee"):
                        args.extend(("--assignee", request["assignee"]))
                    entry["issue_url"] = run_gh(args, retries=0).strip()
                entry["state"] = "issue-created"
                save_journal(plan["plan_id"], journal)
            _verify_journal_issue({"request": request}, repo_name, entry["issue_url"])
            saved_item_id = entry.get("item_id")
            if saved_item_id:
                current_item = _find_project_item_for_issue(project["id"], entry["issue_url"])
                if current_item is None or current_item["id"] != saved_item_id:
                    raise SafetyError(f"entry {key}: journal Project item does not match the planned Issue")
            if not entry.get("item_id"):
                reconcile_item = recovered_issue or entry.get("state") == "project-item-add-attempted"
                existing = (
                    _find_project_item_for_issue(project["id"], entry["issue_url"]) if reconcile_item else None
                )
                if existing:
                    entry["item_id"] = existing["id"]
                else:
                    entry["state"] = "project-item-add-attempted"
                    save_journal(plan["plan_id"], journal)
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
                                    entry["issue_url"],
                                    "--format",
                                    "json",
                                ],
                                retries=0,
                            )
                        )
                    except SafetyError:
                        output = _find_project_item_for_issue(project["id"], entry["issue_url"])
                        if output is None:
                            raise
                    entry["item_id"] = output["id"]
                entry["state"] = "project-item-added"
                save_journal(plan["plan_id"], journal)
            _edit_item(project["id"], entry["item_id"], status["field"]["id"], status["option"]["id"])
            entry["state"] = "status-set"
            save_journal(plan["plan_id"], journal)
            if request.get("priority"):
                if not priority_field:
                    raise SafetyError("Priority field was not found")
                option = resolve_option(priority_field, request["priority"])
                _edit_item(project["id"], entry["item_id"], priority_field["id"], option["id"])
                entry["state"] = "priority-set"
                save_journal(plan["plan_id"], journal)
            entry["state"] = "verified"
            save_journal(plan["plan_id"], journal)
    except SafetyError as exc:
        result = _batch_result(plan, journal)
        if result["completed"] or any(value.get("state") != "pending" for value in journal["entries"].values()):
            raise PartialApplyError(str(exc), result) from exc
        raise
    return _batch_result(plan, journal)


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
            if args.domain == "project":
                plan = make_project_plan(run_gh, path, config)
            else:
                request = _issue_request(args)
                plan = (
                    make_issue_manifest_plan(run_gh, path, config, load_issue_manifest(Path(request["manifest_path"])))
                    if "manifest_path" in request
                    else make_issue_plan(run_gh, path, config, request)
                )
            save_plan(plan)
            print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
            return 0

        journal = load_journal(args.plan_id)
        mutation_started = bool(journal.get("entries")) or bool(journal.get("steps"))
        plan = load_plan(args.plan_id, allow_expired=args.command == "resume" and mutation_started)
        if args.confirm_target != plan["target"]:
            raise SafetyError(f"target confirmation mismatch; expected {plan['target']!r}")
        _, config = _load_current(plan)
        _verify_identity(plan, config)
        with exclusive_lock(plan["target"]):
            if not (plan["domain"] == "project" and args.command == "resume"):
                _verify_observed(plan, config)
            result = (
                _apply_project(plan, config, journal, allow_reconcile=args.command == "resume")
                if plan["domain"] == "project"
                else (
                    _apply_issue_manifest(plan, config, journal)
                    if isinstance(plan.get("request", {}).get("issues"), list)
                    else _create_issue(plan, config, journal)
                )
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except PartialApplyError as exc:
        print(json.dumps(exc.result, ensure_ascii=False, indent=2))
        print(f"github-operations: partial apply: {exc}", file=sys.stderr)
        return 1
    except SafetyError as exc:
        print(f"github-operations: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
