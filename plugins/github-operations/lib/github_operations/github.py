from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable
from typing import Any

from .models import Identity
from .safety import SafetyError, require_exactly_one

Runner = Callable[[list[str]], str]


def run_gh(args: list[str], *, retries: int = 2) -> str:
    command = ["gh", *args]
    environment = {**os.environ, "GH_HOST": "github.com"}
    for attempt in range(retries + 1):
        result = subprocess.run(command, text=True, capture_output=True, check=False, env=environment)
        if result.returncode == 0:
            return result.stdout
        transient = ("rate limit", "timeout", "temporar")
        if attempt < retries and any(marker in result.stderr.lower() for marker in transient):
            time.sleep(2**attempt)
            continue
        raise SafetyError(f"gh command failed: {' '.join(command)}\n{result.stderr.strip()}")
    raise AssertionError("unreachable")


def json_gh(runner: Runner, args: list[str]) -> Any:
    try:
        return json.loads(runner(args))
    except json.JSONDecodeError as exc:
        raise SafetyError(f"gh returned invalid JSON for: {' '.join(args)}") from exc


def identity(runner: Runner, host: str) -> Identity:
    user = json_gh(runner, ["api", f"--hostname={host}", "user"])
    return Identity(host=host, login=user["login"], node_id=user["node_id"])


def organization_preflight(runner: Runner, owner: str, host: str) -> dict[str, Any]:
    auth_document = json_gh(runner, ["auth", "status", "--active", "--hostname", host, "--json", "hosts"])
    accounts = auth_document.get("hosts", {}).get(host, [])
    active = [account for account in accounts if account.get("active")]
    auth = require_exactly_one(active, f"active account for {host}")
    organization = json_gh(runner, ["api", f"--hostname={host}", f"orgs/{owner}"])
    query = """
    query($login: String!) {
      organization(login: $login) { id login viewerCanCreateProjects }
    }
    """
    permission = json_gh(
        runner,
        ["api", "graphql", "-f", f"query={query}", "-F", f"login={owner}"],
    ).get("data", {}).get("organization")
    if not permission:
        raise SafetyError(f"Organization does not exist or is not visible: {owner}")
    return {
        "auth": {key: auth.get(key) for key in ("host", "login", "state", "scopes")},
        "organization": permission,
        "plan": organization.get("plan", {}).get("name", "unknown"),
    }


def project_list(runner: Runner, owner: str) -> list[dict[str, Any]]:
    data = json_gh(runner, ["project", "list", "--owner", owner, "--limit", "1000", "--format", "json"])
    projects = data.get("projects", data if isinstance(data, list) else [])
    return [{key: item.get(key) for key in ("id", "number", "title", "url")} for item in projects]


def resolve_project(runner: Runner, owner: str, title: str) -> dict[str, Any] | None:
    matches = [item for item in project_list(runner, owner) if item.get("title") == title]
    if len(matches) > 1:
        raise SafetyError(f"multiple projects named {title!r} exist under {owner}")
    return matches[0] if matches else None


def require_project(runner: Runner, owner: str, title: str) -> dict[str, Any]:
    project = resolve_project(runner, owner, title)
    if project is None:
        raise SafetyError(f"project {title!r} does not exist under {owner}")
    return project


def project_fields(runner: Runner, owner: str, number: int) -> list[dict[str, Any]]:
    data = json_gh(
        runner,
        ["project", "field-list", str(number), "--owner", owner, "--limit", "1000", "--format", "json"],
    )
    fields = data.get("fields", data if isinstance(data, list) else [])
    return [
        {
            "id": field.get("id"),
            "name": field.get("name"),
            "type": field.get("type"),
            "options": [
                {"id": option.get("id"), "name": option.get("name")} for option in field.get("options", [])
            ],
        }
        for field in fields
    ]


def resolve_field(fields: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return require_exactly_one([field for field in fields if field.get("name") == name], f"field named {name!r}")


def resolve_option(field: dict[str, Any], name: str) -> dict[str, Any]:
    options = field.get("options", [])
    return require_exactly_one([option for option in options if option.get("name") == name], f"option named {name!r}")


def repository(runner: Runner, full_name: str) -> dict[str, Any]:
    return json_gh(runner, ["repo", "view", full_name, "--json", "id,nameWithOwner,url"])


def repository_labels(runner: Runner, full_name: str) -> list[str]:
    data = json_gh(runner, ["label", "list", "--repo", full_name, "--limit", "1000", "--json", "name"])
    return [item["name"] for item in data]


def project_structure(runner: Runner, project_id: str) -> dict[str, Any]:
    query = """
    query($id: ID!) {
      node(id: $id) {
        ... on ProjectV2 {
          repositories(first: 100) { nodes { nameWithOwner } pageInfo { hasNextPage endCursor } }
          views(first: 100) {
            nodes {
              name layout filter
              fields(first: 100) { nodes { ... on ProjectV2FieldCommon { name } } }
              groupByFields(first: 20) { nodes { ... on ProjectV2FieldCommon { name } } }
              verticalGroupByFields(first: 20) { nodes { ... on ProjectV2FieldCommon { name } } }
            }
            pageInfo { hasNextPage }
          }
          workflows(first: 100) { nodes { name enabled } pageInfo { hasNextPage } }
        }
      }
    }
    """
    data = json_gh(runner, ["api", "graphql", "-f", f"query={query}", "-F", f"id={project_id}"])
    node = data.get("data", {}).get("node")
    if not node:
        raise SafetyError(f"could not read Project structure for {project_id}")
    repositories = [item["nameWithOwner"] for item in node["repositories"]["nodes"]]
    page_info = node["repositories"]["pageInfo"]
    while page_info["hasNextPage"]:
        page_query = """
        query($id: ID!, $cursor: String!) {
          node(id: $id) {
            ... on ProjectV2 {
              repositories(first: 100, after: $cursor) {
                nodes { nameWithOwner }
                pageInfo { hasNextPage endCursor }
              }
            }
          }
        }
        """
        page = json_gh(
            runner,
            [
                "api",
                "graphql",
                "-f",
                f"query={page_query}",
                "-F",
                f"id={project_id}",
                "-F",
                f"cursor={page_info['endCursor']}",
            ],
        )["data"]["node"]["repositories"]
        repositories.extend(item["nameWithOwner"] for item in page["nodes"])
        page_info = page["pageInfo"]
    for connection in ("views", "workflows"):
        if node[connection]["pageInfo"]["hasNextPage"]:
            raise SafetyError(f"Project has more than 100 {connection}; complete verification is not supported")
    return {
        "repositories": sorted(repositories),
        "views": node["views"]["nodes"],
        "workflows": node["workflows"]["nodes"],
    }
