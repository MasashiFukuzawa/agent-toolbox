"""Behavioral contracts from the agreed local notification design."""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def notify():
    path = Path("plugins/toolbox/skills/human-notify/scripts/human_notify.py")
    spec = importlib.util.spec_from_file_location("human_notify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_worktrees_share_identity_and_other_repos_do_not(notify, tmp_path):
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Example", "-c",
                    "user.email=" + "example" + chr(64) + "example.test", "commit", "--allow-empty", "-m", "Initial"],
                   check=True, capture_output=True)
    tree = tmp_path / "tree"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-b", "test", str(tree)],
                   check=True, capture_output=True)
    other = tmp_path / "other"
    subprocess.run(["git", "init", str(other)], check=True, capture_output=True)
    assert notify.identity(str(repo)) == notify.identity(str(tree))
    assert notify.identity(str(repo))[0] != notify.identity(str(other))[0]


def test_missing_speaker_still_displays_without_speech_fallback(notify, monkeypatch):
    calls = []

    class Dialog:
        def __init__(self, argv, **kwargs):
            calls.append(argv)

        def wait(self, timeout):
            return 0

    monkeypatch.setattr(notify.subprocess, "Popen", Dialog)
    monkeypatch.setattr(notify, "devices", lambda: {"1": "Headphones"})
    result = notify.deliver({"repo": "example/app", "body": 'Q12 "quoted"', "speech": "Q12"},
                            {"device_name": "Speakers"})
    assert result["status"] == "partial-failure"
    assert result["screen"] == "completed"
    assert len(calls) == 1
    assert calls[0][-2:] == ["example/app｜確認", 'Q12 "quoted"']
    assert "fallback" in result["speech"]


def test_repeat_send_suppresses_only_same_repo_event_revision(notify, monkeypatch, tmp_path, capsys):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"device_name": "Speakers"}))
    monkeypatch.setattr(notify, "locations", lambda: (config, tmp_path))
    monkeypatch.setattr(notify.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(notify, "identity", lambda cwd, explicit: (cwd, explicit or cwd))
    launched = []

    class Child:
        pid = 123

        def __init__(self, *args, **kwargs):
            launched.append(args)

    monkeypatch.setattr(notify.subprocess, "Popen", Child)

    def send(repo, revision):
        monkeypatch.setattr("sys.argv", ["notify", "send", "--cwd", repo, "--event", "board:Q12",
                                       "--revision", revision, "--message", "Decide", "--speech", "Q12",
                                       "--detail", "board.html"])
        notify.main()
        return json.loads(capsys.readouterr().out)

    first = send("repo-a", "1")
    assert first["status"] == "started"
    assert send("repo-a", "1") == {"status": "duplicate", "job": first["job"]}
    assert send("repo-b", "1")["status"] == "started"
    assert send("repo-a", "2")["status"] == "started"
    assert len(launched) == 3


def test_speech_uses_configured_speaker_and_repo_prefix(notify, monkeypatch):
    calls = []

    class Dialog:
        def __init__(self, *args, **kwargs):
            pass

        def wait(self, timeout):
            return 0

    monkeypatch.setattr(notify.subprocess, "Popen", Dialog)
    monkeypatch.setattr(notify, "devices", lambda: {"80": "Speakers", "90": "Headphones"})
    monkeypatch.setattr(notify, "run", lambda argv, **kwargs: calls.append(argv))
    result = notify.deliver({"repo": "example/app", "body": "Q12", "speech": "連絡板のQ12をご確認ください。"},
                            {"device_name": "Speakers"})
    assert result["status"] == "completed"
    assert calls == [["/usr/bin/say", "-a", "80", "--",
                      "example/appの件です。連絡板のQ12をご確認ください。"]]


def test_worker_error_is_observable_and_body_is_removed(notify, monkeypatch, tmp_path):
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"repo": "example/app", "body": "private", "config": {}}))

    def broken(*args):
        raise ValueError("invalid config")

    monkeypatch.setattr(notify, "deliver", broken)
    notify.worker(job, tmp_path)
    result = json.loads((tmp_path / "job.result.json").read_text())
    assert result["status"] == "error"
    assert not job.exists()
