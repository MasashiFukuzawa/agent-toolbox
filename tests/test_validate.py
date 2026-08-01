import shutil
from pathlib import Path

from scripts.validate import (
    REVIEW_COMMON_BEGIN,
    REVIEW_COMMON_END,
    _validate_review_common_mirror,
    _validate_review_mirror,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
REVIEW_SKILLS = ("codex-review", "claude-review")


def _copy_review_skills(tmp_path: Path) -> Path:
    for skill in REVIEW_SKILLS:
        source = ROOT / "plugins/toolbox/skills" / skill
        target = tmp_path / "plugins/toolbox/skills" / skill
        target.mkdir(parents=True)
        shutil.copy(source / "SKILL.md", target / "SKILL.md")
        (target / "references").mkdir()
        shutil.copy(
            source / "references/review-snapshot.md",
            target / "references/review-snapshot.md",
        )
    return tmp_path


def test_repository_contracts() -> None:
    errors, _warnings = validate()
    assert errors == []


def test_done_documentation_is_inside_plugin_distribution() -> None:
    skill = (ROOT / "plugins/done/skills/done/SKILL.md").read_text()
    assert (ROOT / "plugins/done/skills/done/references/done.example.yml").is_file()
    assert (ROOT / "plugins/done/skills/done/references/done.schema.json").is_file()
    assert "references/done.example.yml" in skill
    assert "references/done.schema.json" in skill
    assert "../../" not in skill


def test_trigger_baseline_covers_every_registered_case() -> None:
    errors, _warnings = validate()
    assert "baseline trigger result is stale or incomplete" not in errors


def test_semantic_evaluation_matches_current_skill() -> None:
    errors, _warnings = validate()
    assert not any("semantic evaluation" in error for error in errors)


def test_skill_local_openai_metadata_is_not_published() -> None:
    assert list(ROOT.glob("plugins/*/skills/*/agents/openai.yaml")) == []


def test_review_mirrors_pass_on_current_repository() -> None:
    errors: list[str] = []
    _validate_review_mirror(errors)
    _validate_review_common_mirror(errors)
    assert errors == []


def test_review_common_mirror_normalizes_provider_tokens(tmp_path: Path) -> None:
    root = _copy_review_skills(tmp_path)
    for skill, sentence in (
        ("codex-review", "既定は gpt-5.6-terra で、昇格先は gpt-5.6-sol。Codex を codex exec で起動する。"),
        ("claude-review", "既定は claude-sonnet-5 で、昇格先は claude-opus-5。Claude を claude -p で起動する。"),
    ):
        path = root / "plugins/toolbox/skills" / skill / "SKILL.md"
        path.write_text(
            path.read_text() + f"\n{REVIEW_COMMON_BEGIN}\n{sentence}\n{REVIEW_COMMON_END}\n"
        )
    errors: list[str] = []
    _validate_review_common_mirror(errors, root=root)
    assert errors == []


def test_review_common_mirror_detects_single_character_drift(tmp_path: Path) -> None:
    root = _copy_review_skills(tmp_path)
    path = root / "plugins/toolbox/skills/claude-review/SKILL.md"
    text = path.read_text()
    start = text.index(REVIEW_COMMON_BEGIN) + len(REVIEW_COMMON_BEGIN)
    body_index = text.index("レビュー", start)
    path.write_text(text[:body_index] + "改" + text[body_index + 1 :])
    errors: list[str] = []
    _validate_review_common_mirror(errors, root=root)
    assert any("differs after" in error for error in errors)


def test_review_common_mirror_requires_markers(tmp_path: Path) -> None:
    root = _copy_review_skills(tmp_path)
    path = root / "plugins/toolbox/skills/codex-review/SKILL.md"
    text = path.read_text().replace(REVIEW_COMMON_BEGIN, "").replace(REVIEW_COMMON_END, "")
    path.write_text(text)
    errors: list[str] = []
    _validate_review_common_mirror(errors, root=root)
    assert any("markers not found" in error for error in errors)


def test_review_common_mirror_rejects_block_count_mismatch(tmp_path: Path) -> None:
    root = _copy_review_skills(tmp_path)
    path = root / "plugins/toolbox/skills/codex-review/SKILL.md"
    path.write_text(path.read_text() + f"\n{REVIEW_COMMON_BEGIN}\nextra\n{REVIEW_COMMON_END}\n")
    errors: list[str] = []
    _validate_review_common_mirror(errors, root=root)
    assert any("block count differs" in error for error in errors)


def test_review_common_mirror_rejects_unbalanced_markers(tmp_path: Path) -> None:
    root = _copy_review_skills(tmp_path)
    path = root / "plugins/toolbox/skills/claude-review/SKILL.md"
    path.write_text(path.read_text() + f"\n{REVIEW_COMMON_BEGIN}\nunclosed\n")
    errors: list[str] = []
    _validate_review_common_mirror(errors, root=root)
    assert any("unbalanced" in error for error in errors)
