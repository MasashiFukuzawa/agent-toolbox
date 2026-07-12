from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import Plan
from .safety import SafetyError, atomic_write_json, digest


def state_root() -> Path:
    base = os.environ.get("XDG_STATE_HOME")
    return Path(base).expanduser() / "github-operations" if base else Path.home() / ".local/state/github-operations"


def plan_path(plan_id: str) -> Path:
    return state_root() / "plans" / f"{plan_id}.json"


def journal_path(plan_id: str) -> Path:
    return state_root() / "journals" / f"{plan_id}.json"


def save_plan(plan: Plan) -> None:
    atomic_write_json(plan_path(plan.plan_id), plan.to_dict())


def load_plan(plan_id: str) -> dict:
    path = plan_path(plan_id)
    try:
        plan = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError(f"plan not found or invalid: {plan_id}") from exc
    required = {
        "schema_version",
        "plan_id",
        "domain",
        "action",
        "created_at",
        "expires_at",
        "identity",
        "target",
        "config_path",
        "config_digest",
        "observed_digest",
        "observed",
        "request",
        "operations",
    }
    if set(plan) != required or plan.get("schema_version") != 1 or plan.get("plan_id") != plan_id:
        raise SafetyError("plan schema or identifier is invalid")
    content = dict(plan)
    content.pop("plan_id")
    if digest(content)[:32] != plan_id:
        raise SafetyError("plan content changed after approval; create and approve a new plan")
    expires_at = datetime.fromisoformat(plan["expires_at"])
    if datetime.now(UTC) > expires_at:
        raise SafetyError("plan expired; create and approve a new plan")
    return plan


def save_journal(plan_id: str, value: dict) -> None:
    value["schema_version"] = 1
    value["plan_id"] = plan_id
    atomic_write_json(journal_path(plan_id), value)


def load_journal(plan_id: str) -> dict:
    path = journal_path(plan_id)
    if not path.exists():
        return {}
    try:
        journal = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError(f"journal is invalid: {plan_id}") from exc
    allowed = {
        "schema_version",
        "plan_id",
        "steps",
        "issue_url",
        "item_id",
        "project_id",
        "project_number",
    }
    if set(journal) - allowed or journal.get("schema_version") != 1 or journal.get("plan_id") != plan_id:
        raise SafetyError("journal schema or plan binding is invalid")
    if not isinstance(journal.get("steps", []), list) or not all(
        isinstance(step, str) for step in journal.get("steps", [])
    ):
        raise SafetyError("journal steps are invalid")
    for key in ("issue_url", "item_id", "project_id"):
        if key in journal and not isinstance(journal[key], str):
            raise SafetyError(f"journal field is invalid: {key}")
    if "project_number" in journal and not isinstance(journal["project_number"], int):
        raise SafetyError("journal field is invalid: project_number")
    return journal


def cleanup_old_journals(days: int = 30) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    directory = state_root() / "journals"
    if not directory.exists():
        return
    for path in directory.glob("*.json"):
        modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        if modified < cutoff:
            path.unlink(missing_ok=True)


def clear_stale_lock(target: str) -> Path:
    safe_name = target.replace("/", "_").replace(":", "_")
    path = state_root() / "locks" / f"{safe_name}.lock"
    if not path.exists():
        raise SafetyError(f"lock does not exist: {path}")
    try:
        first_line = path.read_text().splitlines()[0]
        pid = int(first_line.removeprefix("pid="))
    except (OSError, ValueError, IndexError) as exc:
        raise SafetyError(f"lock metadata is invalid; inspect manually: {path}") from exc
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        path.unlink()
        return path
    except PermissionError as exc:
        raise SafetyError(f"cannot verify lock owner process {pid}; leave the lock in place") from exc
    raise SafetyError(f"lock owner process is still running: pid={pid}")


@contextmanager
def exclusive_lock(target: str) -> Iterator[None]:
    locks = state_root() / "locks"
    locks.mkdir(parents=True, exist_ok=True, mode=0o700)
    safe_name = target.replace("/", "_").replace(":", "_")
    path = locks / f"{safe_name}.lock"
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise SafetyError(f"another apply is active or left a stale lock: {path}") from exc
    try:
        os.write(fd, f"pid={os.getpid()}\nstarted={datetime.now(UTC).isoformat()}\n".encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)
