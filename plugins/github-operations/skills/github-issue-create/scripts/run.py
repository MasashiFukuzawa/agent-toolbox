#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def plugin_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        manifests = (candidate / ".codex-plugin/plugin.json", candidate / ".claude-plugin/plugin.json")
        runtime = candidate / "lib/github_operations/__init__.py"
        if runtime.is_file() and any(_manifest_matches(path) for path in manifests):
            return candidate
    raise SystemExit("github-operations plugin runtime not found; install the complete github-operations plugin")


def _manifest_matches(path: Path) -> bool:
    try:
        return json.loads(path.read_text()).get("name") == "github-operations"
    except (OSError, json.JSONDecodeError):
        return False


if tuple(sys.version_info[:2]) < (3, 11):
    raise SystemExit("github-operations requires Python 3.11 or newer")
root = plugin_root()
sys.path.insert(0, str(root / "lib"))
from github_operations.cli import main  # noqa: E402

raise SystemExit(main("issue"))
