"""Local macOS human notifications; Python 3.11+, no third-party dependencies."""
import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid

if os.name != "nt":
    import fcntl
from pathlib import Path

DIALOG = '''on run argv
    display dialog (item 2 of argv) with title (item 1 of argv) buttons {"OK"} default button "OK" giving up after 60
end run'''


def run(argv, timeout=15):
    return subprocess.run(argv, capture_output=True, text=True, check=True, timeout=timeout).stdout.strip()


def locations():
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "human-notify/config.json"
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "human-notify"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    return config, state


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def identity(cwd, explicit=None):
    common = Path(run(["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"]))
    remote = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"],
                            capture_output=True, text=True).stdout.strip()
    # Strip credentials and host; retain owner/repo when origin is available.
    match = re.search(r"[/:]([^/:]+/[^/:]+?)(?:\.git)?$", remote)
    label = explicit or (match.group(1) if match else common.parent.name)
    if not label.strip():
        raise ValueError("repo label is required")
    return str(common.resolve()), label


def devices():
    output = run(["/usr/bin/say", "-a", "?"])
    result = {}
    for line in output.splitlines():
        match = re.match(r"\s*(\d+)\s+(.+?)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def deliver(request, config):
    result = {}
    # Display and speech start independently; neither waits for the other to finish.
    dialog = None
    try:
        dialog = subprocess.Popen(["/usr/bin/osascript", "-e", DIALOG,
                                   request["repo"] + "｜確認", request["body"]],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        result["screen"] = str(exc)
    try:
        available = devices()
        matches = [key for key, name in available.items() if name == config["device_name"]]
        if len(matches) != 1:
            raise ValueError("configured audio device missing or ambiguous; no default-output fallback")
        spoken = config.get("repo_names", {}).get(request["repo"], request["repo"])
        run(["/usr/bin/say", "-a", matches[0], "--", spoken + "の件です。" + request["speech"]], timeout=60)
        result["speech"] = "completed"
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        result["speech"] = str(exc)
    if dialog:
        try:
            result["screen"] = "completed" if dialog.wait(timeout=70) == 0 else "failed"
        except subprocess.TimeoutExpired:
            dialog.kill()
            dialog.wait()
            result["screen"] = "timeout"
    result["status"] = "completed" if all(v == "completed" for v in result.values()) else "partial-failure"
    result["finished_at"] = time.time()
    return result


def worker(job, state):
    try:
        request = json.loads(job.read_text())
        # One OS-held lock per user serializes dialogs and speech across repositories.
        with (state / "delivery.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = deliver(request, request["config"])
    except Exception as exc:
        result = {"status": "error", "error": str(exc), "finished_at": time.time()}
    save(job.with_suffix(".result.json"), result)
    job.unlink()  # Do not retain notification bodies after delivery.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("devices")
    setup = commands.add_parser("configure")
    setup.add_argument("--device-id", required=True)
    notify = commands.add_parser("send")
    notify.add_argument("--cwd", default=os.getcwd())
    notify.add_argument("--repo-label")
    notify.add_argument("--event", required=True)
    notify.add_argument("--revision", required=True)
    notify.add_argument("--message", required=True)
    notify.add_argument("--speech", required=True)
    notify.add_argument("--detail", required=True, help="Board path/URL or another detail reference")
    status = commands.add_parser("status")
    status.add_argument("job")
    internal = commands.add_parser("_worker")
    internal.add_argument("job")
    args = parser.parse_args()
    if platform.system() != "Darwin":
        raise ValueError("unsupported platform: macOS GUI session required; use chat notification")
    config_path, state = locations()
    if args.command == "devices":
        print(json.dumps(devices(), ensure_ascii=False))
        return
    if args.command == "configure":
        available = devices()
        if args.device_id not in available:
            raise ValueError("unknown device ID")
        config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        config.update(device_id=args.device_id, device_name=available[args.device_id])
        save(config_path, config)
        print(json.dumps({"status": "configured", "config": str(config_path)}))
        return
    if args.command == "status":
        job_id = str(uuid.UUID(args.job))
        result = state / (job_id + ".result.json")
        print(result.read_text() if result.exists() else json.dumps({"status": "pending-or-interrupted"}))
        return
    if args.command == "_worker":
        worker(state / (str(uuid.UUID(args.job)) + ".json"), state)
        return
    config = json.loads(config_path.read_text())
    if not isinstance(config.get("device_name"), str) or not isinstance(config.get("repo_names", {}), dict):
        raise ValueError("invalid device_name or repo_names configuration")
    repo_key, label = identity(args.cwd, args.repo_label)
    digest = hashlib.sha256(json.dumps([repo_key, args.event, args.revision]).encode()).hexdigest()
    with (state / "dispatch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        history = state / "history.json"
        records = json.loads(history.read_text()) if history.exists() else {}
        if digest in records:
            print(json.dumps({"status": "duplicate", "job": records[digest]}))
            return
        job_id = str(uuid.uuid4())
        job = state / (job_id + ".json")
        save(job, {"repo": label, "body": args.message + "\n" + args.detail,
                   "speech": args.speech, "config": config})
        try:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_worker", job_id],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            job.unlink()
            raise
        records[digest] = job_id
        save(history, records)
        print(json.dumps({"status": "started", "job": job_id, "pid": child.pid}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)
