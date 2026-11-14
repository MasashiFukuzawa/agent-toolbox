"""Tell a human when an agent session that is working on a goal stops or waits for permission.

Host hooks call `hook` at every turn end, API failure, and permission request. It stays silent
unless the session's worktree carries a mark written by `mark`, so ordinary conversations never
notify. The mark lives in the user's state directory, keyed by the worktree's git directory:
sandboxed hosts keep the git directory itself read-only.
Python 3.9+, standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from human_notify import identity  # noqa: E402  (repository label shared with human_notify)

WORKING = "進行中"
DONE = "完了"
SESSION_ENV = ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")  # set by the hosts for tool commands
DEFAULT_DELAY = 20.0  # seconds of quiet before a declared stop is announced
UNDECLARED_FACTOR = 6  # a stop while the state still says "working" waits this many times longer
GIVE_UP_AFTER = 45 * 60.0
BANNER = (
    "on run argv",
    "display notification (item 1 of argv) with title (item 2 of argv) subtitle (item 3 of argv)",
    "end run",
)


def state_dir() -> Path:
    path = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "human-notify"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def mark_path(cwd: str) -> Path:
    """One mark per worktree: the key is that worktree's own git directory."""
    git_dir = subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--absolute-git-dir"], capture_output=True, text=True, check=True
    ).stdout.strip()
    marks = state_dir() / "marks"
    marks.mkdir(exist_ok=True, mode=0o700)
    return marks / (hashlib.sha256(git_dir.encode("utf-8")).hexdigest()[:20] + ".json")


def stamp_path(mark: Path) -> Path:
    return mark.with_suffix(".stop")


def log(event: str, **fields: object) -> None:
    """Best effort: a record that cannot be written must not stop a notification."""
    try:
        with (state_dir() / "waiting.log").open("a", encoding="utf-8") as handle:
            line = {"at": round(time.time(), 3), "event": event, **fields}
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError:
        pass


def deliver(cwd: str, mark: dict, state: str, body: str) -> bool:
    """One desktop banner: repository and state in the title, the goal as subtitle."""
    try:
        _, label = identity(cwd)
    except (OSError, ValueError, subprocess.SubprocessError):
        label = Path(cwd).name
    title = f"{label}｜{state}"
    goal = str(mark.get("goal", ""))
    try:
        if platform.system() == "Darwin" and shutil.which("osascript"):
            command = ["osascript"]
            for line in BANNER:
                command += ["-e", line]
            subprocess.run([*command, body, title, goal], check=True, capture_output=True, timeout=15)
        elif shutil.which("notify-send"):
            subprocess.run(["notify-send", title, f"{goal}\n{body}"], check=True, capture_output=True, timeout=15)
        else:
            log("skipped", reason="no desktop notifier on this system", repo=label, goal=goal, state=state)
            return False
    except (OSError, subprocess.SubprocessError) as exc:
        # str(exc) would repeat the command line, and with it the message body.
        detail = getattr(exc, "stderr", None) or b""
        if isinstance(detail, bytes):
            detail = detail.decode("utf-8", "replace")
        reason = f"{type(exc).__name__}: {detail.strip()[:200]}".rstrip(": ")
        log("error", reason=reason, repo=label, goal=goal, state=state)
        return False
    log("delivered", repo=label, goal=goal, state=state)
    return True


def read_mark(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def command_mark(args: argparse.Namespace) -> int:
    path = mark_path(args.cwd)
    mark = read_mark(path) or {}
    for key in ("goal", "page", "state", "delay"):
        value = getattr(args, key)
        if value is not None:
            mark[key] = value
    if not mark.get("goal") or not mark.get("page"):
        print("the first mark needs --goal and --page", file=sys.stderr)
        return 2
    mark.setdefault("state", WORKING)
    if args.goal is not None or "id" not in mark:
        mark["id"] = uuid.uuid4().hex  # a new goal, or a new carrier of it: earlier events are not about this mark
    mark["worktree"] = str(Path(args.cwd).resolve())
    # The session that marks is the one that carries the goal; other sessions in the same
    # worktree (a review run, an unrelated conversation) must not speak for it.
    session = next((os.environ[name] for name in SESSION_ENV if os.environ.get(name)), None)
    if session:
        mark["session"] = session
    else:
        mark.pop("session", None)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(mark, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    stamp_path(path).unlink(missing_ok=True)  # the session is active: a pending stop is no longer the latest
    print(json.dumps({"status": "marked", "mark": str(path)}, ensure_ascii=False))
    return 0


def command_clear(args: argparse.Namespace) -> int:
    path = mark_path(args.cwd)
    path.unlink(missing_ok=True)
    stamp_path(path).unlink(missing_ok=True)
    print(json.dumps({"status": "cleared", "mark": str(path)}, ensure_ascii=False))
    return 0


def command_send(args: argparse.Namespace) -> int:
    mark = read_mark(mark_path(args.cwd)) or {}
    if deliver(args.cwd, mark, str(mark.get("state", "連絡")), args.message):
        return 0
    print("the notification was not delivered; tell the human in the conversation instead", file=sys.stderr)
    return 1


def command_hook(_: argparse.Namespace) -> int:
    """Called by the host. Never prints: some hosts treat hook output as a decision."""
    try:
        event = json.loads(sys.stdin.read() or "{}")
        cwd = str(event.get("cwd") or os.getcwd())
        path = mark_path(cwd)
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        return 0
    mark = read_mark(path)
    if mark is None:
        return 0
    session = event.get("session_id")
    if mark.get("session") and session and session != mark["session"]:
        log("other-session", goal=mark.get("goal"))
        return 0
    name = event.get("hook_event_name")
    page = mark.get("page", "")
    # Delivery always happens in a detached process: the hook must return at once, and a host
    # that exits right after the event (an API failure in a one-shot run) must not take it down.
    # What an immediate notice says is fixed here, when the event arrives: by the time it is
    # delivered the worktree may already carry another goal.
    goal = str(mark.get("goal", ""))
    if name == "PermissionRequest":
        tool = str(event.get("tool_name") or "")
        detach("_now", "--cwd", cwd, "--goal", goal, "--state", "許可待ち",
               "--body", f"許可を待っています{'：' + tool if tool else ''}")
        return 0
    if name == "StopFailure":
        # The turn died on an API error: no ordinary turn end follows, so announce it now.
        error = str(event.get("error") or "")[:80]
        detach("_now", "--cwd", cwd, "--goal", goal, "--state", "エラーで停止",
               "--body", f"APIのエラーで止まりました{'：' + error if error else ''}。ページ：{page}")
        return 0
    # A turn ended. Whether the session really stopped is decided later, by `_after`.
    since = repr(time.time())
    stamp_path(path).write_text(since, encoding="utf-8")
    detach("_after", "--cwd", cwd, "--mark", str(path),
           "--transcript", str(event.get("transcript_path") or ""), "--since", since)
    return 0


def detach(*arguments: str) -> None:
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), *arguments],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
    )


def command_now(args: argparse.Namespace) -> int:
    return 0 if deliver(args.cwd, {"goal": args.goal}, args.state, args.body) else 1


def command_after(args: argparse.Namespace) -> int:
    """Announce the stop once the session has been quiet for long enough.

    A turn end is not yet a stop: the host may start the next turn by itself, and it keeps
    writing bookkeeping to the transcript for a moment. So this waits for quiet, measured from
    the transcript's last write. A stop the session declared (any state other than working)
    is announced after a short quiet; an undeclared one waits longer, because the session may
    be inside a long tool call. A newer turn end, an updated mark, or a cleared mark takes over.
    A long tool call that starts right after an undeclared turn end, without the session touching
    its mark, is not told apart from a stop: the transcript is quiet in both cases.
    """
    path = Path(args.mark)
    transcript = Path(args.transcript) if args.transcript else None
    started = time.time()
    while True:
        mark = read_mark(path)
        if mark is None:
            log("cleared")
            return 0
        try:
            latest = stamp_path(path).read_text(encoding="utf-8")
        except OSError:
            latest = ""  # the session updated its mark after this turn end: it is working again
        if latest != args.since:
            log("superseded", goal=mark.get("goal"))
            return 0
        state = str(mark.get("state", WORKING))
        try:
            quiet = max(float(mark.get("delay", DEFAULT_DELAY)), 0.0)
        except (TypeError, ValueError):
            quiet = DEFAULT_DELAY
        needed = quiet * (UNDECLARED_FACTOR if state == WORKING else 1)
        last = float(args.since)
        if transcript and transcript.exists():
            last = max(last, transcript.stat().st_mtime)
        now = time.time()
        if now - last >= needed:
            note = "手が止まりました" if state != WORKING else "手が止まったようです（状態は進行中のまま）"
            if state == DONE:
                note = "受け入れの条件がすべて通りました"
            delivered = deliver(args.cwd, mark, state, f"{note}。ページ：{mark.get('page', '')}")
            # The goal is over once its completion has been announced. A failed delivery keeps
            # the mark so that a later stop announces it again, and a mark that was replaced
            # while the notice was going out belongs to another goal.
            if delivered and state == DONE and (read_mark(path) or {}).get("id") == mark.get("id"):
                path.unlink(missing_ok=True)
                stamp_path(path).unlink(missing_ok=True)
            return 0 if delivered else 1
        if now - started > GIVE_UP_AFTER:
            log("expired", goal=mark.get("goal"), state=state)
            return 0
        time.sleep(min(15.0, max(0.05, needed / 4)))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    mark = commands.add_parser("mark", help="start or update notifications for this worktree's goal")
    mark.add_argument("--cwd", default=os.getcwd())
    mark.add_argument("--goal")
    mark.add_argument("--page")
    mark.add_argument("--state")
    mark.add_argument("--delay", type=float, help="seconds of quiet before a declared stop is announced (default 20); "
                      "a stop while the state is still working waits 6 times longer")
    mark.set_defaults(run=command_mark)
    clear = commands.add_parser("clear", help="stop notifications for this worktree")
    clear.add_argument("--cwd", default=os.getcwd())
    clear.set_defaults(run=command_clear)
    send = commands.add_parser("send", help="notify now, while the session keeps working")
    send.add_argument("--cwd", default=os.getcwd())
    send.add_argument("--message", required=True)
    send.set_defaults(run=command_send)
    hook = commands.add_parser("hook", help="entry point for host hooks; reads the hook JSON on stdin")
    hook.set_defaults(run=command_hook)
    after = commands.add_parser("_after")
    after.add_argument("--cwd", required=True)
    after.add_argument("--mark", required=True)
    after.add_argument("--transcript", default="")
    after.add_argument("--since", required=True)
    after.set_defaults(run=command_after)
    now = commands.add_parser("_now")
    now.add_argument("--cwd", required=True)
    now.add_argument("--goal", required=True)
    now.add_argument("--state", required=True)
    now.add_argument("--body", required=True)
    now.set_defaults(run=command_now)
    args = parser.parse_args()
    try:
        return args.run(args)
    except (OSError, subprocess.SubprocessError) as exc:
        if args.command in ("hook", "_after", "_now"):
            return 0
        print(f"waiting_notify: {exc}", file=sys.stderr)
        if isinstance(exc, PermissionError):
            print("allow the human-notify state directory for writing in this host's sandbox settings",
                  file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
