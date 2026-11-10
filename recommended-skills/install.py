"""Vet the third-party skills listed in skills.toml and install those that pass at user scope.

Each skill is fetched from its upstream repository with `gh skill install --dir` into a
temporary directory and scanned with the SkillSpector release pinned in tooling/skillspector.
Only skills that pass are copied into each host's user skill directory, replacing an older
copy. Re-run it to pick up upstream changes; do not use `gh skill update`, which skips the
scan. `--scan-only` fetches and scans without installing. Exits non-zero when any skill fails.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[1]
MANIFEST = CHECKOUT / "recommended-skills" / "skills.toml"
SCANNER = CHECKOUT / "tooling" / "skillspector"
SKILL_DIRS = {
    "claude-code": Path(".claude/skills"),
    "codex": Path(".codex/skills"),
}


def fetch(skill: dict[str, str], workdir: Path) -> Path | None:
    command = ["gh", "skill", "install", skill["repository"], skill["name"], "--dir", str(workdir)]
    subprocess.run(command, capture_output=True, text=True)
    fetched = workdir / skill["name"]
    return fetched if (fetched / "SKILL.md").is_file() else None


def scan(skill_dir: Path, report: Path) -> bool:
    command = ["uv", "run", "--quiet", "--project", str(SCANNER), "--locked", "skillspector", "scan"]
    command += ["--format", "json", "--output", str(report), "--no-llm", str(skill_dir)]
    if subprocess.run(command, capture_output=True, text=True).returncode == 0:
        return True
    try:
        result = json.loads(report.read_text())
    except (OSError, ValueError):
        print("  SkillSpector did not produce a report", file=sys.stderr)
        return False
    print(f"  {result.get('risk_assessment')}", file=sys.stderr)
    blocking = {
        f"  {issue.get('id')} {issue.get('pattern')}: {(issue.get('location') or {}).get('file')}"
        for issue in result.get("issues", [])
        if issue.get("severity") in ("HIGH", "CRITICAL")
    }
    print("\n".join(sorted(blocking)), file=sys.stderr)
    return False


def same_tree(left: Path, right: Path) -> bool:
    comparison = filecmp.dircmp(left, right, ignore=[])
    if comparison.left_only or comparison.right_only or comparison.funny_files:
        return False
    _, mismatch, errors = filecmp.cmpfiles(left, right, comparison.common_files, shallow=False)
    return not mismatch and not errors and all(same_tree(left / d, right / d) for d in comparison.common_dirs)


def place(source: Path, destination: Path) -> str:
    if destination.is_symlink():
        raise FileExistsError(f"{destination} is a symlink; remove it to let this script manage the skill")
    if destination.is_dir():
        if same_tree(source, destination):
            return "up to date"
        shutil.rmtree(destination)
        status = "updated"
    else:
        status = "installed"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--agent",
        action="append",
        choices=sorted(SKILL_DIRS),
        help="host to install for; repeat for several (default: all)",
    )
    parser.add_argument("--scan-only", action="store_true", help="fetch and scan every skill without installing")
    args = parser.parse_args(argv)
    for tool, url in (("gh", "https://cli.github.com/"), ("uv", "https://docs.astral.sh/uv/")):
        if shutil.which(tool) is None:
            print(f"{tool} is required: {url}", file=sys.stderr)
            return 1

    skills = tomllib.loads(MANIFEST.read_text())["skill"]
    home = Path.home()
    failures = []
    for skill in skills:
        name = skill["name"]
        with tempfile.TemporaryDirectory() as workdir:
            fetched = fetch(skill, Path(workdir) / "skills")
            if fetched is None:
                print(f"failed {name}: could not fetch it from {skill['repository']}", file=sys.stderr)
                failures.append(name)
                continue
            if not scan(fetched, Path(workdir) / "report.json"):
                print(f"blocked {name}: SkillSpector rejected it; nothing was installed", file=sys.stderr)
                failures.append(name)
                continue
            if args.scan_only:
                print(f"passed {name}")
                continue
            for agent in args.agent or sorted(SKILL_DIRS):
                try:
                    print(f"{place(fetched, home / SKILL_DIRS[agent] / name)} {agent}: {name}")
                except FileExistsError as error:
                    print(f"failed {agent}: {error}", file=sys.stderr)
                    failures.append(f"{agent}: {name}")

    if failures:
        print("failed: " + ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
