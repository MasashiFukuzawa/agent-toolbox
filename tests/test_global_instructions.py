import plistlib
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMITTER = ("-c", "user.name=t", "-c", "user.email=test", "-c", "commit.gpgsign=false")
JOB = "agent-toolbox.global-instructions-sync"
HOST_FILES = (".claude/CLAUDE.md", ".codex/AGENTS.md", ".cursor/AGENTS.md")

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """A published repository and a clone where the author lands new instructions."""
    author = tmp_path / "author"
    (author / "global-instructions").mkdir(parents=True)
    shutil.copy(ROOT / "global-instructions/install.py", author / "global-instructions/install.py")
    (author / "global-instructions/AGENTS.md").write_text("v1\n")
    _git("init", "-q", "-b", "main", cwd=author)
    _git("add", ".", cwd=author)
    _git(*COMMITTER, "commit", "-qm", "v1", cwd=author)
    _git("clone", "-q", "--bare", str(author), str(tmp_path / "published.git"), cwd=tmp_path)
    _git("remote", "add", "origin", str(tmp_path / "published.git"), cwd=author)
    return author


def _publish(author: Path, text: str) -> None:
    (author / "global-instructions/AGENTS.md").write_text(text)
    _git(*COMMITTER, "commit", "-qam", text.strip(), cwd=author)
    _git("push", "-q", "origin", "main", cwd=author)


@pytest.fixture
def checkout(upstream: Path, tmp_path: Path) -> Path:
    path = tmp_path / "checkout"
    _git("clone", "-q", str(tmp_path / "published.git"), str(path), cwd=tmp_path)
    return path


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "home"
    for relative in HOST_FILES:
        (path / relative).parent.mkdir(parents=True)
    return path


def _install(checkout: Path, fake_commands, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    for command in ("launchctl", "systemctl"):
        fake_commands.add(command)
    return subprocess.run(
        [sys.executable, str(checkout / "global-instructions/install.py"), *args],
        env=fake_commands.env(home),
        capture_output=True,
        text=True,
    )


def test_every_host_reads_newly_published_instructions_after_the_launchd_job_runs(
    upstream, checkout, fake_commands, home
):
    result = _install(checkout, fake_commands, home, "--scheduler", "launchd")
    assert result.returncode == 0, result.stderr
    plist = home / f"Library/LaunchAgents/{JOB}.plist"
    assert any(call.startswith("launchctl bootstrap") and str(plist) in call for call in fake_commands.calls())

    _publish(upstream, "v2\n")
    job = plistlib.loads(plist.read_bytes())
    subprocess.run(job["ProgramArguments"], check=True)

    assert [(home / relative).read_text() for relative in HOST_FILES] == ["v2\n"] * 3


def test_the_systemd_timer_runs_a_sync_that_publishes_new_instructions(upstream, checkout, fake_commands, home):
    result = _install(checkout, fake_commands, home, "--scheduler", "systemd")
    assert result.returncode == 0, result.stderr
    assert f"systemctl --user enable --now {JOB}.timer" in fake_commands.calls()

    _publish(upstream, "v2\n")
    service = (home / f".config/systemd/user/{JOB}.service").read_text()
    exec_start = next(line for line in service.splitlines() if line.startswith("ExecStart="))
    subprocess.run(shlex.split(exec_start.removeprefix("ExecStart=")), check=True)

    assert (home / ".codex/AGENTS.md").read_text() == "v2\n"


def test_a_real_instruction_file_is_never_replaced(checkout, fake_commands, home):
    personal = home / ".codex/AGENTS.md"
    personal.write_text("my own instructions\n")

    result = _install(checkout, fake_commands, home, "--scheduler", "none")

    assert result.returncode == 1
    assert not personal.is_symlink() and personal.read_text() == "my own instructions\n"
    assert [(home / relative).read_text() for relative in (".claude/CLAUDE.md", ".cursor/AGENTS.md")] == ["v1\n"] * 2


def test_a_host_that_is_not_installed_is_left_untouched(checkout, fake_commands, home):
    shutil.rmtree(home / ".cursor")

    result = _install(checkout, fake_commands, home, "--scheduler", "none")

    assert result.returncode == 0, result.stderr
    assert not (home / ".cursor").exists()


def test_a_link_to_another_checkout_is_repointed_here(checkout, fake_commands, home, tmp_path):
    old = tmp_path / "old-checkout/AGENTS.md"
    old.parent.mkdir()
    old.write_text("stale\n")
    (home / ".claude/CLAUDE.md").symlink_to(old)

    _install(checkout, fake_commands, home, "--scheduler", "none")

    assert (home / ".claude/CLAUDE.md").read_text() == "v1\n"


def test_uninstall_removes_only_this_checkouts_links_and_job(checkout, fake_commands, home, tmp_path):
    _install(checkout, fake_commands, home, "--scheduler", "launchd")
    elsewhere = tmp_path / "elsewhere.md"
    elsewhere.write_text("other\n")
    (home / ".codex/AGENTS.md").unlink()
    (home / ".codex/AGENTS.md").symlink_to(elsewhere)

    result = _install(checkout, fake_commands, home, "--uninstall", "--scheduler", "launchd")

    assert result.returncode == 0, result.stderr
    assert not (home / ".claude/CLAUDE.md").exists() and not (home / ".cursor/AGENTS.md").exists()
    assert (home / ".codex/AGENTS.md").read_text() == "other\n"
    assert not (home / f"Library/LaunchAgents/{JOB}.plist").exists()
    assert any(call.startswith("launchctl bootout") and JOB in call for call in fake_commands.calls())
