"""A session that works on a goal tells its human when it stops; every other session stays silent."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/toolbox/skills/human-notify/scripts/waiting_notify.py"
NOTIFIER = """#!{python}
import json, os, sys, time
if os.path.exists(os.environ["NOTIFY_SINK"] + ".refuse"):
    sys.exit("notifications are not allowed")
hold = os.environ["NOTIFY_SINK"] + ".hold"
if os.path.exists(hold):
    open(hold + ".reached", "w").close()
    while os.path.exists(hold):
        time.sleep(0.02)
with open(os.environ["NOTIFY_SINK"], "a", encoding="utf-8") as sink:
    sink.write(json.dumps(sys.argv[1:], ensure_ascii=False) + "\\n")
"""


class Desk:
    """One isolated machine: its own home, state directory, notifier commands, and a git repository."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.sink = root / "delivered.jsonl"
        self.state = root / "state"
        bin_dir = root / "bin"
        bin_dir.mkdir()
        # Both desktop notifiers are replaced at the OS boundary, so the test runs on macOS and Linux.
        for name in ("osascript", "notify-send"):
            command = bin_dir / name
            command.write_text(NOTIFIER.format(python=sys.executable))
            command.chmod(0o755)
        self.env = {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(root / "home"),
            "XDG_STATE_HOME": str(self.state),
            "XDG_CONFIG_HOME": str(root / "config"),
            "TMPDIR": str(root),
            "NOTIFY_SINK": str(self.sink),
        }
        (root / "home").mkdir()
        self.repo = root / "booking-site"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "README.md").write_text("booking\n")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t", "commit", "-q", "-m", "init")
        self.transcript = root / "transcript.jsonl"
        self.transcript.write_text("{}\n")

    def git(self, *args: str, cwd: Path | None = None) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd or self.repo, env=self.env, check=True, capture_output=True, text=True
        ).stdout

    def run(self, *args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], input=stdin, env=self.env, capture_output=True, text=True
        )

    def hook(self, event: str, cwd: Path | None = None, **fields: str) -> subprocess.CompletedProcess[str]:
        payload = {
            "hook_event_name": event,
            "cwd": str(cwd or self.repo),
            "transcript_path": str(self.transcript),
            **fields,
        }
        return self.run("hook", stdin=json.dumps(payload))

    def marks(self) -> list[Path]:
        return sorted((self.state / "human-notify/marks").glob("*.json"))

    def refuse_notifications(self, refuse: bool) -> None:
        switch = Path(f"{self.sink}.refuse")
        switch.touch() if refuse else switch.unlink()

    def delivered(self) -> list[list[str]]:
        if not self.sink.exists():
            return []
        return [json.loads(line) for line in self.sink.read_text(encoding="utf-8").splitlines()]

    def log(self) -> list[dict]:
        path = self.state / "human-notify/waiting.log"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    def logged(self, event: str) -> list[dict]:
        return [entry for entry in self.log() if entry["event"] == event]

    def wait_for(self, ready, what: str):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            value = ready()
            if value:
                return value
            time.sleep(0.02)
        raise AssertionError(f"timed out waiting for {what}; log: {self.log()}")


@pytest.fixture
def desk(tmp_path: Path) -> Desk:
    return Desk(tmp_path)


def test_sessions_without_a_goal_mark_stay_silent(desk: Desk) -> None:
    result = desk.hook("Stop")

    assert (result.returncode, result.stdout) == (0, "")
    assert desk.delivered() == []
    assert desk.log() == []


def test_a_stopped_goal_session_is_announced_with_repository_goal_and_state(desk: Desk) -> None:
    marked = desk.run(
        "mark", "--cwd", str(desk.repo), "--goal", "予約確認メールの自動再送",
        "--page", "/tmp/goal.html", "--state", "判断待ち", "--delay", "0",
    )
    assert marked.returncode == 0, marked.stderr

    result = desk.hook("Stop")

    assert (result.returncode, result.stdout) == (0, "")
    notice = " ".join(desk.wait_for(desk.delivered, "the notification")[0])
    assert "booking-site" in notice
    assert "予約確認メールの自動再送" in notice
    assert "判断待ち" in notice


def test_a_session_that_keeps_working_is_not_announced(desk: Desk) -> None:
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "0.2")

    first = desk.hook("Stop")
    # The host starts the next turn by itself: the transcript keeps being written.
    later = time.time() + 30
    os.utime(desk.transcript, (later, later))
    second = desk.hook("Stop")

    assert (first.returncode, first.stdout, second.returncode, second.stdout) == (0, "", 0, "")
    desk.wait_for(lambda: desk.logged("superseded"), "the first turn end to yield")
    desk.run("clear", "--cwd", str(desk.repo))
    desk.wait_for(lambda: desk.logged("cleared"), "the second turn end to yield")
    assert desk.delivered() == []


def test_a_stop_the_session_did_not_declare_is_still_announced_once_it_stays_quiet(desk: Desk) -> None:
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "0.05")

    desk.hook("Stop")

    notice = " ".join(desk.wait_for(desk.delivered, "the fallback notification")[0])
    assert "進行中" in notice
    assert "再送" in notice


def test_a_permission_request_is_announced_at_once(desk: Desk) -> None:
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "600")

    result = desk.hook("PermissionRequest", tool_name="Bash")

    assert (result.returncode, result.stdout) == (0, "")
    notice = " ".join(desk.wait_for(desk.delivered, "the notification")[0])
    assert "booking-site" in notice
    assert "許可待ち" in notice
    assert "Bash" in notice


def test_the_mark_belongs_to_one_worktree(desk: Desk) -> None:
    worktree = desk.root / "booking-site-resend"
    desk.git("worktree", "add", "-q", str(worktree), "-b", "resend")
    desk.run("mark", "--cwd", str(worktree), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "0")

    desk.hook("Stop", cwd=desk.repo)
    desk.hook("Stop", cwd=worktree)

    desk.wait_for(desk.delivered, "the worktree's notification")
    assert len(desk.delivered()) == 1
    assert [entry["event"] for entry in desk.log()] == ["delivered"]


def test_the_state_can_change_without_repeating_the_goal_and_clearing_silences_the_session(desk: Desk) -> None:
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "0")
    desk.run("mark", "--cwd", str(desk.repo), "--state", "外部待ち")

    desk.hook("Stop")
    notice = " ".join(desk.wait_for(desk.delivered, "the notification")[0])
    assert "再送" in notice
    assert "外部待ち" in notice

    assert desk.run("clear", "--cwd", str(desk.repo)).returncode == 0
    desk.hook("Stop")
    assert len(desk.delivered()) == 1


def test_an_urgent_message_is_sent_while_the_session_keeps_working(desk: Desk) -> None:
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html")

    result = desk.run("send", "--cwd", str(desk.repo), "--message", "Q1：反映の時刻を決めてください")

    assert result.returncode == 0, result.stderr
    notice = " ".join(desk.delivered()[0])
    assert "booking-site" in notice
    assert "再送" in notice
    assert "Q1：反映の時刻を決めてください" in notice


def test_a_session_that_resumes_and_updates_its_state_withdraws_the_pending_notice(desk: Desk) -> None:
    desk.run(
        "mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html",
        "--state", "判断待ち", "--delay", "0.5",
    )
    desk.hook("Stop")

    # The answer arrives and the session goes back to work before the quiet period is over.
    desk.run("mark", "--cwd", str(desk.repo), "--state", "進行中")

    desk.wait_for(lambda: desk.logged("superseded"), "the pending notice to be withdrawn")
    assert desk.delivered() == []


def test_another_session_in_the_same_worktree_does_not_speak_for_the_goal(desk: Desk) -> None:
    desk.env["CLAUDE_CODE_SESSION_ID"] = "goal-session"
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "0")

    # A review run or an unrelated conversation ends its turn in the same worktree.
    desk.hook("Stop", session_id="review-run")
    desk.hook("PermissionRequest", session_id="review-run", tool_name="Bash")
    desk.wait_for(lambda: len(desk.logged("other-session")) == 2, "the other session to be set aside")
    assert desk.delivered() == []

    desk.hook("Stop", session_id="goal-session")
    assert "再送" in " ".join(desk.wait_for(desk.delivered, "the goal session's notification")[0])


def test_a_turn_that_dies_on_an_api_error_is_announced_at_once(desk: Desk) -> None:
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "600")

    result = desk.hook("StopFailure", error="rate_limit")

    assert (result.returncode, result.stdout) == (0, "")
    notice = " ".join(desk.wait_for(desk.delivered, "the notification")[0])
    assert "booking-site" in notice
    assert "再送" in notice
    assert "rate_limit" in notice


def test_completion_is_announced_once_and_then_the_worktree_is_silent(desk: Desk) -> None:
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "0")
    desk.run("mark", "--cwd", str(desk.repo), "--state", "完了")

    desk.hook("Stop")
    notice = " ".join(desk.wait_for(desk.delivered, "the completion notice")[0])
    assert "完了" in notice
    assert "再送" in notice

    # The goal is over: a later conversation in the same worktree is an ordinary one again.
    desk.wait_for(lambda: not desk.marks(), "the mark to be removed")
    desk.hook("Stop")
    desk.hook("PermissionRequest", tool_name="Bash")
    assert len(desk.delivered()) == 1


def test_a_completion_that_could_not_be_announced_is_announced_at_the_next_stop(desk: Desk) -> None:
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "0")
    desk.run("mark", "--cwd", str(desk.repo), "--state", "完了")
    desk.refuse_notifications(True)

    desk.hook("Stop")
    desk.wait_for(lambda: desk.logged("error"), "the failed delivery to be recorded")
    assert desk.delivered() == []

    desk.refuse_notifications(False)
    desk.hook("Stop")
    notice = " ".join(desk.wait_for(desk.delivered, "the completion notice")[0])
    assert "完了" in notice


def test_a_completion_still_going_out_does_not_silence_the_next_goal(desk: Desk) -> None:
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "0")
    desk.run("mark", "--cwd", str(desk.repo), "--state", "完了")
    hold = Path(f"{desk.sink}.hold")
    hold.touch()

    desk.hook("Stop")
    desk.wait_for(Path(f"{hold}.reached").exists, "the completion notice to start going out")
    # The next goal starts in the same worktree before the first notice has finished.
    desk.run(
        "mark", "--cwd", str(desk.repo), "--goal", "管理画面", "--page", "/tmp/next.html",
        "--state", "判断待ち", "--delay", "0",
    )
    hold.unlink()
    desk.wait_for(desk.delivered, "the completion notice")

    desk.hook("Stop")
    notices = desk.wait_for(lambda: len(desk.delivered()) == 2 and desk.delivered(), "the next goal's notice")
    assert "再送" in " ".join(notices[0])
    assert "管理画面" in " ".join(notices[1])


def test_a_goal_can_be_marked_where_the_git_directory_is_read_only(desk: Desk) -> None:
    # Sandboxed hosts protect the git directory of the workspace they let a session write.
    git_dir = desk.repo / ".git"
    locked = [git_dir, *(path for path in git_dir.rglob("*") if path.is_dir())]
    for path in locked:
        path.chmod(0o555)
    try:
        marked = desk.run(
            "mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html", "--delay", "0"
        )
        assert marked.returncode == 0, marked.stderr
        desk.hook("Stop")
        assert "再送" in " ".join(desk.wait_for(desk.delivered, "the notification")[0])
    finally:
        for path in locked:
            path.chmod(0o755)


def test_a_refused_notification_is_recorded_without_the_message(desk: Desk) -> None:
    desk.run("mark", "--cwd", str(desk.repo), "--goal", "再送", "--page", "/tmp/goal.html")
    desk.refuse_notifications(True)

    result = desk.run("send", "--cwd", str(desk.repo), "--message", "Q1：解約の違約金を決めてください")

    assert result.returncode != 0  # the session learns that its message did not go out
    assert desk.delivered() == []
    (failure,) = desk.logged("error")
    assert "notifications are not allowed" in failure["reason"]
    assert "違約金" not in json.dumps(desk.log(), ensure_ascii=False)


def test_a_first_mark_needs_the_goal_and_the_page(desk: Desk) -> None:
    result = desk.run("mark", "--cwd", str(desk.repo), "--state", "進行中")

    assert result.returncode != 0
    assert "--goal" in result.stderr
    desk.hook("Stop")
    assert desk.delivered() == []
