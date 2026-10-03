"""Fail closed when a reviewed scanner exception no longer matches its source."""

import hashlib
import json
import sys
from pathlib import Path


def verify(skill: Path, baseline: Path) -> None:
    data = json.loads(baseline.read_text())
    if data.get("version") != 1 or data.get("rules"):
        raise ValueError("Only version 1 exact finding fingerprints are allowed")
    fingerprints = data["fingerprints"]
    files = {finding["file"] for finding in fingerprints}
    hashes = data["source_sha256"]
    if not fingerprints or files != set(hashes):
        raise ValueError("Every suppressed finding must have a source binding")
    root = skill.resolve(strict=True)
    for name, digest in hashes.items():
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Baseline source escapes the skill directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Review scanner exception again: {name} changed")
    for finding in fingerprints:
        if not finding.get("reason") or not finding["hash"].startswith("sha256:"):
            raise ValueError("Each fingerprint needs a hash and review reason")


if __name__ == "__main__":
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
