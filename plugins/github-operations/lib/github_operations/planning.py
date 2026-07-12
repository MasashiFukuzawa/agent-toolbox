from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .github import (
    Runner,
    identity,
    organization_preflight,
    project_fields,
    project_structure,
    repository,
    repository_labels,
    resolve_field,
    resolve_option,
    resolve_project,
)
from .models import Plan
from .safety import SafetyError, digest


def find_config(explicit: str | None, cwd: Path) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not path.is_file():
            raise SafetyError(f"config does not exist: {path}")
        return path
    root = _git_root(cwd)
    path = root / ".agents/github-operations.json"
    if not path.is_file():
        raise SafetyError("no config found; pass --config or create .agents/github-operations.json at the git root")
    return path


def _git_root(cwd: Path) -> Path:
    import subprocess

    result = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], text=True, capture_output=True)
    if result.returncode:
        raise SafetyError("current directory is not inside a git repository; pass --config explicitly")
    return Path(result.stdout.strip()).resolve()


def load_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError(f"invalid config: {path}") from exc
    required = {"version", "owner", "project"}
    if not required <= set(config) or config["version"] != 1:
        raise SafetyError("config requires version=1, owner, and project")
    if config.get("host", "github.com") != "github.com":
        raise SafetyError("version 1 supports github.com only; GitHub Enterprise hosts are not yet supported")
    if not isinstance(config["owner"], str) or not config["owner"]:
        raise SafetyError("config owner must be a non-empty string")
    if not isinstance(config["project"], dict) or not config["project"].get("title"):
        raise SafetyError("config project.title must be a non-empty string")
    repositories = config.get("repositories", [])
    if not isinstance(repositories, list) or not all(isinstance(item, str) and item for item in repositories):
        raise SafetyError("config repositories must be a list of non-empty names")
    default_repository = config.get("default_repository")
    if default_repository is not None and default_repository not in repositories:
        raise SafetyError("config default_repository must be included in repositories")
    if config.get("auto_add", {}).get("default_repository_only") and not default_repository:
        raise SafetyError("auto_add.default_repository_only requires default_repository")
    return config


def _new_plan(
    domain: str,
    identity_value: dict,
    target: str,
    path: Path,
    config: dict,
    observed: dict,
    request: dict,
    operations: list[dict],
) -> Plan:
    now = datetime.now(UTC)
    plan = Plan(
        schema_version=1,
        plan_id="",
        domain=domain,
        action="apply",
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=24)).isoformat(),
        identity=identity_value,
        target=target,
        config_path=str(path),
        config_digest=digest(config),
        observed_digest=digest(observed),
        observed=observed,
        request=request,
        operations=operations,
    )
    content = plan.to_dict()
    content.pop("plan_id")
    plan.plan_id = digest(content)[:32]
    return plan


def observe_project(runner: Runner, config: dict) -> dict[str, Any]:
    owner = config["owner"]
    project_cfg = config["project"]
    template_cfg = project_cfg.get("template")
    if not isinstance(template_cfg, dict) or not template_cfg.get("owner") or not template_cfg.get("title"):
        raise SafetyError("Project operations require project.template.owner and project.template.title")
    template = resolve_project(runner, template_cfg["owner"], template_cfg["title"])
    if template is None:
        raise SafetyError("template project was not found")
    existing = resolve_project(runner, owner, project_cfg["title"])
    repos = [repository(runner, f"{owner}/{name}") for name in config.get("repositories", [])]
    contract_project = existing or template
    fields = project_fields(runner, existing and owner or template_cfg["owner"], int(contract_project["number"]))
    structure = project_structure(runner, contract_project["id"])
    drift = contract_drift(project_cfg.get("contract", {}), fields, structure)
    preflight = organization_preflight(runner, owner, config.get("host", "github.com"))
    if not preflight["organization"]["viewerCanCreateProjects"] and existing is None:
        raise SafetyError(f"authenticated user cannot create Projects under {owner}")
    return {
        "preflight": preflight,
        "template": template,
        "existing": existing,
        "repositories": repos,
        "structure": structure,
        "drift": drift,
    }


def contract_drift(contract: dict, fields: list[dict[str, Any]], structure: dict[str, Any]) -> list[str]:
    drift: list[str] = []
    fields_by_name = {field["name"]: field for field in fields}
    for key, default_field in (("statuses", "Status"), ("priorities", "Priority")):
        expected = contract.get(key)
        if not expected:
            continue
        field = fields_by_name.get(default_field)
        actual = [option["name"] for option in field.get("options", [])] if field else []
        if actual != expected:
            drift.append(f"{default_field} options differ: expected={expected!r} actual={actual!r}")
    expected_views = contract.get("views")
    if expected_views:
        actual_by_name = {view["name"]: view for view in structure["views"]}
        for expected in expected_views:
            expected = {"name": expected} if isinstance(expected, str) else expected
            actual = actual_by_name.get(expected["name"])
            if not actual:
                drift.append(f"view is missing: {expected['name']!r}")
                continue
            comparisons = {
                "layout": actual.get("layout"),
                "filter": actual.get("filter"),
                "fields": [item.get("name") for item in actual.get("fields", {}).get("nodes", [])],
                "group_by": [item.get("name") for item in actual.get("groupByFields", {}).get("nodes", [])],
                "vertical_group_by": [
                    item.get("name") for item in actual.get("verticalGroupByFields", {}).get("nodes", [])
                ],
            }
            for key, expected_value in expected.items():
                if key != "name" and comparisons.get(key) != expected_value:
                    drift.append(
                        f"view {expected['name']!r} {key} differs: "
                        f"expected={expected_value!r} actual={comparisons.get(key)!r}"
                    )
    expected_workflows = contract.get("workflows")
    if expected_workflows:
        actual_workflows = {workflow["name"]: workflow["enabled"] for workflow in structure["workflows"]}
        for expected in expected_workflows:
            expected = {"name": expected, "enabled": True} if isinstance(expected, str) else expected
            if actual_workflows.get(expected["name"]) != expected.get("enabled", True):
                drift.append(
                    f"workflow {expected['name']!r} differs: expected enabled={expected.get('enabled', True)!r} "
                    f"actual={actual_workflows.get(expected['name'])!r}"
                )
    return drift


def project_verification_errors(observed: dict[str, Any], config: dict) -> list[str]:
    errors = list(observed.get("drift", []))
    if observed.get("existing") is None:
        errors.append("target Project does not exist")
    linked = set(observed.get("structure", {}).get("repositories", []))
    expected = {f"{config['owner']}/{name}" for name in config.get("repositories", [])}
    for missing in sorted(expected - linked):
        errors.append(f"repository is not linked: {missing}")
    return errors


def make_project_plan(runner: Runner, path: Path, config: dict) -> Plan:
    host = config.get("host", "github.com")
    actor = identity(runner, host)
    observed = observe_project(runner, config)
    project_cfg = config["project"]
    operations: list[dict[str, Any]] = []
    if observed["existing"] is None and observed["drift"]:
        raise SafetyError("template does not satisfy the requested contract: " + "; ".join(observed["drift"]))
    if observed["existing"] is None:
        operations.append({"type": "copy-project", "source": observed["template"], "title": project_cfg["title"]})
    linked = set(observed["structure"]["repositories"]) if observed["existing"] else set()
    for repo in observed["repositories"]:
        if repo["nameWithOwner"] not in linked:
            operations.append({"type": "ensure-repository-link", "repository": repo["nameWithOwner"]})
    operations.append(
        {"type": "verify-contract", "contract": project_cfg.get("contract", {}), "drift": observed["drift"]}
    )
    if config.get("auto_add"):
        plan_name = str(observed["preflight"]["plan"]).lower()
        available = 20 if "enterprise" in plan_name else 5 if plan_name in {"team", "pro"} else 1
        required = len(config.get("repositories", []))
        operations.append(
            {
                "type": "browser-required-auto-add",
                "config": config["auto_add"],
                "available_workflows": available,
                "required_workflows": required,
                "recommendation": (
                    "configure the default repository only and use explicit Project registration for the others"
                    if required > available
                    else "configure one workflow per requested repository"
                ),
            }
        )
    return _new_plan(
        "project",
        actor.__dict__,
        f"{config['owner']}/{project_cfg['title']}",
        path,
        config,
        observed,
        {},
        operations,
    )


def observe_issue(runner: Runner, config: dict, request: dict) -> dict[str, Any]:
    owner = config["owner"]
    repo_name = request["repo"]
    if "/" not in repo_name:
        repo_name = f"{owner}/{repo_name}"
    repo_owner, short_name = repo_name.split("/", 1)
    allowed = config.get("repositories", [])
    if repo_owner != owner or not allowed or short_name not in allowed:
        raise SafetyError(f"repository is outside the configured owner/allowlist: {repo_name}")
    repo = repository(runner, repo_name)
    available_labels = repository_labels(runner, repo_name)
    missing_labels = sorted(set(request.get("labels", [])) - set(available_labels))
    if missing_labels:
        raise SafetyError(f"labels do not exist in {repo_name}: {', '.join(missing_labels)}")
    project = resolve_project(runner, owner, config["project"]["title"])
    if project is None:
        raise SafetyError("target project was not found")
    fields = project_fields(runner, owner, int(project["number"]))
    status_name = config["project"].get("status_field", "Status")
    status_value = config["project"].get("inbox_option", "Inbox")
    status = resolve_field(fields, status_name)
    inbox = resolve_option(status, status_value)
    priority = None
    if request.get("priority"):
        priority_field = resolve_field(fields, config["project"].get("priority_field", "Priority"))
        priority = {"field": priority_field, "option": resolve_option(priority_field, request["priority"])}
    return {
        "repository": repo,
        "selected_labels": request.get("labels", []),
        "project": project,
        "status": {"field": status, "option": inbox},
        "priority": priority,
    }


def make_issue_plan(runner: Runner, path: Path, config: dict, request: dict) -> Plan:
    request = dict(request)
    fingerprint = request.get("fingerprint") or digest(
        {"owner": config["owner"], "repo": request["repo"], "title": request["title"], "body": request["body"]}
    )[:24]
    marker = f"<!-- github-operations:fingerprint={fingerprint} -->"
    if marker not in request["body"]:
        request["body"] = f"{request['body'].rstrip()}\n\n{marker}\n"
    request["fingerprint"] = fingerprint
    actor = identity(runner, config.get("host", "github.com"))
    observed = observe_issue(runner, config, request)
    operations = [
        {"type": "create-issue", "repository": observed["repository"]["nameWithOwner"], "title": request["title"]},
        {"type": "add-project-item", "project": config["project"]["title"]},
        {"type": "set-status", "value": config["project"].get("inbox_option", "Inbox")},
    ]
    if request.get("priority"):
        operations.append({"type": "set-priority", "value": request["priority"]})
    return _new_plan(
        "issue",
        actor.__dict__,
        observed["repository"]["nameWithOwner"],
        path,
        config,
        observed,
        request,
        operations,
    )
