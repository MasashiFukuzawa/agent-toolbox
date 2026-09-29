import json
import shutil
from pathlib import Path

from scripts.validate import (
    REVIEW_COMMON_BEGIN,
    REVIEW_COMMON_END,
    SEMVER,
    _validate_registry,
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


def test_plugin_release_is_only_published_in_the_codex_marketplace() -> None:
    assert (ROOT / "plugins/plugin-release/.codex-plugin/plugin.json").is_file()
    assert not (ROOT / "plugins/plugin-release/.claude-plugin/plugin.json").exists()
    codex = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    claude = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert "plugin-release" in {plugin["name"] for plugin in codex["plugins"]}
    assert "plugin-release" not in {plugin["name"] for plugin in claude["plugins"]}


def test_codex_plugin_versions_follow_semver() -> None:
    assert SEMVER.fullmatch("0.2.0+codex.20260823102630")
    assert not SEMVER.fullmatch("next")
    assert not SEMVER.fullmatch("1.2.3-01")
    assert not SEMVER.fullmatch("1١.2.3")


def test_every_published_host_manifest_has_semver_without_requiring_equal_versions() -> None:
    versions = []
    for path in (ROOT / "plugins").glob("*/.*-plugin/plugin.json"):
        version = json.loads(path.read_text())["version"]
        assert SEMVER.fullmatch(version)
        versions.append(version)
    assert versions


def test_registry_supported_hosts_must_match_host_manifests(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/trigger-registry.yml").write_text(
        "skills:\n  sample:\n    canonical_name: sample\n    supported_hosts: [codex]\n    nearest_neighbors: []\n"
    )
    plugin_dir = tmp_path / "plugins/sample"
    (plugin_dir / ".codex-plugin").mkdir(parents=True)
    (plugin_dir / ".codex-plugin/plugin.json").write_text('{"skills":"./skills/published/"}')
    (plugin_dir / "skills/sample").mkdir(parents=True)
    (plugin_dir / "skills/sample/SKILL.md").write_text("---\nname: sample\n---\n")
    (plugin_dir / "skills/published/other").mkdir(parents=True)
    (plugin_dir / "skills/published/other/SKILL.md").write_text("---\nname: other\n---\n")
    errors: list[str] = []
    _validate_registry({"sample": "description"}, errors)
    assert any("supported_hosts" in error and "plugin manifests" in error for error in errors)


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
        ("codex-review", "既定は gpt-6-luna で、昇格先は gpt-6-sol。Codex を codex exec で起動する。"),
        ("claude-review", "既定は claude-sonnet-5-5 で、昇格先は claude-opus-5-5。Claude を claude -p で起動する。"),
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
