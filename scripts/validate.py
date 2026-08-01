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

ROOT = Path(__file__).resolve().parents[1]
SKILL_PATHS = sorted(ROOT.glob("plugins/*/skills/*/SKILL.md"))
FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
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


def validate() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    skills: dict[str, str] = {}
    for path in SKILL_PATHS:
        text = path.read_text()
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

    total = sum(map(len, skills.values()))
    if total > 4500:
        errors.append(f"toolbox descriptions exceed 4500 chars: {total}")
    _validate_manifests(errors)
    _validate_results(errors)
    _validate_skill_evals(errors)
    _validate_registry(skills, errors)
    _scan_public_content(errors)
    _validate_markdown_links(errors)
    _validate_review_mirror(errors)
    _validate_review_common_mirror(errors)
    return errors, warnings


def _validate_manifests(errors: list[str]) -> None:
    plugin_names = sorted(path.name for path in (ROOT / "plugins").iterdir() if path.is_dir())
    for name in plugin_names:
        for host in (".codex-plugin", ".claude-plugin"):
            path = ROOT / "plugins" / name / host / "plugin.json"
            try:
                manifest = json.loads(path.read_text())
                if manifest.get("name") != name:
                    errors.append(f"manifest name mismatch: {path.relative_to(ROOT)}")
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"invalid or missing manifest {path.relative_to(ROOT)}: {exc}")
    pairs = ((ROOT / ".agents/plugins/marketplace.json", "Codex"), (ROOT / ".claude-plugin/marketplace.json", "Claude"))
    for path, host in pairs:
        try:
            names = sorted(item["name"] for item in json.loads(path.read_text())["plugins"])
            if names != plugin_names:
                errors.append(f"{host} marketplace/plugin drift")
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"invalid {host} marketplace manifest: {exc}")

    done_plugin = ROOT / "plugins/done/skills/done"
    for relative in ("references/done.example.yml", "references/done.schema.json"):
        if not (done_plugin / relative).is_file():
            errors.append(f"done plugin distribution is missing: {relative}")
    if list(ROOT.glob("plugins/*/skills/*/agents/openai.yaml")):
        errors.append("skill-local agents/openai.yaml is not adopted in this repository")


def _validate_results(errors: list[str]) -> None:
    for path in (ROOT / "evals/results").glob("*.json"):
        try:
            result = json.loads(path.read_text())
            rows, summary = result["results"], result["summary"]
            if summary["total"] != len(rows):
                errors.append(f"trigger result total mismatch: {path.relative_to(ROOT)}")
            for status in ("passed", "failed", "not_run"):
                if summary[status] != sum(row["status"] == status for row in rows):
                    errors.append(f"trigger result {status} mismatch: {path.relative_to(ROOT)}")
            if path.name == "baseline.json":
                from scripts.trigger_eval import build_matrix

                matrix = build_matrix()
                expected = {
                    (host, environment, case["skill"], case["type"], case["id"])
                    for host in matrix["hosts"]
                    for environment in matrix["environments"]
                    for case in matrix["cases"]
                }
                actual = {
                    (row["host"], row["environment"], row["skill"], row["type"], row["case_id"])
                    for row in rows
                }
                if actual != expected:
                    errors.append("baseline trigger result is stale or incomplete")
        except (OSError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"invalid trigger result {path.relative_to(ROOT)}: {exc}")


def _validate_skill_evals(errors: list[str]) -> None:
    for path in ROOT.glob("plugins/*/skills/*/evals/evals.json"):
        try:
            document = json.loads(path.read_text())
            expected_name = path.parents[1].name
            if document["skill_name"] != expected_name:
                errors.append(f"eval skill_name mismatch: {path.relative_to(ROOT)}")
            for case in document["evals"]:
                if not {"id", "prompt", "expected_output"} <= set(case):
                    errors.append(f"incomplete eval case: {path.relative_to(ROOT)}")
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid skill eval {path.relative_to(ROOT)}: {exc}")
    for path in ROOT.glob("plugins/*/skills/*/evals/semantic-results.json"):
        try:
            result = json.loads(path.read_text())
            skill_path = path.parents[1] / "SKILL.md"
            evals_path = path.parent / "evals.json"
            skill_hash = hashlib.sha256(skill_path.read_bytes()).hexdigest()
            evals_hash = hashlib.sha256(evals_path.read_bytes()).hexdigest()
            if result["skill_sha256"] != skill_hash or result["evals_sha256"] != evals_hash:
                errors.append(f"stale semantic evaluation: {path.relative_to(ROOT)}")
            evals = json.loads(evals_path.read_text())["evals"]
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
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid semantic evaluation {path.relative_to(ROOT)}: {exc}")


def _validate_registry(skills: dict[str, str], errors: list[str]) -> None:
    registry = yaml.safe_load((ROOT / "docs/trigger-registry.yml").read_text())["skills"]
    if missing := set(skills) - set(registry):
        errors.append(f"trigger registry missing: {', '.join(sorted(missing))}")
    if extra := set(registry) - set(skills):
        errors.append(f"trigger registry has unknown skills: {', '.join(sorted(extra))}")
    for name, entry in registry.items():
        if missing := REQUIRED_REGISTRY_FIELDS - set(entry):
            errors.append(f"registry fields missing for {name}: {', '.join(sorted(missing))}")
        if entry.get("canonical_name") != name:
            errors.append(f"registry canonical_name mismatch: {name}")
        for neighbor in entry.get("nearest_neighbors", []):
            if neighbor not in skills:
                errors.append(f"unknown nearest neighbor {neighbor} from {name}")


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
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or ".venv" in path.parts:
            continue
        if path == Path(__file__).resolve():
            continue
        try:
            content = path.read_text()
        except UnicodeDecodeError:
            continue
        for label, pattern in banned.items():
            if label == "legacy skill reference" and path in exclusions:
                continue
            if pattern.search(content):
                errors.append(f"{label}: {path.relative_to(ROOT)}")
    if list(ROOT.glob("**/case-study.md")):
        errors.append("private case study must not be published")


def _validate_markdown_links(errors: list[str]) -> None:
    """Reject dangling local Markdown links without trying to validate external URLs."""
    link_pattern = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
    skill_roots = {path.parent for path in SKILL_PATHS}
    for path in ROOT.rglob("*.md"):
        if ".git" in path.parts:
            continue
        for raw_target in link_pattern.findall(path.read_text()):
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


REVIEW_MIRROR_SKILLS = ("codex-review", "claude-review")
REVIEW_MIRROR_BEGIN = "<!-- MIRROR:review-async BEGIN -->"
REVIEW_MIRROR_END = "<!-- MIRROR:review-async END -->"
REVIEW_MIRROR_FILES = ("references/review-snapshot.md",)


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
        block = _extract_mirror_block(path.read_text(encoding="utf-8"))
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
            contents[skill] = path.read_text(encoding="utf-8")
        if len(contents) == len(REVIEW_MIRROR_SKILLS) and len(set(contents.values())) != 1:
            errors.append(f"review mirror: {relative} differs between {' and '.join(REVIEW_MIRROR_SKILLS)}")


REVIEW_COMMON_BEGIN = "<!-- MIRROR:review-common BEGIN -->"
REVIEW_COMMON_END = "<!-- MIRROR:review-common END -->"
# Provider-specific tokens replaced by placeholders before comparing
# MIRROR:review-common blocks. Longest-first application keeps overlapping
# tokens (e.g. "claude-opus-5" vs "claude") from corrupting each other.
REVIEW_COMMON_TOKENS: dict[str, tuple[tuple[str, str], ...]] = {
    "codex-review": (
        ("gpt-5.6-sol", "⟪STRONG⟫"),
        ("gpt-5.6-terra", "⟪DEFAULT⟫"),
        ("codex exec", "⟪CLI⟫"),
        ("Codex", "⟪PROVIDER⟫"),
        ("codex", "⟪provider⟫"),
    ),
    "claude-review": (
        ("claude-opus-5", "⟪STRONG⟫"),
        ("claude-sonnet-5", "⟪DEFAULT⟫"),
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
        blocks = _extract_common_blocks(path.read_text(encoding="utf-8"))
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
    print(f"validation: PASS ({len(SKILL_PATHS)} skills)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
