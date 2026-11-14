"""Keep executable guidance from duplicating the shared model catalog."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins/toolbox/skills"
SECOND_OPINION = SKILLS / "second-opinion"


def test_review_launch_guidance_uses_shared_selection():
    catalog = (SKILLS / "model-selection/references/models.md").read_text()
    models = re.findall(r"`((?:gpt|claude)-[a-z0-9.-]+)`", catalog)
    assert models
    instructions = (SECOND_OPINION / "SKILL.md").read_text()
    assert "model-selection" in instructions
    assert not any(model in instructions for model in models)
    for provider in ("claude", "codex"):
        launch = (SECOND_OPINION / f"references/{provider}.md").read_text()
        assert "$REVIEW_MODEL" in launch
        assert "$REVIEW_EFFORT" in launch
        assert not any(model in launch for model in models)
    cases = json.loads((SECOND_OPINION / "evals/evals.json").read_text())["evals"]
    for case in cases:
        assert not re.search(r"(?:gpt-\d|claude-(?:sonnet|opus|fable)-\d)", case["expected_output"])
