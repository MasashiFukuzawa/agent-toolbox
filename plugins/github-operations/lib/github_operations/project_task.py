from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .github import Runner, json_gh
from .safety import SafetyError


def _issue_identity(repo: str, content: dict[str, Any]) -> tuple[int, str]:
    url = content.get("url")
    number = content.get("number")
    if not isinstance(url, str) or not isinstance(number, int):
        raise SafetyError("Project item needs an Issue URL and numeric Issue number")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise SafetyError(f"Project item URL must use https://github.com: {url}")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 4 or parts[2] != "issues" or not parts[3].isdigit():
        raise SafetyError(f"Project item URL is not a canonical Issue URL: {url}")
    item_repo = "/".join(parts[:2])
    if item_repo.casefold() != repo.casefold() or int(parts[3]) != number:
        raise SafetyError(
            f"Project item belongs to {item_repo}#{parts[3]}, not configured {repo}#{number}; "
            "refusing every write"
        )
    return number, url


def _project_state(runner: Runner, owner: str, project_number: int) -> tuple[dict, dict, list[dict]]:
    number = str(project_number)
    project = json_gh(runner, ["project", "view", number, "--owner", owner, "--format", "json"])
    fields = json_gh(
        runner, ["project", "field-list", number, "--owner", owner, "--format", "json"]
    )
    items = json_gh(
        runner,
        ["project", "item-list", number, "--owner", owner, "--limit", "10000", "--format", "json"],
    ).get("items", [])
    return project, fields, items


def _status_option(fields: dict, status: str) -> tuple[str, str]:
    field = next((item for item in fields.get("fields", []) if item.get("name") == "Status"), None)
    if field is None:
        raise SafetyError("Project has no Status field")
    option = next((item for item in field.get("options", []) if item.get("name") == status), None)
    if option is None:
        raise SafetyError(f"Project Status has no option {status!r}")
    return field["id"], option["id"]


def claim_project_task(
    runner: Runner,
    *,
    repo: str,
    owner: str,
    project_number: int,
    item_id: str,
    issue_url: str,
    issue_number: int,
    expected_status: str,
    in_progress: str,
) -> dict[str, Any]:
    """Revalidate a candidate, self-assign it, then move it to In Progress."""
    project, fields, items = _project_state(runner, owner, project_number)
    picked = next((item for item in items if item.get("id") == item_id), None)
    if picked is None:
        raise SafetyError(f"Project item {item_id} no longer exists; select and inspect a new candidate")
    number, url = _issue_identity(repo, picked.get("content") or {})
    if url != issue_url or number != issue_number:
        raise SafetyError(f"Project item {item_id} changed after collaboration preflight")
    if picked.get("status") != expected_status:
        raise SafetyError(
            f"Project item {item_id} is now {picked.get('status')!r}, not expected "
            f"{expected_status!r}; select and inspect a new candidate"
        )
    field_id, option_id = _status_option(fields, in_progress)
    runner(["issue", "edit", str(issue_number), "--repo", repo, "--add-assignee", "@me"])
    try:
        runner(
            [
                "project", "item-edit", "--project-id", project["id"], "--id", item_id,
                "--field-id", field_id, "--single-select-option-id", option_id,
            ]
        )
    except SafetyError as exc:
        _project, _fields, current_items = _project_state(runner, owner, project_number)
        current = next((item for item in current_items if item.get("id") == item_id), None)
        current_status = current.get("status") if current else None
        if current_status == in_progress:
            return {
                "itemId": item_id,
                "issueUrl": issue_url,
                "status": in_progress,
                "reconciled": True,
            }
        raise SafetyError(
            f"partial claim for {issue_url}: self-assignment succeeded but Project item {item_id} "
            f"is observed as {current_status!r}, not {in_progress!r}; stop implementation and retry "
            f"this exact claim only if it remains {expected_status!r} ({exc})"
        ) from exc
    return {"itemId": item_id, "issueUrl": issue_url, "status": in_progress}
