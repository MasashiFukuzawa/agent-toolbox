#!/usr/bin/env python3
"""Validate skills, manifests, trigger metadata, and public-content boundaries."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml
from jsonschema import Draft202012Validator, FormatChecker, SchemaError

from scripts.plugin_paths import (
    is_tracked_file,
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
REQUIRED_REGISTRY_FIELDS = {
    "canonical_name",
    "category",
    "supported_hosts",
    "runtime_dependencies",
    "side_effect_level",
    "positive_triggers",
    "nearest_neighbors",
    "negative_triggers",
    "ambiguous_precedence",
}
HOST_MANIFEST_DIRS = {"codex": ".codex-plugin", "claude-code": ".claude-plugin"}


def validate() -> tuple[list[str], list[str]]:
    """Stop before reading repository content if a symlink escapes or is unresolved."""
    errors: list[str] = []
    warnings: list[str] = []
    errors.extend(_repository_boundary_errors())
    errors.extend(_plugin_boundary_errors())
    if errors:
        return errors, warnings

    skills: dict[str, str] = {}
    for path in _skill_paths():
        try:
            text = require_public_file(ROOT, path).read_text()
        except (OSError, ValueError) as exc:
            errors.append(f"cannot read public skill {path.relative_to(ROOT)}: {exc}")
            continue
        match = FRONTMATTER.match(text)
        if not match:
            errors.append(f"missing frontmatter: {path.relative_to(ROOT)}")
            continue
        try:
            metadata = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            errors.append(f"invalid YAML: {path.relative_to(ROOT)}: {exc}")
            continue
        name = path.parent.name
        if set(metadata or {}) != {"name", "description"}:
            errors.append(f"frontmatter keys must be name, description: {path.relative_to(ROOT)}")
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
        skills[name] = description

    # No catalog-wide total cap: per-skill bounds above govern residency cost,
    # and a total cap couples unrelated skills (adding one forces trimming
    # another). See docs/skill-conventions.md "Description budget".
    _validate_manifests(errors)
    _validate_results(errors)
    _validate_skill_evals(errors)
    _validate_registry(skills, errors)
    _scan_public_content(errors)
    _validate_markdown_links(errors)
    _validate_review_mirror(errors)
    _validate_review_common_mirror(errors)
    return errors, warnings


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

    done_plugin = ROOT / "plugins/done/skills/done"
    for relative in ("references/done.example.yml", "references/done.schema.json"):
        try:
            require_public_file(ROOT, done_plugin / relative)
        except ValueError:
            errors.append(f"done plugin distribution is missing: {relative}")
    if public_paths(ROOT, list(ROOT.glob("plugins/*/skills/*/agents/openai.yaml"))):
        errors.append("skill-local agents/openai.yaml is not adopted in this repository")


def _marketplace_source_path(entry: dict, host: str) -> str | None:
    source = entry.get("source")
    if host == "Codex" and isinstance(source, dict) and source.get("source") == "local":
        path = source.get("path")
        return path if isinstance(path, str) else None
    if host == "Claude" and isinstance(source, str):
        return source
    return None


def _validate_results(errors: list[str]) -> None:
    baseline_path = ROOT / "evals/results/baseline.json"
    try:
        require_public_file(ROOT, baseline_path)
        if is_tracked_file(ROOT, baseline_path) is False:
            raise ValueError("required trigger baseline is not tracked by Git")
    except ValueError as exc:
        errors.append(f"required trigger baseline is missing or ignored: {baseline_path.relative_to(ROOT)}: {exc}")
        return

    schema_path = ROOT / "evals/result-schema.json"
    try:
        schema = json.loads(require_public_file(ROOT, schema_path).read_text())
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
    except (OSError, json.JSONDecodeError, SchemaError, ValueError) as exc:
        errors.append(f"invalid trigger result schema {schema_path.relative_to(ROOT)}: {exc}")
        return

    for path in public_paths(ROOT, list((ROOT / "evals/results").glob("*.json"))):
        try:
            result = json.loads(require_public_file(ROOT, path).read_text())
            if schema_errors := list(validator.iter_errors(result)):
                for schema_error in schema_errors:
                    location = "/".join(str(part) for part in schema_error.absolute_path) or "$"
                    errors.append(
                        f"trigger result schema mismatch: {path.relative_to(ROOT)} at {location}: "
                        f"{schema_error.message}"
                    )
                continue
            rows, summary = result["results"], result["summary"]
            if summary["total"] != len(rows):
                errors.append(f"trigger result total mismatch: {path.relative_to(ROOT)}")
            for status in ("passed", "failed", "not_run"):
                if summary[status] != sum(row["status"] == status for row in rows):
                    errors.append(f"trigger result {status} mismatch: {path.relative_to(ROOT)}")
            if path.name == "baseline.json":
                from scripts.trigger_eval import build_matrix

                matrix = build_matrix()
                from scripts.trigger_eval import matrix_sha256

                if result.get("matrix_sha256") != matrix_sha256(matrix):
                    errors.append("baseline trigger result is stale or incomplete")
                expected = {
                    (host, environment, case["skill"], case["type"], case["id"])
                    for host in matrix["hosts"]
                    for environment in matrix["environments"]
                    for case in matrix["cases"]
                    if host in case["supported_hosts"]
                }
                actual = {
                    (row["host"], row["environment"], row["skill"], row["type"], row["case_id"])
                    for row in rows
                }
                if actual != expected or len(rows) != len(expected):
                    errors.append("baseline trigger result is stale or incomplete")
        except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid trigger result {path.relative_to(ROOT)}: {exc}")


def _validate_skill_evals(errors: list[str]) -> None:
    for path in public_paths(ROOT, list(ROOT.glob("plugins/*/skills/*/evals/evals.json"))):
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


def _validate_registry(skills: dict[str, str], errors: list[str]) -> None:
    registry_path = ROOT / "docs/trigger-registry.yml"
    try:
        registry = yaml.safe_load(require_public_file(ROOT, registry_path).read_text())["skills"]
    except (OSError, KeyError, TypeError, yaml.YAMLError, ValueError) as exc:
        errors.append(f"invalid trigger registry {registry_path.relative_to(ROOT)}: {exc}")
        return
    if missing := set(skills) - set(registry):
        errors.append(f"trigger registry missing: {', '.join(sorted(missing))}")
    if extra := set(registry) - set(skills):
        errors.append(f"trigger registry has unknown skills: {', '.join(sorted(extra))}")
    for name, entry in registry.items():
        if missing := REQUIRED_REGISTRY_FIELDS - set(entry):
            errors.append(f"registry fields missing for {name}: {', '.join(sorted(missing))}")
        if entry.get("canonical_name") != name:
            errors.append(f"registry canonical_name mismatch: {name}")
        declared_hosts = set(entry.get("supported_hosts", []))
        actual_hosts = {
            host
            for host in HOST_MANIFEST_DIRS
            if any(_host_publishes_skill(path, host) for path in _skill_paths() if path.parent.name == name)
        }
        if declared_hosts != actual_hosts:
            errors.append(
                f"{name}: registry supported_hosts {sorted(declared_hosts)} "
                f"do not match plugin manifests {sorted(actual_hosts)}"
            )
        for neighbor in entry.get("nearest_neighbors", []):
            if neighbor not in skills:
                errors.append(f"unknown nearest neighbor {neighbor} from {name}")
            elif neighbor not in registry:
                errors.append(f"nearest neighbor {neighbor} from {name} is missing from the trigger registry")
            elif not declared_hosts <= set(registry[neighbor].get("supported_hosts", [])):
                errors.append(f"nearest neighbor {neighbor} from {name} lacks required hosts {sorted(declared_hosts)}")


def _host_publishes_skill(skill_path: Path, host: str) -> bool:
    plugin_dir = skill_path.parents[2]
    manifest_path = plugin_dir / HOST_MANIFEST_DIRS[host] / "plugin.json"
    if (
        not public_paths(ROOT, [manifest_path])
        or manifest_path.is_symlink()
        or _has_symlink_parent(plugin_dir, manifest_path)
        or _path_within_plugin(plugin_dir, manifest_path) is None
        or not manifest_path.is_file()
    ):
        return False
    resolved_skill = _path_within_plugin(plugin_dir, skill_path)
    if resolved_skill is None:
        return False
    if host == "claude-code":
        skills_root = _path_within_plugin(plugin_dir, plugin_dir / "skills")
        if skills_root is None:
            return False
        try:
            resolved_skill.relative_to(skills_root)
            return True
        except ValueError:
            return False
    try:
        repository_root = plugin_dir.parent.parent
        manifest = json.loads(require_public_file(repository_root, manifest_path).read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return False
    paths = manifest.get("skills", [])
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, list):
        return False
    for relative in paths:
        target = _codex_skill_root(plugin_dir, relative)
        if target is None:
            continue
        try:
            resolved_skill.relative_to(target)
            return True
        except ValueError:
            continue
    return False


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
        "legacy skill reference": re.compile(
            r"worktree-flow|write-meaningful-tests|documentation-lookup|research-first"
        ),
    }
    exclusions = {ROOT / "scripts/validate.py", ROOT / "docs/trigger-registry.yml", ROOT / "docs/skill-conventions.md"}
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
            if label == "legacy skill reference" and path in exclusions:
                continue
            if pattern.search(content):
                errors.append(f"{label}: {path.relative_to(ROOT)}")
    if any(path.name == "case-study.md" for path in iter_public_files(ROOT)):
        errors.append("private case study must not be published")


def _validate_markdown_links(errors: list[str]) -> None:
    """Reject dangling local Markdown links without trying to validate external URLs."""
    link_pattern = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
    skill_roots = {path.parent for path in _skill_paths()}
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


REVIEW_MIRROR_SKILLS = ("codex-review", "claude-review")
REVIEW_MIRROR_BEGIN = "<!-- MIRROR:review-async BEGIN -->"
REVIEW_MIRROR_END = "<!-- MIRROR:review-async END -->"
REVIEW_MIRROR_FILES = (
    "references/review-snapshot.md",
    "references/durable-run-record.md",
)


def _extract_mirror_block(text: str) -> str | None:
    start = text.find(REVIEW_MIRROR_BEGIN)
    end = text.find(REVIEW_MIRROR_END)
    if start == -1 or end == -1 or end < start:
        return None
    return text[start : end + len(REVIEW_MIRROR_END)]


def _validate_review_mirror(errors: list[str], root: Path = ROOT) -> None:
    """The two reviewer skills share host-neutral text; keep it byte-identical.

    Missing markers are an error, not a silent skip: a gate that always passes
    is worse than no gate.
    """
    blocks: dict[str, str] = {}
    for skill in REVIEW_MIRROR_SKILLS:
        path = root / "plugins/toolbox/skills" / skill / "SKILL.md"
        if not path.exists():
            errors.append(f"review mirror: missing {path.relative_to(root)}")
            continue
        try:
            block = _extract_mirror_block(require_public_file(root, path).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            errors.append(f"review mirror: cannot read {path.relative_to(root)}: {exc}")
            continue
        if block is None:
            errors.append(f"review mirror: markers not found in {path.relative_to(root)}")
            continue
        blocks[skill] = block
    if len(blocks) == len(REVIEW_MIRROR_SKILLS) and len(set(blocks.values())) != 1:
        errors.append(
            "review mirror: MIRROR:review-async block differs between "
            + " and ".join(REVIEW_MIRROR_SKILLS)
        )

    for relative in REVIEW_MIRROR_FILES:
        contents: dict[str, str] = {}
        for skill in REVIEW_MIRROR_SKILLS:
            path = root / "plugins/toolbox/skills" / skill / relative
            if not path.exists():
                errors.append(f"review mirror: missing {path.relative_to(root)}")
                continue
            try:
                contents[skill] = require_public_file(root, path).read_text(encoding="utf-8")
            except (OSError, ValueError) as exc:
                errors.append(f"review mirror: cannot read {path.relative_to(root)}: {exc}")
        if len(contents) == len(REVIEW_MIRROR_SKILLS) and len(set(contents.values())) != 1:
            errors.append(f"review mirror: {relative} differs between {' and '.join(REVIEW_MIRROR_SKILLS)}")


REVIEW_COMMON_BEGIN = "<!-- MIRROR:review-common BEGIN -->"
REVIEW_COMMON_END = "<!-- MIRROR:review-common END -->"
# Provider-specific tokens replaced by placeholders before comparing
# MIRROR:review-common blocks. Longest-first application keeps overlapping
# tokens (e.g. "claude-opus-5-5" vs "claude") from corrupting each other.
REVIEW_COMMON_TOKENS: dict[str, tuple[tuple[str, str], ...]] = {
    "codex-review": (
        ("gpt-6.1-sol", "⟪DEFAULT⟫"),
        ("gpt-6-astra", "⟪STRONG⟫"),
        ("codex exec", "⟪CLI⟫"),
        ("Codex", "⟪PROVIDER⟫"),
        ("codex", "⟪provider⟫"),
    ),
    "claude-review": (
        ("claude-opus-5-5", "⟪STRONG⟫"),
        ("claude-sonnet-5-5", "⟪DEFAULT⟫"),
        ("claude -p", "⟪CLI⟫"),
        ("Claude", "⟪PROVIDER⟫"),
        ("claude", "⟪provider⟫"),
    ),
}


def _extract_common_blocks(text: str) -> list[str] | None:
    """Return MIRROR:review-common block bodies, or None on malformed markers."""
    blocks: list[str] = []
    position = 0
    while True:
        begin = text.find(REVIEW_COMMON_BEGIN, position)
        stray_end = text.find(REVIEW_COMMON_END, position)
        if begin == -1:
            return None if stray_end != -1 else blocks
        if stray_end != -1 and stray_end < begin:
            return None
        end = text.find(REVIEW_COMMON_END, begin)
        if end == -1:
            return None
        blocks.append(text[begin + len(REVIEW_COMMON_BEGIN) : end])
        position = end + len(REVIEW_COMMON_END)


def _normalize_review_common(skill: str, block: str) -> str:
    for token, placeholder in sorted(REVIEW_COMMON_TOKENS[skill], key=lambda pair: -len(pair[0])):
        block = block.replace(token, placeholder)
    return block


def _validate_review_common_mirror(errors: list[str], root: Path = ROOT) -> None:
    """MIRROR:review-common blocks must match after provider-token normalization.

    Like the async mirror, missing markers, unbalanced markers, and count
    mismatches are errors, never silent skips.
    """
    normalized: dict[str, list[str]] = {}
    for skill in REVIEW_MIRROR_SKILLS:
        path = root / "plugins/toolbox/skills" / skill / "SKILL.md"
        if not path.exists():
            errors.append(f"review mirror: missing {path.relative_to(root)}")
            continue
        try:
            contents = require_public_file(root, path).read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            errors.append(f"review mirror: cannot read {path.relative_to(root)}: {exc}")
            continue
        blocks = _extract_common_blocks(contents)
        if blocks is None:
            errors.append(f"review mirror: unbalanced MIRROR:review-common markers in {path.relative_to(root)}")
            continue
        if not blocks:
            errors.append(f"review mirror: MIRROR:review-common markers not found in {path.relative_to(root)}")
            continue
        normalized[skill] = [_normalize_review_common(skill, block) for block in blocks]
    if len(normalized) != len(REVIEW_MIRROR_SKILLS):
        return
    counts = {skill: len(blocks) for skill, blocks in normalized.items()}
    if len(set(counts.values())) != 1:
        errors.append(
            "review mirror: MIRROR:review-common block count differs: "
            + ", ".join(f"{skill}={count}" for skill, count in counts.items())
        )
        return
    for index, blocks in enumerate(zip(*(normalized[skill] for skill in REVIEW_MIRROR_SKILLS), strict=True)):
        if len(set(blocks)) != 1:
            errors.append(
                f"review mirror: MIRROR:review-common block {index + 1} differs after "
                "normalization between " + " and ".join(REVIEW_MIRROR_SKILLS)
            )


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
