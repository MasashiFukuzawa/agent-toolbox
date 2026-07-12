from pathlib import Path

from scripts.validate import validate

ROOT = Path(__file__).resolve().parents[1]


def test_repository_contracts() -> None:
    errors, _warnings = validate()
    assert errors == []


def test_done_documentation_is_inside_plugin_distribution() -> None:
    skill = (ROOT / "plugins/done/skills/done/SKILL.md").read_text()
    assert (ROOT / "plugins/done/examples/done.yml").is_file()
    assert (ROOT / "plugins/done/schema/done.schema.json").is_file()
    assert "../../examples/done.yml" in skill
    assert "../../schema/done.schema.json" in skill


def test_trigger_baseline_covers_every_registered_case() -> None:
    errors, _warnings = validate()
    assert "baseline trigger result is stale or incomplete" not in errors


def test_semantic_evaluation_matches_current_skill() -> None:
    errors, _warnings = validate()
    assert not any("semantic evaluation" in error for error in errors)
