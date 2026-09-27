"""Keep executable guidance from duplicating the shared model catalog."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins/toolbox/skills"


def test_review_launch_guidance_uses_shared_selection():
    catalog = (SKILLS / "model-selection/references/models.md").read_text()
    models = re.findall(r"`((?:gpt|claude)-[a-z0-9.-]+)`", catalog)
    assert models
    for name in ("claude-review", "codex-review"):
        instructions = (SKILLS / name / "SKILL.md").read_text()
        assert "model-selection" in instructions
        assert "$REVIEW_MODEL" in instructions
        assert "$REVIEW_EFFORT" in instructions
        assert not any(model in instructions for model in models)
        cases = json.loads((SKILLS / name / "evals/evals.json").read_text())["evals"]
        for case in cases:
            assert not re.search(r"(?:gpt-\d|claude-(?:sonnet|opus|fable)-\d)", case["expected_output"])
