"""Link this checkout's global instructions into each agent host and keep the checkout current.

Run it from a checkout that you only update with ``git pull --ff-only``. Every host whose
configuration directory exists gets a symlink to ``global-instructions/AGENTS.md``. A
scheduled job fast-forwards the checkout so the hosts pick up new instructions without a
manual pull. Real files are never replaced; ``--uninstall`` removes only links into this
checkout and the scheduled job.
"""

from __future__ import annotations

import argparse
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

CHECKOUT = Path(__file__).resolve().parents[1]
INSTRUCTIONS = CHECKOUT / "global-instructions" / "AGENTS.md"
JOB = "agent-toolbox.global-instructions-sync"
INTERVAL_SECONDS = 6 * 60 * 60

# Claude Code reads a project's AGENTS.md, but its user-level file is CLAUDE.md.
HOST_FILES = {
    "Claude Code": Path(".claude/CLAUDE.md"),
    "Codex": Path(".codex/AGENTS.md"),
    "Cursor": Path(".cursor/AGENTS.md"),
}


def link_hosts(home: Path) -> int:
    conflicts = 0
    for host, relative in HOST_FILES.items():
        link = home / relative
        if not link.parent.is_dir():
            print(f"skip {host}: {link.parent} does not exist")
        elif link.is_symlink() and link.resolve() == INSTRUCTIONS:
            print(f"ok {host}: {link}")
        elif link.exists() and not link.is_symlink():
            print(f"conflict {host}: {link} is a real file; back it up and remove it, then re-run", file=sys.stderr)
            conflicts += 1
        else:
            if link.is_symlink():
                link.unlink()
            link.symlink_to(INSTRUCTIONS)
            print(f"linked {host}: {link} -> {INSTRUCTIONS}")
    return conflicts


def unlink_hosts(home: Path) -> None:
    for host, relative in HOST_FILES.items():
        link = home / relative
        if link.is_symlink() and link.resolve() == INSTRUCTIONS:
            link.unlink()
            print(f"unlinked {host}: {link}")


def sync_command() -> list[str]:
    git = shutil.which("git")
    if git is None:
        raise SystemExit("git is required")
    return [git, "-C", str(CHECKOUT), "pull", "--ff-only", "--quiet"]


def launchd_plist(home: Path) -> Path:
    return home / "Library/LaunchAgents" / f"{JOB}.plist"


def install_launchd(home: Path) -> None:
    plist = launchd_plist(home)
    plist.parent.mkdir(parents=True, exist_ok=True)
    log = home / "Library/Logs" / f"{JOB}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(
        plistlib.dumps(
            {
                "Label": JOB,
                "ProgramArguments": sync_command(),
                "StartInterval": INTERVAL_SECONDS,
                "RunAtLoad": True,
                "StandardOutPath": str(log),
                "StandardErrorPath": str(log),
            }
        )
    )
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{JOB}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", domain, str(plist)], check=True)
    print(f"scheduled {JOB} with launchd: {plist}")


def uninstall_launchd(home: Path) -> None:
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{JOB}"], capture_output=True)
    launchd_plist(home).unlink(missing_ok=True)
    print(f"removed {JOB} from launchd")


def systemd_dir(home: Path) -> Path:
    return home / ".config/systemd/user"


def install_systemd(home: Path) -> None:
    unit_dir = systemd_dir(home)
    unit_dir.mkdir(parents=True, exist_ok=True)
    command = " ".join(f'"{part}"' for part in sync_command())
    (unit_dir / f"{JOB}.service").write_text(
        f"[Unit]\nDescription=Fast-forward the agent-toolbox global instructions checkout\n"
        f"[Service]\nType=oneshot\nExecStart={command}\n"
    )
    (unit_dir / f"{JOB}.timer").write_text(
        "[Unit]\nDescription=Fast-forward the agent-toolbox global instructions checkout periodically\n"
        f"[Timer]\nOnBootSec=5m\nOnUnitActiveSec={INTERVAL_SECONDS}s\nPersistent=true\n"
        "[Install]\nWantedBy=timers.target\n"
    )
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", f"{JOB}.timer"], check=True)
    print(f"scheduled {JOB} with systemd: {unit_dir}")


def uninstall_systemd(home: Path) -> None:
    subprocess.run(["systemctl", "--user", "disable", "--now", f"{JOB}.timer"], capture_output=True)
    for suffix in ("service", "timer"):
        (systemd_dir(home) / f"{JOB}.{suffix}").unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    print(f"removed {JOB} from systemd")


SCHEDULERS = {
    "launchd": (install_launchd, uninstall_launchd),
    "systemd": (install_systemd, uninstall_systemd),
}


def default_scheduler() -> str:
    if platform.system() == "Darwin":
        return "launchd"
    if shutil.which("systemctl"):
        return "systemd"
    return "none"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--uninstall", action="store_true", help="remove links into this checkout and the job")
    parser.add_argument(
        "--scheduler",
        choices=[*SCHEDULERS, "none"],
        default=default_scheduler(),
        help="how to run the periodic fast-forward (default: launchd on macOS, systemd when available, else none)",
    )
    args = parser.parse_args(argv)
    home = Path.home()

    if args.uninstall:
        unlink_hosts(home)
        if args.scheduler != "none":
            SCHEDULERS[args.scheduler][1](home)
        return 0

    conflicts = link_hosts(home)
    if args.scheduler == "none":
        print(f"no scheduler: run `git -C {CHECKOUT} pull --ff-only` to update the instructions")
    else:
        SCHEDULERS[args.scheduler][0](home)
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
