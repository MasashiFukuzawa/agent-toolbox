import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.plugin_paths import (
    git_ignored_entries,
    is_tracked_file,
    iter_public_files,
    plugin_boundary_errors,
    public_paths,
    repository_boundary_errors,
)
from scripts.validate import (
    REVIEW_COMMON_BEGIN,
    REVIEW_COMMON_END,
    SEMVER,
    _has_symlink_parent,
    _host_publishes_skill,
    _path_within_plugin,
    _plugin_boundary_errors,
    _skill_paths,
    _validate_manifests,
    _validate_markdown_links,
    _validate_registry,
    _validate_results,
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


def test_full_validation_rejects_external_skill_symlink_before_reading(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    plugin_dir = tmp_path / "plugins/sample"
    plugin_dir.mkdir(parents=True)
    external_skill = tmp_path / "external/skills/sample/SKILL.md"
    external_skill.parent.mkdir(parents=True)
    external_skill.write_bytes(b"\xff")
    (plugin_dir / "skills").symlink_to(external_skill.parent.parent, target_is_directory=True)

    errors, _warnings = validate()

    assert errors == ["plugin path escapes plugin: plugins/sample/skills"]


def test_full_validation_rejects_cyclic_skill_symlink_before_reading(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    skill = tmp_path / "plugins/sample/skills/sample/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.symlink_to(skill)

    errors, _warnings = validate()

    assert errors == ["plugin path escapes plugin: plugins/sample/skills/sample/SKILL.md"]


def test_full_validation_rejects_symlinked_plugins_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    external_plugins = tmp_path / "external/plugins"
    (external_plugins / "sample").mkdir(parents=True)
    (tmp_path / "plugins").symlink_to(external_plugins, target_is_directory=True)

    errors, _warnings = validate()

    assert errors == ["plugins directory escapes repository through a symlink"]


def test_full_validation_rejects_external_repository_symlink_before_reading(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    external = tmp_path.parent / f"{tmp_path.name}-external.yml"
    external.write_bytes(b"\xff")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "external.yml").symlink_to(external)
    (tmp_path / "plugins").mkdir()

    errors, _warnings = validate()

    assert errors == ["repository path escapes root or is unresolved: docs/external.yml"]


def test_markdown_link_validation_skips_venv_markdown_symlinks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    external = tmp_path.parent / f"{tmp_path.name}-external.md"
    external.write_text("[broken](missing.md)\n")
    venv_markdown = tmp_path / ".venv/site-packages/external.md"
    venv_markdown.parent.mkdir(parents=True)
    venv_markdown.symlink_to(external)
    errors: list[str] = []

    _validate_markdown_links(errors)

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


def test_every_published_host_manifest_uses_semver() -> None:
    versions = []
    for path in (ROOT / "plugins").glob("*/.*-plugin/plugin.json"):
        version = json.loads(path.read_text())["version"]
        assert SEMVER.fullmatch(version)
        versions.append(version)
    assert versions


@pytest.mark.parametrize("manifest_path", ["./../..", "./../other/skills"])
def test_codex_manifest_cannot_publish_skills_outside_its_plugin(tmp_path: Path, manifest_path: str) -> None:
    plugin_dir = tmp_path / "plugins/sample"
    manifest_dir = plugin_dir / ".codex-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(json.dumps({"skills": manifest_path}))
    sibling_skill = tmp_path / "plugins/other/skills/sample/SKILL.md"
    sibling_skill.parent.mkdir(parents=True)
    sibling_skill.write_text("---\nname: sample\n---\n")
    skill_dir = plugin_dir / "skills/sample"
    skill_dir.parent.mkdir(parents=True)
    skill_dir.symlink_to(sibling_skill.parent, target_is_directory=True)
    skill = skill_dir / "SKILL.md"

    assert not _host_publishes_skill(skill, "codex")


def test_codex_manifest_publishes_skill_inside_its_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins/sample"
    manifest_dir = plugin_dir / ".codex-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text('{"skills":"./skills/"}')
    skill = plugin_dir / "skills/sample/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: sample\n---\n")

    assert _host_publishes_skill(skill, "codex")


def test_codex_manifest_validator_rejects_skills_path_outside_plugin(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    plugin_dir = tmp_path / "plugins/sample"
    manifest_dir = plugin_dir / ".codex-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "sample", "version": "1.0.0", "skills": "./../other/skills"})
    )
    (tmp_path / ".agents/plugins").mkdir(parents=True)
    (tmp_path / ".agents/plugins/marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "sample", "source": {"source": "local", "path": "./plugins/sample"}}]})
    )
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text('{"plugins":[]}')

    errors: list[str] = []
    _validate_manifests(errors)

    assert any("Codex skills path escapes plugin" in error for error in errors)


def test_codex_manifest_validator_rejects_external_skill_symlink(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    plugin_dir = tmp_path / "plugins/sample"
    manifest_dir = plugin_dir / ".codex-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "sample", "version": "1.0.0", "skills": "./skills/"})
    )
    external_skill = tmp_path / "plugins/other/skills/other/SKILL.md"
    external_skill.parent.mkdir(parents=True)
    external_skill.write_text("---\nname: other\n---\n")
    skills = plugin_dir / "skills"
    skills.mkdir()
    (skills / "other").symlink_to(external_skill.parent, target_is_directory=True)
    (tmp_path / ".agents/plugins").mkdir(parents=True)
    (tmp_path / ".agents/plugins/marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "sample", "source": {"source": "local", "path": "./plugins/sample"}}]})
    )
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text('{"plugins":[]}')

    errors: list[str] = []
    _validate_manifests(errors)

    assert any("Codex skill path escapes plugin" in error for error in errors)


def test_claude_manifest_validator_rejects_external_skill_symlink(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    plugin_dir = tmp_path / "plugins/sample"
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text('{"name":"sample","version":"1.0.0"}')
    external_skill = tmp_path / "plugins/other/skills/other/SKILL.md"
    external_skill.parent.mkdir(parents=True)
    external_skill.write_text("---\nname: other\n---\n")
    skills = plugin_dir / "skills"
    skills.mkdir()
    (skills / "other").symlink_to(external_skill.parent, target_is_directory=True)
    (tmp_path / ".agents/plugins").mkdir(parents=True)
    (tmp_path / ".agents/plugins/marketplace.json").write_text('{"plugins":[]}')
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "sample", "source": "./plugins/sample"}]})
    )

    errors: list[str] = []
    _validate_manifests(errors)

    assert any("Claude skill path escapes plugin" in error for error in errors)


def test_claude_manifest_publishes_skill_inside_its_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins/sample"
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text('{"name":"sample","version":"1.0.0"}')
    skill = plugin_dir / "skills/sample/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: sample\n---\n")

    assert _host_publishes_skill(skill, "claude-code")


def test_claude_manifest_without_skills_directory_is_valid(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    manifest_dir = tmp_path / "plugins/sample/.claude-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text('{"name":"sample","version":"1.0.0"}')
    (tmp_path / ".agents/plugins").mkdir(parents=True)
    (tmp_path / ".agents/plugins/marketplace.json").write_text('{"plugins":[]}')
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text(
        '{"plugins":[{"name":"sample","source":"./plugins/sample"}]}'
    )

    errors: list[str] = []
    _validate_manifests(errors)

    assert not any("Claude skills path escapes plugin" in error for error in errors)


def test_plugin_boundary_allows_internal_resource_symlink(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    plugin_dir = tmp_path / "plugins/sample"
    resource = plugin_dir / "references/shared.md"
    resource.parent.mkdir(parents=True)
    resource.write_text("shared")
    alias = plugin_dir / "references/alias"
    alias.symlink_to("shared.md")

    assert _plugin_boundary_errors() == []


@pytest.mark.parametrize("link_kind", ["absolute", "ignored-intermediate", "linked-directory"])
def test_public_resource_link_must_directly_reference_a_relative_file(tmp_path: Path, link_kind: str) -> None:
    from scripts.plugin_paths import require_public_file

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    plugin = tmp_path / "plugins/sample"
    shared = plugin / "references/shared.md"
    shared.parent.mkdir(parents=True)
    shared.write_text("public")
    alias = plugin / "references/alias.md"
    if link_kind == "absolute":
        alias.symlink_to(shared)
    elif link_kind == "ignored-intermediate":
        (tmp_path / ".gitignore").write_text("plugins/sample/references/local.md\n")
        (shared.parent / "local.md").symlink_to("shared.md")
        alias.symlink_to("local.md")
    else:
        (tmp_path / ".gitignore").write_text("plugins/sample/local\n")
        (plugin / "local").symlink_to("references", target_is_directory=True)
        alias.symlink_to("../local/shared.md")

    assert "plugin path escapes plugin: plugins/sample/references/alias.md" in plugin_boundary_errors(tmp_path)
    with pytest.raises(ValueError, match="unsafe symlink"):
        require_public_file(tmp_path, alias)


def test_plugin_boundary_rejects_internal_directory_symlink(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    plugin_dir = tmp_path / "plugins/sample"
    resources = plugin_dir / "references/shared"
    resources.mkdir(parents=True)
    alias = plugin_dir / "references/alias"
    alias.symlink_to("shared", target_is_directory=True)

    assert _plugin_boundary_errors() == ["plugin directory symlinks are not allowed: plugins/sample/references/alias"]


def test_git_ignored_local_directory_symlinks_are_outside_publication_boundary(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".claude/\nplugins/sample/.cache/\n")
    (tmp_path / "external").mkdir()
    plugin_dir = tmp_path / "plugins/sample"
    plugin_dir.mkdir(parents=True)
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude/skills").symlink_to(plugin_dir, target_is_directory=True)
    cache_dir = plugin_dir / ".cache"
    cache_dir.mkdir()
    resource = plugin_dir / "references/shared.md"
    resource.parent.mkdir()
    resource.write_text("shared")
    (cache_dir / "shared.md").symlink_to(resource)

    assert repository_boundary_errors(tmp_path) == []
    assert plugin_boundary_errors(tmp_path) == []
    assert not any(".claude" in path.parts for path in iter_public_files(tmp_path))


def test_git_ignored_distribution_paths_are_excluded_from_skill_and_result_discovery(
    tmp_path: Path, monkeypatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("*-workspace/\nevals/results/latest.json\n")
    published_skill = tmp_path / "plugins/toolbox/skills/sample/SKILL.md"
    published_skill.parent.mkdir(parents=True)
    published_skill.write_text("---\nname: sample\ndescription: valid\n---\n")
    local_skill = tmp_path / "plugins/sample-workspace/skills/local/SKILL.md"
    local_skill.parent.mkdir(parents=True)
    local_skill.write_text("local")
    latest_result = tmp_path / "evals/results/latest.json"
    latest_result.parent.mkdir(parents=True)
    latest_result.write_text("local result")
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)

    assert [path.relative_to(tmp_path).as_posix() for path in _skill_paths()] == [
        "plugins/toolbox/skills/sample/SKILL.md"
    ]
    assert public_paths(tmp_path, list((tmp_path / "evals/results").glob("*.json"))) == []


@pytest.mark.parametrize("ignore_relative", [".gitignore", "nested/.gitignore"])
def test_git_ignore_listing_rejects_symlinked_ignore_rules_before_git_reads_them(
    tmp_path: Path, monkeypatch, ignore_relative: str
) -> None:
    import scripts.plugin_paths as plugin_paths

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    external_ignore = tmp_path.parent / f"{tmp_path.name}-external.gitignore"
    external_ignore.write_text("private/\n")
    ignore_file = tmp_path / ignore_relative
    ignore_file.parent.mkdir(parents=True, exist_ok=True)
    ignore_file.symlink_to(external_ignore)

    commands: list[list[str]] = []
    original_run = plugin_paths.subprocess.run

    def record_git_command(command, *args, **kwargs):
        commands.append(list(command))
        return original_run(command, *args, **kwargs)

    monkeypatch.setattr(plugin_paths.subprocess, "run", record_git_command)

    with pytest.raises(ValueError, match="ignore rules file is a symlink"):
        plugin_paths.git_ignored_entries(tmp_path)

    # Index-only tracking probes do not load ignore rules; enumeration must wait.
    assert all("--others" not in command for command in commands)


def test_git_ignored_directory_does_not_load_nested_ignore_rules(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("scratch/\n")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / ".gitignore").symlink_to(tmp_path / "missing-rules")
    public_file = tmp_path / "public.md"
    public_file.write_text("public")

    assert repository_boundary_errors(tmp_path) == []
    assert public_file in list(iter_public_files(tmp_path))


def test_tracked_directory_still_checks_nested_ignore_rules(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("shared/\n")
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "public.md").write_text("public")
    subprocess.run(["git", "add", "-f", "shared/public.md"], cwd=tmp_path, check=True)
    (shared / ".gitignore").symlink_to(tmp_path / "missing-rules")

    assert any("ignore rules file is a symlink" in error for error in repository_boundary_errors(tmp_path))


def test_broken_git_metadata_symlink_is_not_treated_as_a_non_git_copy(tmp_path: Path) -> None:
    from scripts.plugin_paths import is_tracked_file

    (tmp_path / ".git").symlink_to(tmp_path / "missing-git-metadata", target_is_directory=True)

    with pytest.raises(ValueError, match="cannot determine Git-ignored paths"):
        git_ignored_entries(tmp_path)
    with pytest.raises(ValueError, match="cannot verify Git tracking status"):
        is_tracked_file(tmp_path, tmp_path / "evals/results/baseline.json")


def test_public_plugin_symlink_cannot_target_git_ignored_file(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("plugins/sample/private.md\n")
    plugin_dir = tmp_path / "plugins/sample"
    (plugin_dir / "skills/local").mkdir(parents=True)
    ignored_target = plugin_dir / "private.md"
    ignored_target.write_text("local-only skill contents")
    skill = plugin_dir / "skills/local/SKILL.md"
    skill.symlink_to("../../private.md")

    assert plugin_boundary_errors(tmp_path) == [
        "plugin symlink targets ignored content: plugins/sample/skills/local/SKILL.md"
    ]


@pytest.mark.parametrize("initialize_git", [False, True])
def test_ignored_directory_symlink_is_excluded_from_skill_discovery(
    tmp_path: Path, initialize_git: bool
) -> None:
    if initialize_git:
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("plugins/sample/skills/alias\n")
    plugin_skills = tmp_path / "plugins/sample/skills"
    plugin_skills.mkdir(parents=True)
    external_skill = tmp_path / "external/alias/SKILL.md"
    external_skill.parent.mkdir(parents=True)
    external_skill.write_text("local-only skill")
    (plugin_skills / "alias").symlink_to(external_skill.parent, target_is_directory=True)

    assert plugin_boundary_errors(tmp_path) == []
    assert public_paths(tmp_path, list(plugin_skills.glob("*/SKILL.md"))) == []


def test_non_git_public_discovery_excludes_local_state(tmp_path: Path) -> None:
    from scripts.plugin_paths import require_public_file

    (tmp_path / ".gitignore").write_text(
        "*-workspace/\nplugins/**/private-drafts/\nevals/results/latest.json\n"
    )
    (tmp_path / ".claude/skills/local").mkdir(parents=True)
    (tmp_path / ".claude/skills/local/SKILL.md").write_text("private")
    workspace_skill = tmp_path / "plugins/sample-workspace/skills/local/SKILL.md"
    workspace_skill.parent.mkdir(parents=True)
    workspace_skill.write_text("private")
    latest = tmp_path / "evals/results/latest.json"
    latest.parent.mkdir(parents=True)
    latest.write_text("private")
    ignored_skill = tmp_path / "plugins/toolbox/skills/private-drafts/SKILL.md"
    ignored_skill.parent.mkdir(parents=True)
    ignored_skill.write_text("private draft")

    assert public_paths(
        tmp_path,
        [tmp_path / ".claude/skills/local/SKILL.md", workspace_skill, latest, ignored_skill],
    ) == []
    assert not any(path.relative_to(tmp_path).parts[0] == ".claude" for path in iter_public_files(tmp_path))
    with pytest.raises(ValueError, match="ignored"):
        require_public_file(tmp_path, latest)


def test_non_git_ignore_does_not_read_rules_below_ignored_directories(tmp_path: Path) -> None:
    from scripts.plugin_paths import require_public_file

    (tmp_path / ".gitignore").write_text("private/\n")
    ignored_dir = tmp_path / "plugins/toolbox/skills/private"
    ignored_dir.mkdir(parents=True)
    (ignored_dir / ".gitignore").write_text("!secret/SKILL.md\n")
    secret_skill = ignored_dir / "secret/SKILL.md"
    secret_skill.parent.mkdir()
    secret_skill.write_text("private")

    with pytest.raises(ValueError, match="ignored"):
        require_public_file(tmp_path, secret_skill)


def test_non_git_required_file_rejects_symlink_before_reading_external_ignore_rules(
    tmp_path: Path, monkeypatch
) -> None:
    import scripts.plugin_paths as plugin_paths

    external = tmp_path.parent / f"{tmp_path.name}-external"
    external.mkdir()
    external_ignore = external / ".gitignore"
    external_ignore.write_text("secret.md\n")
    (external / "secret.md").write_text("private")
    (tmp_path / "alias").symlink_to(external, target_is_directory=True)

    read_ignore_paths: list[Path] = []
    original = plugin_paths._fallback_gitignore_spec

    def record_ignore_read(path: Path):
        read_ignore_paths.append(path)
        return original(path)

    monkeypatch.setattr(plugin_paths, "_fallback_gitignore_spec", record_ignore_read)

    with pytest.raises(ValueError, match="escapes root"):
        plugin_paths.require_public_file(tmp_path, tmp_path / "alias/secret.md")

    assert external_ignore not in read_ignore_paths


def test_non_git_ignore_rules_reject_symlink_before_reading_target(tmp_path: Path, monkeypatch) -> None:
    import scripts.plugin_paths as plugin_paths

    external_ignore = tmp_path.parent / f"{tmp_path.name}-external.gitignore"
    external_ignore.write_bytes(b"\xff")
    ignore_file = tmp_path / ".gitignore"
    ignore_file.symlink_to(external_ignore)

    read_paths: list[Path] = []
    original_read_text = Path.read_text

    def record_read(path: Path, *args, **kwargs):
        read_paths.append(path)
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", record_read)

    with pytest.raises(ValueError, match="ignore rules file is a symlink"):
        plugin_paths.require_public_file(tmp_path, tmp_path / "required.json")

    assert external_ignore not in read_paths


def test_non_git_nested_ignore_can_unignore_parent_directory(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("a/b/\n")
    nested = tmp_path / "a"
    nested.mkdir()
    (nested / ".gitignore").write_text("!b/\n")
    public_file = nested / "b/public.md"
    public_file.parent.mkdir()
    public_file.write_text("public")

    assert public_paths(tmp_path, [public_file]) == [public_file]


def test_non_git_directory_only_pattern_excludes_the_directory(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("build/\n")
    build_dir = tmp_path / "plugins/toolbox/build"
    build_dir.mkdir(parents=True)
    public_file = build_dir / "output.json"
    public_file.write_text("local")

    assert public_paths(tmp_path, [build_dir]) == []
    assert public_paths(tmp_path, [public_file]) == []


@pytest.mark.parametrize("initialize_git", [False, True])
def test_directory_only_ignore_does_not_hide_directory_symlink(tmp_path: Path, initialize_git: bool) -> None:
    if initialize_git:
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("plugins/sample/skills/alias/\n")
    plugin_skills = tmp_path / "plugins/sample/skills"
    plugin_skills.mkdir(parents=True)
    external = tmp_path.parent / f"{tmp_path.name}-external"
    external.mkdir()
    (plugin_skills / "alias").symlink_to(external, target_is_directory=True)

    assert "plugin path escapes plugin: plugins/sample/skills/alias" in plugin_boundary_errors(tmp_path)


def test_non_git_nested_ignore_can_unignore_file_in_visible_directory(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*.md\n")
    skills_dir = tmp_path / "plugins/toolbox/skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / ".gitignore").write_text("!keep.md\n")
    kept = skills_dir / "keep.md"
    kept.write_text("public")

    assert public_paths(tmp_path, [kept]) == [kept]


def test_non_git_public_paths_do_not_hide_unignored_workspaces_directory(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("evals/workspaces/\n*-workspace/\n")
    public_file = tmp_path / "plugins/toolbox/skills/sample/references/workspaces/guide.md"
    public_file.parent.mkdir(parents=True)
    public_file.write_text("public")

    assert public_paths(tmp_path, [public_file]) == [public_file]


def test_git_metadata_is_always_outside_the_publication_boundary(tmp_path: Path) -> None:
    from scripts.plugin_paths import require_public_file

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    docs = tmp_path / "docs"
    docs.mkdir()
    link = docs / "config.md"
    link.symlink_to("../.git/config")

    assert any("repository symlink targets ignored content: docs/config.md" in error
               for error in repository_boundary_errors(tmp_path))
    with pytest.raises(ValueError, match="ignored"):
        require_public_file(tmp_path, tmp_path / ".git/config")


@pytest.mark.parametrize("initialize_git", [False, True])
def test_nested_git_metadata_is_never_public(tmp_path: Path, initialize_git: bool) -> None:
    from scripts.plugin_paths import require_public_file

    if initialize_git:
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    nested_config = tmp_path / "plugins/sample/vendor/.git/config"
    nested_config.parent.mkdir(parents=True)
    nested_config.write_text("[remote]\nurl = private\n")

    assert nested_config not in list(iter_public_files(tmp_path))
    assert public_paths(tmp_path, [nested_config]) == []
    with pytest.raises(ValueError, match="ignored"):
        require_public_file(tmp_path, nested_config)


def test_tracked_shared_files_in_local_root_directories_are_still_scanned(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    shared_file = tmp_path / ".claude/settings.json"
    shared_file.parent.mkdir(parents=True)
    shared_file.write_text('{"shared": true}')
    subprocess.run(["git", "add", ".claude/settings.json"], cwd=tmp_path, check=True)

    assert public_paths(tmp_path, [shared_file]) == [shared_file]
    assert shared_file in list(iter_public_files(tmp_path))


def test_required_public_file_handles_root_symlink_alias(tmp_path: Path) -> None:
    from scripts.plugin_paths import require_public_file

    public_file = tmp_path / "docs/public.md"
    public_file.parent.mkdir()
    public_file.write_text("public")
    ignored_file = tmp_path / "evals/results/latest.json"
    ignored_file.parent.mkdir(parents=True)
    ignored_file.write_text("local")
    (tmp_path / ".gitignore").write_text("evals/results/latest.json\n")
    root_alias = tmp_path.parent / f"{tmp_path.name}-alias"
    root_alias.symlink_to(tmp_path, target_is_directory=True)
    aliased_file = root_alias / "docs/public.md"
    aliased_ignored_file = root_alias / "evals/results/latest.json"

    assert require_public_file(root_alias, aliased_file) == public_file.resolve()
    assert public_paths(root_alias, [aliased_ignored_file]) == []
    assert _has_symlink_parent(tmp_path.resolve(), aliased_file)


def test_required_public_file_rejects_parent_traversal(tmp_path: Path) -> None:
    from scripts.plugin_paths import require_public_file

    latest = tmp_path / "evals/results/latest.json"
    latest.parent.mkdir(parents=True)
    latest.write_text("private")
    (tmp_path / ".gitignore").write_text("evals/results/latest.json\n")

    with pytest.raises(ValueError, match="parent traversal"):
        require_public_file(tmp_path, tmp_path / "evals/x/../results/latest.json")


def test_tracked_gitignored_files_remain_public_for_validation(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("plugins/sample/private.md\n")
    private = tmp_path / "plugins/sample/private.md"
    private.parent.mkdir(parents=True)
    private.write_text("private")
    subprocess.run(["git", "add", ".gitignore"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-f", "plugins/sample/private.md"], cwd=tmp_path, check=True)

    ignored_files, _ignored_dirs = git_ignored_entries(tmp_path)
    assert Path("plugins/sample/private.md") not in ignored_files
    assert public_paths(tmp_path, [private]) == [private]


def test_git_public_discovery_ignores_user_global_and_info_excludes(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    global_excludes = tmp_path / "global-excludes"
    global_excludes.write_text("plugins/sample/global.md\n")
    subprocess.run(["git", "config", "core.excludesFile", str(global_excludes)], cwd=tmp_path, check=True)
    (tmp_path / ".git/info/exclude").write_text("plugins/sample/info.md\n")
    global_file = tmp_path / "plugins/sample/global.md"
    info_file = tmp_path / "plugins/sample/info.md"
    global_file.parent.mkdir(parents=True)
    global_file.write_text("public")
    info_file.write_text("public")

    assert public_paths(tmp_path, [global_file, info_file]) == [global_file, info_file]


def test_git_ignore_enumeration_failure_is_not_treated_as_empty(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    original_run = subprocess.run

    def fail_ls_files(args, **kwargs):
        if args[:2] == ["git", "ls-files"]:
            return subprocess.CompletedProcess(args, 2, stdout=b"", stderr=b"broken index")
        return original_run(args, **kwargs)

    monkeypatch.setattr("scripts.plugin_paths.subprocess.run", fail_ls_files)
    with pytest.raises(ValueError, match="cannot determine Git-ignored paths"):
        git_ignored_entries(tmp_path)


def test_git_tracking_probe_treats_glob_characters_as_literal(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    tracked = tmp_path / "plugins/sample/cache0/kept.md"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("public")
    subprocess.run(["git", "add", "plugins/sample/cache0/kept.md"], cwd=tmp_path, check=True)

    assert is_tracked_file(tmp_path, tmp_path / "plugins/sample/cache[0]/missing.md") is False


def test_invalid_non_git_ignore_file_fails_closed(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_bytes(b"\xff")

    errors = repository_boundary_errors(tmp_path)

    assert any("cannot read ignore rules" in error for error in errors)


def test_git_root_tracking_failure_does_not_skip_baseline_check(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    original_run = subprocess.run

    def fail_rev_parse(args, **kwargs):
        if args[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return subprocess.CompletedProcess(args, 128, stdout="", stderr="safe.directory denied")
        return original_run(args, **kwargs)

    monkeypatch.setattr("scripts.plugin_paths.subprocess.run", fail_rev_parse)
    with pytest.raises(ValueError, match="git rev-parse failed"):
        git_ignored_entries(tmp_path)
    with pytest.raises(ValueError, match="cannot verify Git tracking status"):
        is_tracked_file(tmp_path, tmp_path / "evals/results/baseline.json")


def test_manifest_symlink_is_rejected_even_when_parent_is_git_ignored(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    plugin_dir = tmp_path / "plugins/sample"
    manifest_dir = plugin_dir / ".codex-plugin"
    manifest_dir.mkdir(parents=True)
    (tmp_path / ".gitignore").write_text("plugins/sample/.codex-plugin/\n")
    external_manifest = tmp_path / "external/plugin.json"
    external_manifest.parent.mkdir(parents=True)
    external_manifest.write_bytes(b"\xff")
    (manifest_dir / "plugin.json").symlink_to(external_manifest)
    claude_manifest = plugin_dir / ".claude-plugin/plugin.json"
    claude_manifest.parent.mkdir(parents=True)
    claude_manifest.write_text('{"name":"sample","version":"1.0.0"}')
    (tmp_path / ".agents/plugins").mkdir(parents=True)
    (tmp_path / ".agents/plugins/marketplace.json").write_text('{"plugins":[]}')
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text(
        '{"plugins":[{"name":"sample","source":"./plugins/sample"}]}'
    )

    errors: list[str] = []
    _validate_manifests(errors)

    assert not any("manifest" in error for error in errors)


def test_manifest_inside_ignored_symlinked_parent_is_not_read(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    (tmp_path / ".gitignore").write_text("plugins/sample/.codex-plugin/\n")
    plugin_dir = tmp_path / "plugins/sample"
    external_manifest_dir = tmp_path / "external/.codex-plugin"
    external_manifest_dir.mkdir(parents=True)
    (external_manifest_dir / "plugin.json").write_bytes(b"not JSON")
    (plugin_dir / ".codex-plugin").parent.mkdir(parents=True)
    (plugin_dir / ".codex-plugin").symlink_to(external_manifest_dir, target_is_directory=True)
    claude_manifest = plugin_dir / ".claude-plugin/plugin.json"
    claude_manifest.parent.mkdir(parents=True)
    claude_manifest.write_text('{"name":"sample","version":"1.0.0"}')
    (tmp_path / ".agents/plugins").mkdir(parents=True)
    (tmp_path / ".agents/plugins/marketplace.json").write_text('{"plugins":[]}')
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text(
        '{"plugins":[{"name":"sample","source":"./plugins/sample"}]}'
    )

    errors: list[str] = []
    _validate_manifests(errors)

    assert "manifest path traverses a symlink: plugins/sample/.codex-plugin/plugin.json" in errors


def test_full_validation_rejects_repository_directory_symlink_to_ancestor(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "loop").symlink_to(".", target_is_directory=True)
    (tmp_path / "plugins").mkdir()

    errors, _warnings = validate()

    assert errors == ["repository directory symlinks are not allowed: docs/loop"]


def test_plugin_root_symlink_is_outside_its_own_boundary(tmp_path: Path) -> None:
    external_plugin = tmp_path / "external/sample"
    external_plugin.mkdir(parents=True)
    plugin_dir = tmp_path / "plugins/sample"
    plugin_dir.parent.mkdir(parents=True)
    plugin_dir.symlink_to(external_plugin, target_is_directory=True)

    assert _path_within_plugin(plugin_dir, external_plugin / "skills") is None


def test_manifest_validator_rejects_symlinked_plugin_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    external_plugin = tmp_path / "external/sample"
    manifest_dir = external_plugin / ".codex-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "sample", "version": "1.0.0", "skills": "./skills/"})
    )
    skill = external_plugin / "skills/sample/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: sample\n---\n")
    plugin_dir = tmp_path / "plugins/sample"
    plugin_dir.parent.mkdir(parents=True)
    plugin_dir.symlink_to(external_plugin, target_is_directory=True)
    (tmp_path / ".agents/plugins").mkdir(parents=True)
    (tmp_path / ".agents/plugins/marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "sample", "source": {"source": "local", "path": "./plugins/sample"}}]})
    )
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text('{"plugins":[]}')

    errors: list[str] = []
    _validate_manifests(errors)

    assert errors == ["plugin entry must not be a symlink: plugins/sample"]


def test_manifest_validator_rejects_symlinked_plugins_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    external_plugins = tmp_path / "external/plugins"
    plugin_dir = external_plugins / "sample"
    manifest_dir = plugin_dir / ".codex-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "sample", "version": "1.0.0", "skills": "./skills/"})
    )
    skill = plugin_dir / "skills/sample/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("---\nname: sample\n---\n")
    (tmp_path / "plugins").symlink_to(external_plugins, target_is_directory=True)
    (tmp_path / ".agents/plugins").mkdir(parents=True)
    (tmp_path / ".agents/plugins/marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "sample", "source": {"source": "local", "path": "./plugins/sample"}}]})
    )
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text('{"plugins":[]}')

    errors: list[str] = []
    _validate_manifests(errors)

    assert errors == ["plugins directory escapes repository through a symlink"]


def test_cyclic_symlink_is_reported_as_outside_the_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins/sample"
    loop = plugin_dir / "skills/loop"
    loop.parent.mkdir(parents=True)
    loop.symlink_to(loop, target_is_directory=True)

    assert _path_within_plugin(plugin_dir, loop / "SKILL.md") is None


def test_publication_check_rejects_cyclic_skill_file_symlink(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugins/sample"
    manifest_dir = plugin_dir / ".codex-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text('{"skills":"./skills/"}')
    skill = plugin_dir / "skills/sample/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.symlink_to(skill)

    assert not _host_publishes_skill(skill, "codex")


def test_manifest_validator_reports_cyclic_skill_symlink(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    plugin_dir = tmp_path / "plugins/sample"
    manifest_dir = plugin_dir / ".codex-plugin"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "sample", "version": "1.0.0", "skills": "./skills/"})
    )
    loop = plugin_dir / "skills/loop"
    loop.parent.mkdir()
    loop.symlink_to(loop, target_is_directory=True)
    (tmp_path / ".agents/plugins").mkdir(parents=True)
    (tmp_path / ".agents/plugins/marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "sample", "source": {"source": "local", "path": "./plugins/sample"}}]})
    )
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin/marketplace.json").write_text('{"plugins":[]}')

    errors: list[str] = []
    _validate_manifests(errors)

    assert any("Codex skills path has no skills" in error for error in errors)


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


def test_nearest_neighbor_must_support_every_host_of_the_skill(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/trigger-registry.yml").write_text(
        "skills:\n"
        "  sample:\n"
        "    canonical_name: sample\n"
        "    supported_hosts: [codex]\n"
        "    nearest_neighbors: [neighbor]\n"
        "  neighbor:\n"
        "    canonical_name: neighbor\n"
        "    supported_hosts: [claude-code]\n"
        "    nearest_neighbors: []\n"
    )
    sample = tmp_path / "plugins/sample"
    (sample / ".codex-plugin").mkdir(parents=True)
    (sample / ".codex-plugin/plugin.json").write_text('{"skills":"./skills/"}')
    (sample / "skills/sample").mkdir(parents=True)
    (sample / "skills/sample/SKILL.md").write_text("---\nname: sample\n---\n")
    neighbor = tmp_path / "plugins/neighbor"
    (neighbor / ".claude-plugin").mkdir(parents=True)
    (neighbor / ".claude-plugin/plugin.json").write_text("{}")
    (neighbor / "skills/neighbor").mkdir(parents=True)
    (neighbor / "skills/neighbor/SKILL.md").write_text("---\nname: neighbor\n---\n")
    errors: list[str] = []
    _validate_registry({"sample": "", "neighbor": ""}, errors)
    assert any("nearest neighbor neighbor from sample lacks required hosts" in error for error in errors)


def test_registry_reports_neighbor_missing_from_registry_without_crashing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/trigger-registry.yml").write_text(
        "skills:\n  source:\n    canonical_name: source\n"
        "    supported_hosts: [codex]\n    nearest_neighbors: [neighbor]\n"
    )
    errors: list[str] = []
    _validate_registry({"source": "", "neighbor": ""}, errors)
    assert any("neighbor neighbor from source is missing from the trigger registry" in error for error in errors)


def test_trigger_result_documents_are_checked_against_published_schema(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)
    (tmp_path / "evals/results").mkdir(parents=True)
    (tmp_path / "evals/result-schema.json").write_bytes((ROOT / "evals/result-schema.json").read_bytes())
    (tmp_path / "evals/results/baseline.json").write_bytes((ROOT / "evals/results/baseline.json").read_bytes())
    valid_document = {
        "schema_version": 1,
        "matrix_sha256": "0" * 64,
        "summary": {"total": 1, "passed": 1, "failed": 0, "not_run": 0},
        "results": [
            {
                "host": "codex",
                "environment": "isolated",
                "skill": "sample",
                "type": "positive",
                "case_id": 1,
                "status": "passed",
            }
        ],
    }
    (tmp_path / "evals/results/valid.json").write_text(json.dumps(valid_document))
    errors: list[str] = []
    _validate_results(errors)
    assert errors == []

    invalid_documents = []
    invalid = copy.deepcopy(valid_document)
    invalid["results"][0]["skill"] = {}
    invalid_documents.append(invalid)
    invalid = copy.deepcopy(valid_document)
    invalid["results"][0]["skill"] = ""
    invalid_documents.append(invalid)
    invalid = copy.deepcopy(valid_document)
    invalid["results"][0]["type"] = "unregistered"
    invalid_documents.append(invalid)
    invalid = copy.deepcopy(valid_document)
    invalid["results"][0]["case_id"] = {}
    invalid_documents.append(invalid)
    invalid = copy.deepcopy(valid_document)
    invalid["results"][0]["case_id"] = 0
    invalid_documents.append(invalid)
    invalid = copy.deepcopy(valid_document)
    invalid["results"][0]["unexpected"] = True
    invalid_documents.append(invalid)
    invalid = copy.deepcopy(valid_document)
    invalid["summary"]["unexpected"] = True
    invalid_documents.append(invalid)
    invalid = copy.deepcopy(valid_document)
    invalid["unexpected"] = True
    invalid_documents.append(invalid)
    invalid = copy.deepcopy(valid_document)
    invalid["matrix_sha256"] = "not-a-digest"
    invalid_documents.append(invalid)
    invalid = copy.deepcopy(valid_document)
    invalid["generated_at"] = "yesterday"
    invalid_documents.append(invalid)
    invalid = copy.deepcopy(valid_document)
    invalid["summary"]["total"] = -1
    invalid_documents.append(invalid)

    for document in invalid_documents:
        (tmp_path / "evals/results/invalid.json").write_text(json.dumps(document))
        errors = []
        _validate_results(errors)
        assert any("trigger result schema mismatch" in error for error in errors)


def test_trigger_baseline_is_required_and_cannot_be_ignored(tmp_path: Path, monkeypatch) -> None:
    missing_root = tmp_path / "missing"
    (missing_root / "evals/results").mkdir(parents=True)
    (missing_root / "evals/result-schema.json").write_bytes((ROOT / "evals/result-schema.json").read_bytes())
    monkeypatch.setattr("scripts.validate.ROOT", missing_root)

    errors: list[str] = []
    _validate_results(errors)
    assert any("required trigger baseline is missing or ignored" in error for error in errors)


def test_git_trigger_baseline_must_be_tracked(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "evals/results").mkdir(parents=True)
    (tmp_path / "evals/result-schema.json").write_bytes((ROOT / "evals/result-schema.json").read_bytes())
    (tmp_path / "evals/results/baseline.json").write_bytes((ROOT / "evals/results/baseline.json").read_bytes())
    monkeypatch.setattr("scripts.validate.ROOT", tmp_path)

    errors: list[str] = []
    _validate_results(errors)

    assert any("required trigger baseline is not tracked by Git" in error for error in errors)

    ignored_root = tmp_path / "ignored"
    (ignored_root / "evals/results").mkdir(parents=True)
    (ignored_root / "evals/result-schema.json").write_bytes((ROOT / "evals/result-schema.json").read_bytes())
    (ignored_root / ".gitignore").write_text("evals/results/baseline.json\n")
    baseline = ignored_root / "evals/results/baseline.json"
    baseline.write_bytes((ROOT / "evals/results/baseline.json").read_bytes())
    monkeypatch.setattr("scripts.validate.ROOT", ignored_root)
    errors = []
    _validate_results(errors)
    assert any("required trigger baseline is missing or ignored" in error for error in errors)


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
        ("codex-review", "既定は gpt-6.1-sol で、昇格先は gpt-6-astra。Codex を codex exec で起動する。"),
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
