"""Install the third-party skills listed in skills.toml at user scope with `gh skill install`.

Skills that are already installed for a host are left alone; update them with
`gh skill update`. Exits non-zero when any installation fails.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

MANIFEST = Path(__file__).resolve().with_name("skills.toml")
SKILL_DIRS = {
    "claude-code": Path(".claude/skills"),
    "codex": Path(".codex/skills"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--agent",
        action="append",
        choices=sorted(SKILL_DIRS),
        help="host to install for; repeat for several (default: all)",
    )
    args = parser.parse_args(argv)
    if shutil.which("gh") is None:
        print("gh is required: https://cli.github.com/", file=sys.stderr)
        return 1

    skills = tomllib.loads(MANIFEST.read_text())["skill"]
    home = Path.home()
    failures = []
    for agent in args.agent or sorted(SKILL_DIRS):
        for skill in skills:
            name = skill["name"]
            if (home / SKILL_DIRS[agent] / name / "SKILL.md").is_file():
                print(f"ok {agent}: {name} is already installed")
                continue
            command = ["gh", "skill", "install", skill["repository"], name, "--agent", agent, "--scope", "user"]
            if subprocess.run(command).returncode == 0:
                print(f"installed {agent}: {name}")
            else:
                failures.append(f"{agent}: {name}")

    if failures:
        print("failed: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
