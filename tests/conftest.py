import os
import stat
from pathlib import Path

import pytest


class FakeCommands:
    """Stand-ins for host commands that record each invocation instead of touching the machine."""

    def __init__(self, root: Path) -> None:
        self.bin = root / "bin"
        self.bin.mkdir()
        self.log = root / "calls.log"
        self.log.touch()

    def add(self, name: str, exit_code_script: str = "exit 0") -> None:
        path = self.bin / name
        path.write_text(f'#!/bin/sh\necho "{name} $*" >> "{self.log}"\n{exit_code_script}\n')
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def calls(self) -> list[str]:
        return self.log.read_text().splitlines()

    def env(self, home: Path) -> dict[str, str]:
        return {**os.environ, "HOME": str(home), "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}"}


@pytest.fixture
def fake_commands(tmp_path: Path) -> FakeCommands:
    return FakeCommands(tmp_path)
