#!/usr/bin/env python3
"""Validate skills, manifests, skill evaluation files, and public-content boundaries."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml

from scripts.plugin_paths import (
    iter_public_files,
    plugin_boundary_errors,
    plugin_path_within,
    public_paths,
    repository_boundary_errors,
    require_public_file,
)

ROOT = Path(__file__).resolve().parents[1]
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
SEMVER_IDENTIFIER = r"(?:0|[1-9][0-9]*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    rf"(?:-{SEMVER_IDENTIFIER}(?:\.{SEMVER_IDENTIFIER})*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z"
)
REPO_SKILL_DIR = ".agents/skills"
CLAUDE_REPO_SKILL_DIR = ".claude/skills"


def validate() -> tuple[list[str], list[str]]:
    """Stop before reading repository content if a symlink escapes or is unresolved."""
    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(_repository_boundary_errors())
    errors.extend(_plugin_boundary_errors())
    if errors:
        return errors, warnings

    for path in [*_skill_paths(), *_repo_skill_paths()]:
        _validate_skill_file(path, errors, warnings)
    _validate_repo_skill_mirror(errors)

    # No catalog-wide total cap: per-skill bounds above govern residency cost,
    # and a total cap couples unrelated skills (adding one forces trimming
    # another). See docs/skill-conventions.md "Description budget".
    _validate_manifests(errors)
    _validate_skill_evals(errors)
    _scan_public_content(errors)
    _validate_markdown_links(errors)
    return errors, warnings


EXPLICIT_ONLY_KEY = "disable-model-invocation"
EXPLICIT_ONLY_CODEX_METADATA = {"policy": {"allow_implicit_invocation": False}}


def _validate_explicit_only(path: Path, metadata: dict, errors: list[str]) -> None:
    """Explicit-only skills must opt out of implicit invocation on both hosts, and nothing else."""
    relative = path.relative_to(ROOT)
    claude_opt_out = EXPLICIT_ONLY_KEY in metadata
    if claude_opt_out and metadata[EXPLICIT_ONLY_KEY] is not True:
        errors.append(f"{EXPLICIT_ONLY_KEY} must be true when present: {relative}")
    codex_path = path.parent / "agents/openai.yaml"
    codex_opt_out = codex_path.exists()
    if codex_opt_out:
        try:
            codex_metadata = yaml.safe_load(require_public_file(ROOT, codex_path).read_text())
        except (OSError, ValueError, yaml.YAMLError) as exc:
            errors.append(f"invalid agents/openai.yaml: {relative.parent}: {exc}")
            return
        if codex_metadata != EXPLICIT_ONLY_CODEX_METADATA:
            errors.append(
                f"agents/openai.yaml may only set policy.allow_implicit_invocation: false: {relative.parent}"
            )
    if claude_opt_out != codex_opt_out:
        errors.append(
            f"explicit-only skills need both {EXPLICIT_ONLY_KEY}: true and agents/openai.yaml: {relative.parent}"
        )


def _validate_skill_file(path: Path, errors: list[str], warnings: list[str]) -> str | None:
    try:
        text = require_public_file(ROOT, path).read_text()
    except (OSError, ValueError) as exc:
        errors.append(f"cannot read public skill {path.relative_to(ROOT)}: {exc}")
        return None
    match = FRONTMATTER.match(text)
    if not match:
        errors.append(f"missing frontmatter: {path.relative_to(ROOT)}")
        return None
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        errors.append(f"invalid YAML: {path.relative_to(ROOT)}: {exc}")
        return None
    name = path.parent.name
    keys = set(metadata or {})
    if keys not in ({"name", "description"}, {"name", "description", EXPLICIT_ONLY_KEY}):
        errors.append(
            f"frontmatter keys must be name, description (and optionally {EXPLICIT_ONLY_KEY}): "
            f"{path.relative_to(ROOT)}"
        )
    _validate_explicit_only(path, metadata or {}, errors)
    if metadata.get("name") != name:
        errors.append(f"name/directory mismatch: {path.relative_to(ROOT)}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        errors.append(f"invalid kebab-case name: {name}")
    description = str(metadata.get("description", ""))
    if len(description) > 500:
        errors.append(f"description exceeds 500 chars: {name}")
    if len(description) < 120:
        errors.append(f"description is below 120-char target: {name}")
    if len(description) > 300:
        warnings.append(f"description exceeds 300-char warning: {name}")
    sentences = [part for part in re.split(r"[。！？]", description) if part]
    positive = re.search(
        r"(?:時|依頼|場合|前|障害|検証|確認|調査|レビュー|参照|開発|実装).*使う|正のトリガー", description
    )
    negative = re.search(r"使わない|には.+を使う|なら.+を使う|限定する|限定し", description)
    if len(sentences) < 3 or not positive or not negative:
        errors.append(f"description must express purpose, trigger, and negative boundary: {name}")
    if not re.search(r"^description:\s*>-\s*$", match.group(1), re.MULTILINE):
        errors.append(f"description should use folded scalar: {name}")
    if len(text.splitlines()) > 500:
        errors.append(f"SKILL.md exceeds 500 lines: {name}")
    return description


def _repo_skill_paths() -> list[Path]:
    """Repository-local skills: Codex reads `.agents/skills`, Claude Code reads `.claude/skills`."""
    return sorted(public_paths(ROOT, list(ROOT.glob(f"{REPO_SKILL_DIR}/*/SKILL.md"))))


def _validate_repo_skill_mirror(errors: list[str]) -> None:
    """Each repository-local skill is a file in `.agents/skills` linked from `.claude/skills`."""
    sources = {path.parent.name: path for path in _repo_skill_paths()}
    links = {
        path.parent.name: path
        for path in public_paths(ROOT, list(ROOT.glob(f"{CLAUDE_REPO_SKILL_DIR}/*/SKILL.md")))
    }
    for name in sorted(set(sources) | set(links)):
        source, link = sources.get(name), links.get(name)
        if link is None:
            errors.append(f"repo skill {name} needs a {CLAUDE_REPO_SKILL_DIR}/{name}/SKILL.md symlink")
        elif source is None or not link.is_symlink() or link.resolve() != source.resolve():
            errors.append(f"{link.relative_to(ROOT)} must be a symlink to {REPO_SKILL_DIR}/{name}/SKILL.md")


def _repository_boundary_errors() -> list[str]:
    return repository_boundary_errors(ROOT)


def _plugin_boundary_errors() -> list[str]:
    return plugin_boundary_errors(ROOT)


def _skill_paths() -> list[Path]:
    return sorted(public_paths(ROOT, list(ROOT.glob("plugins/*/skills/*/SKILL.md"))))


def _validate_manifests(errors: list[str]) -> None:
    plugins_root = ROOT / "plugins"
    if plugins_root.is_symlink():
        errors.append("plugins directory escapes repository through a symlink")
        return
    plugin_dirs = sorted(path for path in public_paths(ROOT, list((ROOT / "plugins").iterdir())) if path.is_dir())
    if any(path.is_symlink() for path in plugin_dirs):
        errors.extend(_plugin_boundary_errors())
        return
    host_names = {"Codex": [], "Claude": []}
    for plugin_dir in plugin_dirs:
        found_manifest = False
        present_hosts: set[str] = set()
        for host, directory in (("Codex", ".codex-plugin"), ("Claude", ".claude-plugin")):
            path = plugin_dir / directory / "plugin.json"
            if _has_symlink_parent(plugin_dir, path):
                errors.append(f"manifest path traverses a symlink: {path.relative_to(ROOT)}")
                continue
            if not public_paths(ROOT, [path]):
                continue
            if path.is_symlink():
                errors.append(f"manifest must not be a symlink: {path.relative_to(ROOT)}")
                continue
            if not path.is_file():
                continue
            if _path_within_plugin(plugin_dir, path) is None:
                errors.append(f"manifest path escapes plugin: {path.relative_to(ROOT)}")
                continue
            found_manifest = True
            present_hosts.add(host)
            try:
                manifest = json.loads(require_public_file(ROOT, path).read_text())
                if manifest.get("name") != plugin_dir.name:
                    errors.append(f"manifest name mismatch: {path.relative_to(ROOT)}")
                version = manifest.get("version")
                if not isinstance(version, str) or not SEMVER.fullmatch(version):
                    errors.append(f"{host} manifest has invalid SemVer version: {path.relative_to(ROOT)}")
                if host == "Codex":
                    skill_paths = manifest.get("skills")
                    if isinstance(skill_paths, str):
                        skill_paths = [skill_paths]
                    if not isinstance(skill_paths, list) or not skill_paths or not all(
                        isinstance(skill_path, str) and skill_path.startswith("./") for skill_path in skill_paths
                    ):
                        errors.append(f"Codex manifest has invalid skills path: {path.relative_to(ROOT)}")
                    else:
                        for skill_path in skill_paths:
                            target = _codex_skill_root(plugin_dir, skill_path)
                            if target is None:
                                lexical_target = (plugin_dir / skill_path).resolve(strict=False)
                                try:
                                    lexical_target.relative_to(plugin_dir.resolve())
                                except ValueError:
                                    errors.append(f"Codex skills path escapes plugin: {path.relative_to(ROOT)}")
                                else:
                                    errors.append(f"Codex skills path has no skills: {path.relative_to(ROOT)}")
                                continue
                            discovered_skills = (
                                public_paths(ROOT, list(target.glob("*/SKILL.md"))) if target.is_dir() else []
                            )
                            if not discovered_skills:
                                errors.append(f"Codex skills path has no skills: {path.relative_to(ROOT)}")
                            elif any(_path_within_plugin(plugin_dir, skill) is None for skill in discovered_skills):
                                errors.append(f"Codex skill path escapes plugin: {path.relative_to(ROOT)}")
                else:
                    skills_path = plugin_dir / "skills"
                    target = _path_within_plugin(plugin_dir, skills_path) if skills_path.exists() else None
                    if skills_path.exists() and target is None:
                        errors.append(f"Claude skills path escapes plugin: {path.relative_to(ROOT)}")
                    elif target is not None and target.is_dir() and any(
                        _path_within_plugin(plugin_dir, skill) is None
                        for skill in public_paths(ROOT, list(target.glob("*/SKILL.md")))
                    ):
                        errors.append(f"Claude skill path escapes plugin: {path.relative_to(ROOT)}")
                host_names[host].append(plugin_dir.name)
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"invalid or missing manifest {path.relative_to(ROOT)}: {exc}")
        if not found_manifest:
            errors.append(f"plugin has no host manifest: {plugin_dir.relative_to(ROOT)}")
        else:
            # Every plugin ships for both hosts; a manifest dropped on one side would
            # otherwise pass, because each marketplace is only compared with its own host.
            errors.extend(
                f"plugin is missing its {host} manifest: {plugin_dir.relative_to(ROOT)}"
                for host in ("Codex", "Claude")
                if host not in present_hosts
            )
    pairs = (
        (ROOT / ".agents/plugins/marketplace.json", "Codex"),
        (ROOT / ".claude-plugin/marketplace.json", "Claude"),
    )
    for path, host in pairs:
        try:
            entries = json.loads(require_public_file(ROOT, path).read_text())["plugins"]
            names = sorted(item["name"] for item in entries)
            if names != sorted(host_names[host]):
                errors.append(f"{host} marketplace/plugin drift")
            source_paths = {item["name"]: _marketplace_source_path(item, host) for item in entries}
            expected_paths = {name: f"./plugins/{name}" for name in host_names[host]}
            if source_paths != expected_paths:
                errors.append(f"{host} marketplace source path drift")
        except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid {host} marketplace manifest: {exc}")

    for metadata_path in public_paths(ROOT, list(ROOT.glob("plugins/*/skills/*/agents/openai.yaml"))):
        if not (metadata_path.parent.parent / "SKILL.md").is_file():
            errors.append(f"agents/openai.yaml has no sibling skill: {metadata_path.relative_to(ROOT)}")


def _marketplace_source_path(entry: dict, host: str) -> str | None:
    source = entry.get("source")
    if host == "Codex" and isinstance(source, dict) and source.get("source") == "local":
        path = source.get("path")
        return path if isinstance(path, str) else None
    if host == "Claude" and isinstance(source, str):
        return source
    return None


def _validate_skill_evals(errors: list[str]) -> None:
    eval_paths = [*ROOT.glob("plugins/*/skills/*/evals/evals.json"), *ROOT.glob(f"{REPO_SKILL_DIR}/*/evals/evals.json")]
    for path in public_paths(ROOT, eval_paths):
        try:
            document = json.loads(require_public_file(ROOT, path).read_text())
            expected_name = path.parents[1].name
            if document["skill_name"] != expected_name:
                errors.append(f"eval skill_name mismatch: {path.relative_to(ROOT)}")
            for case in document["evals"]:
                if not {"id", "prompt", "expected_output"} <= set(case):
                    errors.append(f"incomplete eval case: {path.relative_to(ROOT)}")
        except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid skill eval {path.relative_to(ROOT)}: {exc}")
    for path in public_paths(ROOT, list(ROOT.glob("plugins/*/skills/*/evals/semantic-results.json"))):
        try:
            result = json.loads(require_public_file(ROOT, path).read_text())
            skill_path = path.parents[1] / "SKILL.md"
            evals_path = path.parent / "evals.json"
            safe_skill_path = require_public_file(ROOT, skill_path)
            safe_evals_path = require_public_file(ROOT, evals_path)
            skill_hash = hashlib.sha256(safe_skill_path.read_bytes()).hexdigest()
            evals_hash = hashlib.sha256(safe_evals_path.read_bytes()).hexdigest()
            if result["skill_sha256"] != skill_hash or result["evals_sha256"] != evals_hash:
                errors.append(f"stale semantic evaluation: {path.relative_to(ROOT)}")
            evals = json.loads(safe_evals_path.read_text())["evals"]
            expected = {case["id"]: len(case.get("assertions", [])) for case in evals}
            for executor in result["executors"]:
                if executor["status"] == "passed":
                    actual = {case["id"]: len(case["assertions"]) for case in executor["cases"]}
                    if actual != expected or not all(
                        case["passed"] and all(case["assertions"]) for case in executor["cases"]
                    ):
                        errors.append(f"incomplete semantic evaluation: {path.relative_to(ROOT)}")
                elif executor["status"] == "not_run" and not executor.get("reason"):
                    errors.append(f"semantic evaluation skip needs reason: {path.relative_to(ROOT)}")
        except (OSError, KeyError, TypeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid semantic evaluation {path.relative_to(ROOT)}: {exc}")


def _codex_skill_root(plugin_dir: Path, relative: object) -> Path | None:
    if not isinstance(relative, str) or not relative.startswith("./"):
        return None
    return _path_within_plugin(plugin_dir, plugin_dir / relative)


def _path_within_plugin(plugin_dir: Path, path: Path) -> Path | None:
    return plugin_path_within(ROOT, plugin_dir, path)


def _has_symlink_parent(root: Path, path: Path) -> bool:
    parent = path.parent
    while parent != root.parent:
        if parent.is_symlink():
            return True
        if parent == parent.parent:
            return False
        parent = parent.parent
    return False


def _scan_public_content(errors: list[str]) -> None:
    banned = {
        "absolute macOS home path": re.compile(r"/Users/[^/\s]+/"),
        "email address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
        "legacy license/source marker": re.compile(
            r"everything-claude-code|cloudflare-starterkit|\bMIT License\b", re.I
        ),
        "removed skill reference": re.compile(
            r"worktree-flow|write-meaningful-tests|documentation-lookup|research-first"
            r"|technical-research|structured-text-parsing|cloudflare-worker-cd"
            r"|daily-plan|owner-board"
            # `done` is also an ordinary word, so only the forms that point at the retired skill.
            r"|`done`|done(?:を|に|が|で|へ|の担当|スキル| skill| plugin|@)|(?:なら|には|は)done"
        ),
    }
    exclusions = {
        ROOT / "scripts/validate.py",
        ROOT / "tests/test_validate.py",
        ROOT / "docs/skill-conventions.md",
        ROOT / "CHANGELOG.md",  # history has to name what was removed
    }
    for path in iter_public_files(ROOT):
        if _is_root_excluded(path):
            continue
        if path == Path(__file__).resolve():
            continue
        try:
            content = require_public_file(ROOT, path).read_text()
        except UnicodeDecodeError:
            continue
        for label, pattern in banned.items():
            if label == "removed skill reference" and path in exclusions:
                continue
            if pattern.search(content):
                errors.append(f"{label}: {path.relative_to(ROOT)}")
    if any(path.name == "case-study.md" for path in iter_public_files(ROOT)):
        errors.append("private case study must not be published")


def _validate_markdown_links(errors: list[str]) -> None:
    """Reject dangling local Markdown links without trying to validate external URLs."""
    link_pattern = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
    skill_roots = {path.parent for path in [*_skill_paths(), *_repo_skill_paths()]}
    for path in iter_public_files(ROOT, ".md"):
        if _is_root_excluded(path):
            continue
        try:
            content = require_public_file(ROOT, path).read_text()
        except (OSError, ValueError) as exc:
            errors.append(f"cannot read public Markdown {path.relative_to(ROOT)}: {exc}")
            continue
        for raw_target in link_pattern.findall(content):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative = unquote(target.split("#", 1)[0])
            if not relative:
                continue
            resolved = (path.parent / relative).resolve()
            if not resolved.exists():
                errors.append(f"dangling Markdown link in {path.relative_to(ROOT)}: {target}")
                continue
            skill_root = next((root for root in skill_roots if path == root / "SKILL.md" or root in path.parents), None)
            if skill_root and resolved != skill_root and skill_root not in resolved.parents:
                errors.append(f"skill-local Markdown link escapes skill root in {path.relative_to(ROOT)}: {target}")


def _is_root_excluded(path: Path) -> bool:
    try:
        first = path.relative_to(ROOT).parts[0]
    except (ValueError, IndexError):
        return False
    return first in {".git", ".venv"}


def main() -> int:
    errors, warnings = validate()
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        print("\n".join(dict.fromkeys(errors)), file=sys.stderr)
        return 1
    print(f"validation: PASS ({len(_skill_paths())} skills)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
