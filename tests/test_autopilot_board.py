"""Tests for the deterministic parts of the autopilot plumbing.

These are the pieces that used to be shell embedded in prose, where three review
rounds kept finding defects that only appear at runtime.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "autopilot_board", ROOT / "plugins/toolbox/skills/autopilot/scripts/autopilot_board.py"
)
board = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(board)


class TestBranchName:
    def test_slugifies_an_ascii_title(self):
        assert board.branch_name("Add Retry To Queue", 7) == "autopilot/add-retry-to-queue"

    def test_collapses_separators_and_trims(self):
        assert board.branch_name("Fix  bug / crash__now", 1) == "autopilot/fix-bug-crash-now"

    def test_falls_back_to_the_issue_number_for_non_ascii(self):
        assert board.branch_name("キューに再試行を追加", 42) == "autopilot/issue-42"

    def test_falls_back_when_slugification_leaves_almost_nothing(self):
        # "C# / .NET" reduces to "c-net" only if punctuation survives; it does not.
        assert board.branch_name("C# — !!", 9) == "autopilot/issue-9"

    def test_truncates_without_a_trailing_hyphen(self):
        name = board.branch_name("word " * 40, 1)
        assert len(name) <= len(board.BRANCH_PREFIX) + board.BRANCH_MAX
        assert not name.endswith("-")

    def test_non_ascii_without_an_issue_number_uses_a_stable_hash(self):
        assert board.branch_name("日本語のみ", None) == "autopilot/task-1864ec8f49b1"

    def test_non_ascii_hash_fallback_is_nfkc_stable(self):
        assert board.branch_name("ＡＩ タスク", None) == board.branch_name("AI タスク", None)

    def test_empty_title_without_an_issue_number_still_fails(self):
        with pytest.raises(board.Failure, match="empty title"):
            board.branch_name("", None)


class TestPickItem:
    ITEMS = [
        {"id": "a", "status": "Inbox", "priority": "P1"},
        {"id": "b", "status": "Ready", "priority": "P2"},
        {"id": "c", "status": "Ready", "priority": "P1"},
    ]

    def test_earlier_columns_outrank_later_ones(self):
        # Ready comes first in pick_from, so its P2 beats Inbox's P1.
        assert board.pick_item(self.ITEMS, ["Ready", "Inbox"])["id"] == "c"

    def test_priority_breaks_ties_within_a_column(self):
        assert board.pick_item(self.ITEMS, ["Ready"])["id"] == "c"

    def test_items_without_a_priority_sort_last(self):
        items = [{"id": "x", "status": "Ready"}, {"id": "y", "status": "Ready", "priority": "P3"}]
        assert board.pick_item(items, ["Ready"])["id"] == "y"

    def test_returns_none_when_no_column_matches(self):
        assert board.pick_item(self.ITEMS, ["Done"]) is None


class TestResolveOptionId:
    FIELDS = {
        "fields": [
            {"id": "f1", "name": "Priority", "options": [{"id": "o0", "name": "P1"}]},
            {
                "id": "f2",
                "name": "Status",
                "options": [{"id": "o1", "name": "Ready"}, {"id": "o2", "name": "In Progress"}],
            },
        ]
    }

    def test_returns_the_field_and_option_ids(self):
        assert board.resolve_option_id(self.FIELDS, "Status", "In Progress") == ("f2", "o2")

    def test_names_the_available_options_when_one_is_missing(self):
        with pytest.raises(board.Failure, match="Ready, In Progress"):
            board.resolve_option_id(self.FIELDS, "Status", "In Review")

    def test_fails_on_an_unknown_field(self):
        with pytest.raises(board.Failure, match="no field named"):
            board.resolve_option_id(self.FIELDS, "Stage", "Ready")


class TestGateAllows:
    @pytest.mark.parametrize("value", ["human", "Auto", "AUTO", "auto ", "true", "yes", "", None, 1, 0, False])
    def test_anything_ambiguous_falls_back_to_human(self, value):
        assert board.gate_allows({"gates": {"merge": value}}, "merge") is False

    @pytest.mark.parametrize("value", ["auto", True])
    def test_unmistakable_affirmatives_allow(self, value):
        # Deployed configs write the boolean; the skill documents the string.
        assert board.gate_allows({"gates": {"merge": value}}, "merge") is True

    def test_missing_gates_block(self):
        assert board.gate_allows({}, "merge") is False


class TestStatusName:
    def test_uses_the_existing_names_by_default(self):
        assert board.status_name({}, "inProgress") == "In Progress"
        assert board.status_name({}, "inReview") == "In Review"
        assert board.status_name({}, "done") == "Done"

    def test_accepts_adapter_local_names(self):
        source = {"statusNames": {"inProgress": "Doing", "inReview": "Checking"}}
        assert board.status_name(source, "inProgress") == "Doing"
        assert board.status_name(source, "inReview") == "Checking"
        assert board.status_name(source, "done") == "Done"

    def test_rejects_empty_or_unknown_names(self):
        with pytest.raises(board.Failure, match="non-empty string"):
            board.status_name({"statusNames": {"done": ""}}, "done")
        with pytest.raises(board.Failure, match="unknown lifecycle phase"):
            board.status_name({}, "blocked")

    def test_rejects_a_non_object_or_unknown_mapping_key(self):
        with pytest.raises(board.Failure, match="must be an object"):
            board.status_name({"statusNames": "Doing"}, "done")
        with pytest.raises(board.Failure, match="unknown keys: inreview"):
            board.status_name({"statusNames": {"inreview": "Checking"}}, "done")


class TestProtectionIsEnforced:
    GOOD = {
        "required_status_checks": {"contexts": ["ci"]},
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
    }

    def test_accepts_protection_that_can_stop_a_bad_merge(self):
        assert board.protection_is_enforced(self.GOOD) == (True, [])

    def test_rejects_when_admins_can_bypass(self):
        protection = {**self.GOOD, "enforce_admins": {"enabled": False}}
        ok, reasons = board.protection_is_enforced(protection)
        assert not ok and any("enforce_admins" in r for r in reasons)

    def test_rejects_when_nothing_must_pass(self):
        protection = {**self.GOOD, "required_status_checks": {"contexts": []}}
        ok, reasons = board.protection_is_enforced(protection)
        assert not ok and any("required status checks" in r for r in reasons)

    def test_rejects_when_force_pushes_are_allowed(self):
        protection = {**self.GOOD, "allow_force_pushes": {"enabled": True}}
        ok, reasons = board.protection_is_enforced(protection)
        assert not ok and any("force push" in r for r in reasons)

    def test_an_unprotected_branch_reports_every_reason(self):
        ok, reasons = board.protection_is_enforced({})
        assert not ok and len(reasons) == 2


class TestPreflight:
    def _config(self, tmp_path, **extra):
        path = tmp_path / "autopilot.json"
        path.write_text(json.dumps({"repo": "owner/name", **extra}))
        return path

    def test_refuses_when_the_directory_is_a_different_repository(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(board, "run_gh", lambda a: json.dumps({"nameWithOwner": "owner/other"}))
        assert board.main(["--config", str(self._config(tmp_path)), "preflight"]) == 1
        assert "repository mismatch" in capsys.readouterr().err

    def test_human_gate_needs_no_protection_lookup(self, tmp_path, monkeypatch):
        monkeypatch.setattr(board, "run_gh", lambda a: json.dumps({"nameWithOwner": "owner/name"}))
        assert board.main(["--config", str(self._config(tmp_path)), "preflight"]) == 0

    def test_protection_that_exists_but_cannot_enforce_also_downgrades(self, tmp_path, monkeypatch, capsys):
        def fake(args):
            if args[0] == "repo":
                return json.dumps({"nameWithOwner": "owner/name"})
            return json.dumps({})  # a rule exists but enforces nothing

        monkeypatch.setattr(board, "run_gh", fake)
        config = self._config(tmp_path, gates={"merge": "auto"})
        assert board.main(["--config", str(config), "preflight"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["mergeGate"] == "human"
        assert "enforce_admins" in out["notes"][0]

    def test_a_protected_branch_keeps_the_automatic_gate(self, tmp_path, monkeypatch, capsys):
        def fake(args):
            if args[0] == "repo":
                return json.dumps({"nameWithOwner": "owner/name"})
            return json.dumps(TestProtectionIsEnforced.GOOD)

        monkeypatch.setattr(board, "run_gh", fake)
        config = self._config(tmp_path, gates={"merge": "auto"})
        assert board.main(["--config", str(config), "preflight"]) == 0
        assert json.loads(capsys.readouterr().out)["mergeGate"] == "auto"

    def test_missing_config_stops_the_run(self, tmp_path, capsys):
        assert board.main(["--config", str(tmp_path / "absent.json"), "preflight"]) == 1
        assert "not found" in capsys.readouterr().err

    def test_unprotected_branch_downgrades_instead_of_refusing(self, tmp_path, monkeypatch, capsys):
        # Refusing would strand a whole backlog over a repository setting no task can
        # fix; stopping at PR creation is what an unset gate would have done anyway.
        def fake(args):
            if args[0] == "repo":
                return json.dumps({"nameWithOwner": "owner/name"})
            raise board.Failure("gh api failed: HTTP 404: Branch not protected")

        monkeypatch.setattr(board, "run_gh", fake)
        config = self._config(tmp_path, gates={"merge": "auto"})
        assert board.main(["--config", str(config), "preflight"]) == 0
        out = json.loads(capsys.readouterr().out)
        assert out["mergeGate"] == "human"
        assert "no protection rule" in out["notes"][0]

    def test_a_plan_that_cannot_protect_also_downgrades(self, tmp_path, monkeypatch, capsys):
        def fake(args):
            if args[0] == "repo":
                return json.dumps({"nameWithOwner": "owner/name"})
            raise board.Failure("gh api failed: HTTP 403: Upgrade to GitHub Pro")

        monkeypatch.setattr(board, "run_gh", fake)
        config = self._config(tmp_path, gates={"merge": True})
        assert board.main(["--config", str(config), "preflight"]) == 0
        assert json.loads(capsys.readouterr().out)["mergeGate"] == "human"

    def test_an_unexpected_gh_error_still_stops(self, tmp_path, monkeypatch):
        def fake(args):
            if args[0] == "repo":
                return json.dumps({"nameWithOwner": "owner/name"})
            raise board.Failure("gh api failed: HTTP 500")

        monkeypatch.setattr(board, "run_gh", fake)
        config = self._config(tmp_path, gates={"merge": "auto"})
        assert board.main(["--config", str(config), "preflight"]) == 1

    def test_deploy_gate_is_resolved_too(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(board, "run_gh", lambda a: json.dumps({"nameWithOwner": "owner/name"}))
        config = self._config(tmp_path, gates={"deploy": True})
        board.main(["--config", str(config), "preflight"])
        assert json.loads(capsys.readouterr().out)["deployGate"] == "auto"


class TestNextTask:
    PROJECT = {"id": "PVT_1"}
    FIELDS = {
        "fields": [
            {
                "id": "f",
                "name": "Status",
                "options": [
                    {"id": "ready", "name": "Ready"},
                    {"id": "wip", "name": "In Progress"},
                ],
            }
        ]
    }

    def _run(self, tmp_path, monkeypatch, items, extra_args=()):
        config = tmp_path / "autopilot.json"
        config.write_text(
            json.dumps(
                {
                    "repo": "owner/name",
                    "taskSource": {"githubProjects": {"owner": "o", "projectNumber": 1, "pickFrom": ["Ready"]}},
                }
            )
        )
        calls = []

        def fake(args):
            calls.append(args)
            if args[1] == "view":
                return json.dumps(self.PROJECT)
            if args[1] == "field-list":
                return json.dumps(self.FIELDS)
            if args[1] == "item-list":
                return json.dumps({"items": items})
            return ""

        monkeypatch.setattr(board, "run_gh", fake)
        args = board.build_parser().parse_args(
            [
                "--config",
                str(config),
                "next-task",
                "--expected-config-digest",
                board.config_digest(json.loads(config.read_text())),
                *extra_args,
            ]
        )
        return board.cmd_next_task(args), calls

    def test_claiming_a_task_moves_it_to_in_progress(self, tmp_path, monkeypatch):
        items = [
            {
                "id": "i1",
                "status": "Ready",
                "title": "Add cache",
                "content": {"number": 3, "url": "https://github.com/owner/name/issues/3"},
            }
        ]
        result, calls = self._run(tmp_path, monkeypatch, items)
        assert result["task"]["itemId"] == "i1"
        assert result["task"]["branch"] == "autopilot/add-cache"
        assert result["task"]["projectId"] == "PVT_1"
        assert result["task"]["resumed"] is False
        assert not [c for c in calls if c[1] == "item-edit"]
        assert not [c for c in calls if c[:2] == ["issue", "edit"]]

    def test_resuming_does_not_rewrite_the_board(self, tmp_path, monkeypatch):
        items = [
            {
                "id": "i1",
                "status": "Ready",
                "title": "New",
                "content": {"number": 1, "url": "https://github.com/owner/name/issues/1"},
            },
            {
                "id": "i2",
                "status": "In Progress",
                "title": "Half done",
                "content": {"number": 2, "url": "https://github.com/owner/name/issues/2"},
            },
        ]
        result, calls = self._run(tmp_path, monkeypatch, items)
        assert result["task"]["itemId"] == "i2", "an in-flight task outranks a fresh one"
        assert result["task"]["resumed"] is True
        assert not [c for c in calls if c[1] == "item-edit"], "already In Progress; nothing to set"
        assert not [c for c in calls if c[:2] == ["issue", "edit"]]

    def test_an_excluded_task_does_not_block_the_rest_of_the_board(self, tmp_path, monkeypatch):
        # The escalated task is still sitting In Progress; without exclusion the resume
        # path re-claims it every iteration and no other task ever runs.
        items = [
            {
                "id": "stuck",
                "status": "In Progress",
                "title": "Stuck",
                "content": {"number": 1, "url": "https://github.com/owner/name/issues/1"},
            },
            {
                "id": "next",
                "status": "Ready",
                "title": "Next one",
                "content": {"number": 2, "url": "https://github.com/owner/name/issues/2"},
            },
        ]
        result, _ = self._run(tmp_path, monkeypatch, items, ["--exclude", "stuck"])
        assert result["task"]["itemId"] == "next"

    def test_an_empty_board_ends_the_run_cleanly(self, tmp_path, monkeypatch):
        result, _ = self._run(
            tmp_path,
            monkeypatch,
            [{"id": "x", "status": "Done", "content": {"url": "https://github.com/owner/name/issues/1"}}],
        )
        assert result == {"task": None}

    def test_custom_in_progress_name_is_used_for_claim(self, tmp_path, monkeypatch):
        config = tmp_path / "autopilot.json"
        config.write_text(
            json.dumps(
                {
                    "repo": "owner/name",
                    "taskSource": {
                        "githubProjects": {
                            "owner": "o",
                            "projectNumber": 1,
                            "pickFrom": ["Ready"],
                            "statusNames": {"inProgress": "Doing"},
                        }
                    },
                }
            )
        )
        fields = {
            "fields": [
                {
                    "id": "f",
                    "name": "Status",
                    "options": [
                        {"id": "ready", "name": "Ready"},
                        {"id": "doing", "name": "Doing"},
                    ],
                }
            ]
        }
        calls = []

        def fake(args):
            calls.append(args)
            if args[1] == "view":
                return json.dumps(self.PROJECT)
            if args[1] == "field-list":
                return json.dumps(fields)
            if args[1] == "item-list":
                return json.dumps(
                    {
                        "items": [
                            {
                                "id": "i1",
                                "status": "Ready",
                                "title": "Add cache",
                                "content": {"number": 3, "url": "https://github.com/owner/name/issues/3"},
                            }
                        ]
                    }
                )
            return ""

        monkeypatch.setattr(board, "run_gh", fake)
        args = board.build_parser().parse_args(
            [
                "--config",
                str(config),
                "next-task",
                "--expected-config-digest",
                board.config_digest(json.loads(config.read_text())),
            ]
        )
        assert board.cmd_next_task(args)["task"]["itemId"] == "i1"
        assert not [call for call in calls if call[1] == "item-edit"]

    def test_custom_in_progress_name_is_used_for_resume(self, tmp_path, monkeypatch):
        items = [
            {
                "id": "i1",
                "status": "Doing",
                "title": "Half done",
                "content": {"number": 3, "url": "https://github.com/owner/name/issues/3"},
            }
        ]
        config = tmp_path / "autopilot.json"
        config.write_text(
            json.dumps(
                {
                    "repo": "owner/name",
                    "taskSource": {
                        "githubProjects": {
                            "owner": "o",
                            "projectNumber": 1,
                            "pickFrom": ["Ready"],
                            "statusNames": {"inProgress": "Doing"},
                        }
                    },
                }
            )
        )
        calls = []

        def fake(args):
            calls.append(args)
            if args[1] == "view":
                return json.dumps(self.PROJECT)
            if args[1] == "field-list":
                return json.dumps(
                    {
                        "fields": [
                            {
                                "id": "f",
                                "name": "Status",
                                "options": [{"id": "doing", "name": "Doing"}],
                            }
                        ]
                    }
                )
            if args[1] == "item-list":
                return json.dumps({"items": items})
            return ""

        monkeypatch.setattr(board, "run_gh", fake)
        args = board.build_parser().parse_args(
            [
                "--config",
                str(config),
                "next-task",
                "--expected-config-digest",
                board.config_digest(json.loads(config.read_text())),
            ]
        )
        result = board.cmd_next_task(args)
        assert result["task"]["resumed"] is True
        assert not [call for call in calls if call[1] == "item-edit"]

    def test_foreign_repository_issue_is_rejected_without_writes(self, tmp_path, monkeypatch):
        items = [
            {
                "id": "foreign",
                "status": "Ready",
                "title": "Wrong repository",
                "content": {
                    "number": 3,
                    "url": "https://github.com/another/repository/issues/3",
                },
            }
        ]
        with pytest.raises(board.Failure, match="not configured owner/name#3"):
            self._run(tmp_path, monkeypatch, items)

    def test_draft_item_is_rejected_before_it_is_claimed(self, tmp_path, monkeypatch):
        config = tmp_path / "autopilot.json"
        config.write_text(
            json.dumps(
                {
                    "repo": "owner/name",
                    "taskSource": {
                        "githubProjects": {
                            "owner": "o",
                            "projectNumber": 1,
                            "pickFrom": ["Ready"],
                        }
                    },
                }
            )
        )
        calls = []

        def fake(args):
            calls.append(args)
            if args[1] == "view":
                return json.dumps(self.PROJECT)
            if args[1] == "field-list":
                return json.dumps(self.FIELDS)
            if args[1] == "item-list":
                return json.dumps(
                    {
                        "items": [
                            {
                                "id": "draft",
                                "status": "Ready",
                                "title": "Untracked",
                                "content": {},
                            }
                        ]
                    }
                )
            return ""

        monkeypatch.setattr(board, "run_gh", fake)
        args = board.build_parser().parse_args(
            [
                "--config",
                str(config),
                "next-task",
                "--expected-config-digest",
                board.config_digest(json.loads(config.read_text())),
            ]
        )
        with pytest.raises(board.Failure, match="no durable Issue journal"):
            board.cmd_next_task(args)
        assert not [call for call in calls if call[1] == "item-edit"]


class TestSetStatus:
    def _run(self, tmp_path, monkeypatch, extra_args, status_names=None):
        config = tmp_path / "autopilot.json"
        source = {"owner": "o", "projectNumber": 1}
        if status_names:
            source["statusNames"] = status_names
        config.write_text(json.dumps({"repo": "owner/name", "taskSource": {"githubProjects": source}}))
        calls = []

        def fake(args):
            calls.append(args)
            if args[1] == "field-list":
                return json.dumps(
                    {
                        "fields": [
                            {
                                "id": "f",
                                "name": "Status",
                                "options": [
                                    {"id": "checking", "name": "Checking"},
                                    {"id": "review", "name": "In Review"},
                                ],
                            }
                        ]
                    }
                )
            return ""

        monkeypatch.setattr(board, "run_gh", fake)
        args = board.build_parser().parse_args(
            [
                "--config",
                str(config),
                "set-status",
                "--project-id",
                "p",
                "--item-id",
                "i",
                *extra_args,
            ]
        )
        return board.cmd_set_status(args), calls

    def test_semantic_phase_uses_the_adapter_mapping(self, tmp_path, monkeypatch):
        result, calls = self._run(tmp_path, monkeypatch, ["--phase", "inReview"], {"inReview": "Checking"})
        assert result["status"] == "Checking"
        assert any("checking" in call for call in calls if call[1] == "item-edit")

    def test_literal_status_remains_backward_compatible(self, tmp_path, monkeypatch):
        result, calls = self._run(tmp_path, monkeypatch, ["--status", "In Review"])
        assert result["status"] == "In Review"
        assert any("review" in call for call in calls if call[1] == "item-edit")

    def test_phase_and_literal_status_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            board.build_parser().parse_args(
                [
                    "set-status",
                    "--project-id",
                    "p",
                    "--item-id",
                    "i",
                    "--phase",
                    "done",
                    "--status",
                    "Done",
                ]
            )


class TestBranchNameCommand:
    def test_available_outside_the_board_path(self, capsys):
        assert board.main(["branch-name", "--title", "Fix the parser"]) == 0
        assert json.loads(capsys.readouterr().out)["branch"] == "autopilot/fix-the-parser"

    def test_non_ascii_needs_an_issue_number(self, capsys):
        assert board.main(["branch-name", "--title", "日本語", "--issue-number", "8"]) == 0
        assert json.loads(capsys.readouterr().out)["branch"] == "autopilot/issue-8"

    def test_non_ascii_without_an_issue_number_uses_a_stable_hash(self, capsys):
        assert board.main(["branch-name", "--title", "日本語"]) == 0
        assert json.loads(capsys.readouterr().out)["branch"].startswith("autopilot/task-")
