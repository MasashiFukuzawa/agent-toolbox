import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "recommended-skills/install.py"
SKILLS = tomllib.loads((ROOT / "recommended-skills/skills.toml").read_text())["skill"]


def _install(fake_commands, home: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER)], env=fake_commands.env(home), capture_output=True, text=True
    )


def test_every_recommended_skill_is_installed_for_each_host_at_user_scope(fake_commands, tmp_path):
    fake_commands.add("gh")

    result = _install(fake_commands, tmp_path / "home")

    assert result.returncode == 0, result.stderr
    assert sorted(fake_commands.calls()) == sorted(
        f"gh skill install {skill['repository']} {skill['name']} --agent {agent} --scope user"
        for skill in SKILLS
        for agent in ("claude-code", "codex")
    )


def test_an_installed_skill_is_left_for_gh_skill_update(fake_commands, tmp_path):
    fake_commands.add("gh")
    home = tmp_path / "home"
    installed = home / ".codex/skills" / SKILLS[0]["name"]
    installed.mkdir(parents=True)
    (installed / "SKILL.md").write_text("locally reviewed copy")

    result = _install(fake_commands, home)

    assert result.returncode == 0, result.stderr
    assert not [call for call in fake_commands.calls() if f"{SKILLS[0]['name']} --agent codex" in call]
    assert (installed / "SKILL.md").read_text() == "locally reviewed copy"


def test_a_failed_install_is_reported_without_skipping_the_rest(fake_commands, tmp_path):
    failing = SKILLS[0]["name"]
    fake_commands.add("gh", f'case "$*" in *" {failing} "*) exit 1;; esac')

    result = _install(fake_commands, tmp_path / "home")

    assert result.returncode == 1
    assert failing in result.stderr
    assert len(fake_commands.calls()) == 2 * len(SKILLS)
