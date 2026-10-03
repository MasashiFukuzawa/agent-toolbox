import hashlib
import json
from pathlib import Path

import pytest

from scripts.verify_scan_baseline import verify


def test_baseline_requires_unchanged_source_and_exact_rules(tmp_path: Path):
    skill = tmp_path / "skill"
    skill.mkdir()
    source = skill / "test.ts"
    source.write_text("owned temporary fixture cleanup")
    data = {
        "version": 1,
        "rules": [],
        "fingerprints": [{"hash": "sha256:0123456789abcdef", "file": "test.ts", "reason": "Reviewed"}],
        "source_sha256": {"test.ts": hashlib.sha256(source.read_bytes()).hexdigest()},
    }
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(data))
    verify(skill, baseline)
    source.write_text("changed cleanup")
    with pytest.raises(ValueError, match="changed"):
        verify(skill, baseline)
    source.write_text("owned temporary fixture cleanup")
    data["rules"] = [{"rule_id": "TM1"}]
    baseline.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="exact"):
        verify(skill, baseline)


def test_baseline_rejects_unbound_and_external_source(tmp_path: Path):
    skill = tmp_path / "skill"
    skill.mkdir()
    outside = tmp_path / "outside.ts"
    outside.write_text("outside")
    data = {
        "version": 1,
        "rules": [],
        "fingerprints": [{"hash": "sha256:0123456789abcdef", "file": "../outside.ts", "reason": "Reviewed"}],
        "source_sha256": {},
    }
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="binding"):
        verify(skill, baseline)
    data["source_sha256"] = {"../outside.ts": hashlib.sha256(outside.read_bytes()).hexdigest()}
    baseline.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="escapes"):
        verify(skill, baseline)
