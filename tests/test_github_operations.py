from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/github-operations"
LIB = PLUGIN / "lib"
sys.path.insert(0, str(LIB))

from github_operations import cli  # noqa: E402
from github_operations.planning import (  # noqa: E402
    load_config,
    make_issue_plan,
    make_project_plan,
    project_verification_errors,
)
from github_operations.safety import SafetyError  # noqa: E402
from github_operations.state import (  # noqa: E402
    exclusive_lock,
    load_journal,
    load_plan,
    plan_path,
    save_journal,
    save_plan,
)


def fake_runner(args: list[str]) -> str:
    command = " ".join(args)
    if command.startswith("api --hostname=github.com user"):
        return json.dumps({"login": "reviewer", "node_id": "U_1"})
    if command.startswith("auth status --active --hostname github.com"):
        return json.dumps({"hosts": {"github.com": [{"login": "reviewer", "active": True}]}})
    if command.startswith("api --hostname=github.com orgs/target-owner"):
        return json.dumps({"login": "target-owner", "plan": {"name": "free"}})
    if command.startswith("project list --owner template-owner"):
        return json.dumps({"projects": [{"id": "P_TEMPLATE", "number": 4, "title": "Product Development Template"}]})
    if command.startswith("project list --owner target-owner"):
        return json.dumps({"projects": [{"id": "P_TARGET", "number": 8, "title": "Product Development"}]})
    if command.startswith("repo view target-owner/"):
        full_name = args[2]
        return json.dumps({"id": f"R_{full_name}", "nameWithOwner": full_name, "url": f"https://github.com/{full_name}"})
    if command.startswith("project field-list 8 --owner target-owner"):
        return json.dumps(
            {
                "fields": [
                    {"id": "F_STATUS", "name": "Status", "options": [{"id": "O_INBOX", "name": "Inbox"}]},
                    {"id": "F_PRIORITY", "name": "Priority", "options": [{"id": "O_P1", "name": "P1: next"}]},
                ]
            }
        )
    if command.startswith("project field-list 4 --owner template-owner"):
        return json.dumps(
            {
                "fields": [
                    {"id": "F_STATUS", "name": "Status", "options": [{"id": "O_INBOX", "name": "Inbox"}]},
                    {"id": "F_PRIORITY", "name": "Priority", "options": [{"id": "O_P1", "name": "P1: next"}]},
                ]
            }
        )
    if command.startswith("api graphql"):
        if "login=target-owner" in command:
            return json.dumps(
                {
                    "data": {
                        "organization": {
                            "id": "O_TARGET",
                            "login": "target-owner",
                            "viewerCanCreateProjects": True,
                        }
                    }
                }
            )
        return json.dumps(
            {
                "data": {
                    "node": {
                        "repositories": {"nodes": [], "pageInfo": {"hasNextPage": False, "endCursor": None}},
                        "views": {
                            "nodes": [
                                {
                                    "name": "Board",
                                    "layout": "BOARD",
                                    "filter": "",
                                    "fields": {"nodes": []},
                                    "groupByFields": {"nodes": []},
                                    "verticalGroupByFields": {"nodes": []},
                                }
                            ],
                            "pageInfo": {"hasNextPage": False},
                        },
                        "workflows": {
                            "nodes": [{"name": "Item added to project", "enabled": True}],
                            "pageInfo": {"hasNextPage": False},
                        },
                    }
                }
            }
        )
    if command.startswith("label list --repo target-owner/primary"):
        return json.dumps([{"name": "bug"}, {"name": "feature"}])
    raise AssertionError(f"unexpected gh call: {args}")


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    path = tmp_path / "github-operations.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "owner": "target-owner",
                "repositories": ["primary"],
                "project": {
                    "title": "Product Development",
                    "template": {"owner": "template-owner", "title": "Product Development Template"},
                    "status_field": "Status",
                    "inbox_option": "Inbox",
                    "priority_field": "Priority",
                },
            }
        )
    )
    return path


def test_project_plan_is_deterministic_except_identity_fields(config_path: Path) -> None:
    config = load_config(config_path)
    plan = make_project_plan(fake_runner, config_path, config)
    assert plan.target == "target-owner/Product Development"
    assert plan.observed["existing"]["id"] == "P_TARGET"
    assert [operation["type"] for operation in plan.operations] == ["ensure-repository-link", "verify-contract"]


def test_issue_plan_resolves_fields_by_semantic_name(config_path: Path) -> None:
    config = load_config(config_path)
    plan = make_issue_plan(
        fake_runner,
        config_path,
        config,
        {
            "repo": "primary",
            "title": "Repair retry behavior",
            "body": "Expected behavior",
            "labels": [],
            "priority": "P1: next",
        },
    )
    assert plan.target == "target-owner/primary"
    assert plan.observed["status"]["option"]["id"] == "O_INBOX"
    assert plan.observed["priority"]["option"]["id"] == "O_P1"
    assert "github-operations:fingerprint=" in plan.request["body"]


def test_duplicate_projects_fail_closed(config_path: Path) -> None:
    def duplicate_runner(args: list[str]) -> str:
        if args[:3] == ["project", "list", "--owner"] and args[3] == "target-owner":
            project = {"id": "P", "number": 8, "title": "Product Development"}
            return json.dumps({"projects": [project, {**project, "id": "P2", "number": 9}]})
        return fake_runner(args)

    with pytest.raises(SafetyError, match="multiple projects"):
        make_project_plan(duplicate_runner, config_path, load_config(config_path))


@pytest.mark.parametrize(("plan_name", "available"), [("free", 1), ("team", 5), ("unknown", 1)])
def test_auto_add_limit_is_derived_conservatively(config_path: Path, plan_name: str, available: int) -> None:
    config = load_config(config_path)
    config["auto_add"] = {"default_repository_only": True}

    def plan_runner(args: list[str]) -> str:
        if args[:3] == ["api", "--hostname=github.com", "orgs/target-owner"]:
            value = {"login": "target-owner"}
            if plan_name != "unknown":
                value["plan"] = {"name": plan_name}
            return json.dumps(value)
        return fake_runner(args)

    plan = make_project_plan(plan_runner, config_path, config)
    auto_add = next(operation for operation in plan.operations if operation["type"] == "browser-required-auto-add")
    assert auto_add["available_workflows"] == available


def test_missing_label_fails_before_issue_creation(config_path: Path) -> None:
    config = load_config(config_path)
    request = {
        "repo": "primary",
        "title": "Repair retry behavior",
        "body": "Expected behavior",
        "labels": ["missing"],
        "priority": None,
    }
    with pytest.raises(SafetyError, match="labels do not exist"):
        make_issue_plan(fake_runner, config_path, config, request)


def test_project_creation_permission_is_required_when_project_is_absent(config_path: Path) -> None:
    def denied_runner(args: list[str]) -> str:
        command = " ".join(args)
        if command.startswith("project list --owner target-owner"):
            return json.dumps({"projects": []})
        if command.startswith("api graphql") and "login=target-owner" in command:
            return json.dumps(
                {
                    "data": {
                        "organization": {
                            "id": "O_TARGET",
                            "login": "target-owner",
                            "viewerCanCreateProjects": False,
                        }
                    }
                }
            )
        return fake_runner(args)

    with pytest.raises(SafetyError, match="cannot create Projects"):
        make_project_plan(denied_runner, config_path, load_config(config_path))


@pytest.mark.parametrize("skill", ["github-project-provisioning", "github-issue-create"])
def test_launcher_works_from_arbitrary_cwd(skill: str, tmp_path: Path) -> None:
    launcher = PLUGIN / "skills" / skill / "scripts/run.py"
    result = subprocess.run([sys.executable, str(launcher), "--help"], cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_standalone_skill_copy_fails_with_plugin_instruction(tmp_path: Path) -> None:
    source = PLUGIN / "skills/github-issue-create/scripts/run.py"
    destination = tmp_path / "github-issue-create/scripts/run.py"
    destination.parent.mkdir(parents=True)
    destination.write_text(source.read_text())
    spec = importlib.util.spec_from_file_location("standalone_launcher", destination)
    assert spec is not None
    result = subprocess.run([sys.executable, str(destination), "--help"], text=True, capture_output=True)
    assert result.returncode != 0
    assert "complete github-operations plugin" in result.stderr


def test_launcher_accepts_plugin_with_one_host_manifest(tmp_path: Path) -> None:
    copied = tmp_path / "github-operations"
    shutil.copytree(PLUGIN, copied)
    shutil.rmtree(copied / ".claude-plugin")
    launcher = copied / "skills/github-issue-create/scripts/run.py"
    result = subprocess.run([sys.executable, str(launcher), "--help"], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_launcher_rejects_other_domain() -> None:
    launcher = PLUGIN / "skills/github-issue-create/scripts/run.py"
    result = subprocess.run([sys.executable, str(launcher), "project", "plan"], text=True, capture_output=True)
    assert result.returncode != 0
    assert "only supports the issue domain" in result.stderr


def test_plan_content_tampering_is_rejected(config_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    plan = make_issue_plan(
        fake_runner,
        config_path,
        load_config(config_path),
        {"repo": "primary", "title": "Approved", "body": "Approved body", "labels": [], "priority": None},
    )
    save_plan(plan)
    path = plan_path(plan.plan_id)
    document = json.loads(path.read_text())
    document["request"]["title"] = "Unapproved"
    path.write_text(json.dumps(document))
    with pytest.raises(SafetyError, match="content changed"):
        load_plan(plan.plan_id)


def test_non_github_com_host_is_rejected(config_path: Path) -> None:
    config = json.loads(config_path.read_text())
    config["host"] = "github.example.test"
    config_path.write_text(json.dumps(config))
    with pytest.raises(SafetyError, match="github.com only"):
        load_config(config_path)


@pytest.mark.parametrize("repo", ["other-owner/primary", "target-owner/unlisted"])
def test_issue_repository_must_match_owner_and_allowlist(config_path: Path, repo: str) -> None:
    request = {"repo": repo, "title": "Title", "body": "Body", "labels": [], "priority": None}
    with pytest.raises(SafetyError, match="allowlist"):
        make_issue_plan(fake_runner, config_path, load_config(config_path), request)


def test_project_verification_reports_drift_and_missing_links() -> None:
    observed = {
        "existing": {"id": "P"},
        "drift": ["views differ"],
        "structure": {"repositories": ["target-owner/primary"]},
    }
    config = {"owner": "target-owner", "repositories": ["primary", "secondary"]}
    assert project_verification_errors(observed, config) == [
        "views differ",
        "repository is not linked: target-owner/secondary",
    ]


def test_issue_apply_records_every_step_without_duplicate_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    calls: list[list[str]] = []

    def runner(args: list[str], *, retries: int = 2) -> str:
        calls.append(args)
        command = " ".join(args)
        if command.startswith("api --paginate"):
            return "[[]]"
        if command.startswith("issue create"):
            return "https://github.com/target-owner/primary/issues/1\n"
        if command.startswith("issue view"):
            return json.dumps(
                {
                    "url": "https://github.com/target-owner/primary/issues/1",
                    "body": "Body\n<!-- github-operations:fingerprint=abc -->\n",
                }
            )
        if command.startswith("project item-list"):
            return '{"items": []}'
        if command.startswith("project item-add"):
            return '{"id": "ITEM_1"}'
        if command.startswith("project field-list"):
            return json.dumps(
                {
                    "fields": [
                        {"id": "F_STATUS", "name": "Status", "options": [{"id": "O_INBOX", "name": "Inbox"}]},
                        {"id": "F_PRIORITY", "name": "Priority", "options": [{"id": "O_P1", "name": "P1: next"}]},
                    ]
                }
            )
        if command.startswith("project item-edit"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(cli, "run_gh", runner)
    plan = {
        "plan_id": "PLAN",
        "created_at": "2026-07-12T00:00:00+00:00",
        "request": {
            "title": "Title",
            "body": "Body\n<!-- github-operations:fingerprint=abc -->\n",
            "labels": [],
            "assignee": None,
            "priority": "P1: next",
            "fingerprint": "abc",
        },
        "observed": {
            "repository": {"nameWithOwner": "target-owner/primary"},
            "project": {"id": "P", "number": 1},
        },
    }
    config = {
        "owner": "target-owner",
        "project": {"status_field": "Status", "inbox_option": "Inbox", "priority_field": "Priority"},
    }
    journal = cli._create_issue(plan, config, {})
    assert journal["issue_url"].endswith("/issues/1")
    assert journal["steps"] == ["issue-created", "project-item-added", "status-set", "priority-set"]
    assert sum(call[:2] == ["issue", "create"] for call in calls) == 1


def test_exclusive_lock_rejects_concurrent_apply(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    first = exclusive_lock("target-owner/primary")
    first.__enter__()
    try:
        with pytest.raises(SafetyError, match="another apply"):
            exclusive_lock("target-owner/primary").__enter__()
    finally:
        first.__exit__(None, None, None)


def test_project_apply_copies_links_and_post_verifies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    project = {"id": "P_NEW", "number": 9, "title": "Product Development"}
    state = {"project": None, "linked": set()}
    calls: list[list[str]] = []

    def resolve(_runner, _owner: str, _title: str):
        return state["project"]

    def runner(args: list[str], *, retries: int = 2) -> str:
        calls.append(args)
        if args[:2] == ["project", "copy"]:
            state["project"] = project
            return "{}"
        if args[:2] == ["project", "link"]:
            state["linked"].add(args[-1])
            return ""
        raise AssertionError(args)

    def structure(_runner, _project_id: str) -> dict:
        return {"repositories": sorted(state["linked"]), "views": [], "workflows": []}

    def observe(_runner, config: dict) -> dict:
        return {
            "existing": project,
            "drift": [],
            "structure": {"repositories": sorted(state["linked"])},
        }

    monkeypatch.setattr(cli, "resolve_project", resolve)
    monkeypatch.setattr(cli, "require_project", lambda *_args: project)
    monkeypatch.setattr(cli, "run_gh", runner)
    monkeypatch.setattr(cli, "project_structure", structure)
    monkeypatch.setattr(cli, "observe_project", observe)
    plan = {
        "plan_id": "PLAN_PROJECT",
        "observed": {
            "template": {"id": "P_TEMPLATE", "number": 1, "title": "Template"},
            "existing": None,
            "drift": [],
        },
    }
    config = {
        "owner": "target-owner",
        "repositories": ["primary", "secondary"],
        "project": {
            "title": "Product Development",
            "template": {"owner": "template-owner", "title": "Template"},
        },
    }
    result = cli._apply_project(plan, config, {}, allow_reconcile=False)
    assert result["verified"] is True
    assert state["linked"] == {"target-owner/primary", "target-owner/secondary"}
    assert sum(call[:2] == ["project", "copy"] for call in calls) == 1
    assert sum(call[:2] == ["project", "link"] for call in calls) == 2


def test_verify_returns_nonzero_for_project_drift(
    config_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli,
        "observe_project",
        lambda *_args: {
            "existing": {"id": "P"},
            "drift": ["workflow differs"],
            "structure": {"repositories": ["target-owner/primary"]},
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["github-operations", "project", "verify", "--config", str(config_path)],
    )
    assert cli.main() == 1
    assert json.loads(capsys.readouterr().out)["verified"] is False


def test_item_add_unknown_result_is_reconciled_without_new_issue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    item_reads = 0
    calls: list[list[str]] = []

    def runner(args: list[str], *, retries: int = 2) -> str:
        nonlocal item_reads
        calls.append(args)
        command = " ".join(args)
        if command.startswith("project item-list"):
            item_reads += 1
            if item_reads == 1:
                return '{"items": []}'
            return json.dumps(
                {"items": [{"id": "ITEM_1", "content": {"url": "https://github.com/o/r/issues/1"}}]}
            )
        if command.startswith("issue view"):
            return json.dumps(
                {
                    "url": "https://github.com/o/r/issues/1",
                    "body": "<!-- github-operations:fingerprint=abc -->",
                }
            )
        if command.startswith("project item-add"):
            raise SafetyError("response lost")
        if command.startswith("project field-list"):
            return json.dumps(
                {
                    "fields": [
                        {"id": "F_STATUS", "name": "Status", "options": [{"id": "O_INBOX", "name": "Inbox"}]}
                    ]
                }
            )
        if command.startswith("project item-edit"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(cli, "run_gh", runner)
    plan = {
        "plan_id": "PLAN_RESUME",
        "created_at": "2026-07-12T00:00:00+00:00",
        "request": {"priority": None, "fingerprint": "abc"},
        "observed": {"repository": {"nameWithOwner": "o/r"}, "project": {"id": "P", "number": 1}},
    }
    config = {"owner": "o", "project": {"status_field": "Status", "inbox_option": "Inbox"}}
    journal = {"issue_url": "https://github.com/o/r/issues/1", "steps": ["issue-created"]}
    result = cli._create_issue(plan, config, journal)
    assert result["item_id"] == "ITEM_1"
    assert not any(call[:2] == ["issue", "create"] for call in calls)


def test_project_resume_requires_copy_attempt_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli,
        "resolve_project",
        lambda *_args: {"id": "P_OTHER", "number": 9, "title": "Product Development"},
    )
    plan = {
        "plan_id": "PLAN_PROJECT_RESUME",
        "observed": {
            "template": {"id": "P_TEMPLATE", "number": 1, "title": "Template"},
            "existing": None,
            "drift": [],
        },
    }
    config = {
        "owner": "target-owner",
        "repositories": [],
        "project": {
            "title": "Product Development",
            "template": {"owner": "template-owner", "title": "Template"},
        },
    }
    with pytest.raises(SafetyError, match="journal proving"):
        cli._apply_project(plan, config, {}, allow_reconcile=True)


def test_tampered_journal_item_is_rejected_before_edit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def runner(args: list[str], *, retries: int = 2) -> str:
        calls.append(args)
        command = " ".join(args)
        if command.startswith("issue view"):
            return json.dumps(
                {
                    "url": "https://github.com/o/r/issues/1",
                    "body": "<!-- github-operations:fingerprint=abc -->",
                }
            )
        if command.startswith("project item-list"):
            return json.dumps(
                {"items": [{"id": "ITEM_REAL", "content": {"url": "https://github.com/o/r/issues/1"}}]}
            )
        raise AssertionError(args)

    monkeypatch.setattr(cli, "run_gh", runner)
    plan = {
        "plan_id": "PLAN_TAMPERED",
        "request": {"priority": None, "fingerprint": "abc"},
        "observed": {"repository": {"nameWithOwner": "o/r"}, "project": {"id": "P", "number": 1}},
    }
    config = {"owner": "o", "project": {"status_field": "Status", "inbox_option": "Inbox"}}
    journal = {
        "issue_url": "https://github.com/o/r/issues/1",
        "item_id": "ITEM_OTHER",
        "steps": ["issue-created", "project-item-added"],
    }
    with pytest.raises(SafetyError, match="does not reference"):
        cli._create_issue(plan, config, journal)
    assert not any(call[:2] == ["project", "item-edit"] for call in calls)


def test_journal_is_bound_to_plan_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    journal = {"steps": ["issue-created"]}
    save_journal("PLAN_A", journal)
    path = tmp_path / "github-operations" / "journals" / "PLAN_A.json"
    stored = json.loads(path.read_text())
    stored["plan_id"] = "PLAN_B"
    path.write_text(json.dumps(stored))
    with pytest.raises(SafetyError, match="plan binding"):
        load_journal("PLAN_A")


def test_journal_rejects_invalid_field_types(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    journal = {"steps": ["issue-created"]}
    save_journal("PLAN_A", journal)
    path = tmp_path / "github-operations" / "journals" / "PLAN_A.json"
    stored = json.loads(path.read_text())
    stored["issue_url"] = 123
    path.write_text(json.dumps(stored))
    with pytest.raises(SafetyError, match="issue_url"):
        load_journal("PLAN_A")
