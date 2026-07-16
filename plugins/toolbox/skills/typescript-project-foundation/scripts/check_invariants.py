#!/usr/bin/env python3
"""Read-only checks for generic TypeScript project-foundation invariants."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")
DOCKER_DIGEST = re.compile(r"^docker://[^\s@]+@sha256:[0-9a-fA-F]{64}$")
PACKAGE_MANAGER = re.compile(r"^pnpm@\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
USES = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str
    path: str | None = None


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def strip_jsonc(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"(^|\s)//.*$", r"\1", text, flags=re.MULTILINE)
    return re.sub(r",\s*([}\]])", r"\1", text)


def safe_read(path: Path, root: Path, findings: list[Finding]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        findings.append(Finding("error", "file-unreadable", str(error), str(path.relative_to(root))))
        return None


def dependencies(package: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        values = package.get(key, {})
        if isinstance(values, dict):
            result.update(values)
    return result


def check_package(root: Path, findings: list[Finding]) -> dict[str, Any] | None:
    path = root / "package.json"
    if not path.exists():
        findings.append(Finding("error", "package-json-missing", "package.json is required", "package.json"))
        return None
    try:
        package = read_json(path)
    except (json.JSONDecodeError, OSError) as error:
        findings.append(Finding("error", "package-json-invalid", str(error), "package.json"))
        return None

    manager = package.get("packageManager")
    if not isinstance(manager, str) or not PACKAGE_MANAGER.fullmatch(manager):
        findings.append(
            Finding(
                "error",
                "package-manager-unpinned",
                "packageManager must be an exact pnpm@x.y.z version",
                "package.json",
            )
        )
    if package.get("type") != "module":
        findings.append(
            Finding("error", "esm-not-explicit", 'package.json must declare "type": "module"', "package.json")
        )
    return package


def check_lockfile(root: Path, findings: list[Finding]) -> None:
    if not (root / "pnpm-lock.yaml").exists():
        findings.append(Finding("error", "lockfile-missing", "pnpm-lock.yaml must be committed", "pnpm-lock.yaml"))


def check_typescript(root: Path, findings: list[Finding]) -> None:
    configs = sorted(root.glob("**/tsconfig*.json"))
    configs = [path for path in configs if "node_modules" not in path.parts]
    if not configs:
        findings.append(Finding("error", "tsconfig-missing", "at least one tsconfig*.json is required"))
        return
    strict_found = False
    external_base_found = False
    for path in configs:
        try:
            text = safe_read(path, root, findings)
            if text is None:
                continue
            data = json.loads(strip_jsonc(text))
        except (json.JSONDecodeError, OSError):
            findings.append(
                Finding(
                    "warning",
                    "tsconfig-unreadable",
                    "could not parse JSONC for generic checks",
                    str(path.relative_to(root)),
                )
            )
            continue
        if data.get("compilerOptions", {}).get("strict") is True:
            strict_found = True
        extends = data.get("extends")
        extend_values = [extends] if isinstance(extends, str) else extends if isinstance(extends, list) else []
        if any(isinstance(value, str) and not value.startswith((".", "/")) for value in extend_values):
            external_base_found = True
    if not strict_found:
        severity = "warning" if external_base_found else "error"
        message = (
            'strict may be inherited from an external tsconfig; verify the resolved config with "tsc --showConfig"'
            if external_base_found
            else 'no tsconfig explicitly sets "strict": true'
        )
        findings.append(Finding(severity, "strict-typescript-missing", message))


def check_formatter(root: Path, package: dict[str, Any] | None, findings: list[Finding]) -> None:
    if package is None:
        return
    deps = dependencies(package)
    owners: set[str] = set()
    if "oxfmt" in deps or any(root.glob(".oxfmtrc*")):
        owners.add("oxfmt")
    if "@biomejs/biome" in deps or (root / "biome.json").exists() or (root / "biome.jsonc").exists():
        owners.add("biome")
    if "prettier" in deps or any(root.glob(".prettierrc*")):
        owners.add("prettier")
    if not owners:
        findings.append(Finding("error", "formatter-missing", "configure exactly one formatter owner"))
    elif len(owners) > 1:
        findings.append(
            Finding("error", "formatter-overlap", f"multiple formatter owners detected: {', '.join(sorted(owners))}")
        )


def check_pnpm_policy(root: Path, findings: list[Finding]) -> None:
    path = root / "pnpm-workspace.yaml"
    if not path.exists():
        findings.append(
            Finding(
                "error", "pnpm-policy-missing", "pnpm-workspace.yaml must contain project security settings", path.name
            )
        )
        return
    text = safe_read(path, root, findings)
    if text is None:
        return
    age_match = re.search(r"(?m)^minimumReleaseAge:\s*['\"]?(\d+)['\"]?\s*(?:#.*)?$", text)
    if age_match is None or int(age_match.group(1)) < 10080:
        findings.append(
            Finding(
                "error", "pnpm-minimumReleaseAge-missing", "minimumReleaseAge must be at least 10080 minutes", path.name
            )
        )
    required = {
        "minimumReleaseAgeStrict": r"(?m)^minimumReleaseAgeStrict:\s*['\"]?true['\"]?\s*(?:#.*)?$",
        "blockExoticSubdeps": r"(?m)^blockExoticSubdeps:\s*['\"]?true['\"]?\s*(?:#.*)?$",
    }
    for key, pattern in required.items():
        if not re.search(pattern, text):
            findings.append(Finding("error", f"pnpm-{key}-missing", f"required pnpm policy missing: {key}", path.name))
    if not re.search(r"(?m)^allowBuilds:\s*(?:\{[^}]*\})?\s*(?:#.*)?$", text):
        findings.append(
            Finding(
                "warning",
                "pnpm-allowBuilds-missing",
                "define a narrow allowBuilds map when dependencies require lifecycle builds",
                path.name,
            )
        )


def workflow_files(root: Path) -> list[Path]:
    directory = root / ".github" / "workflows"
    if not directory.exists():
        return []
    return sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")])


def check_actions(root: Path, package: dict[str, Any] | None, findings: list[Finding]) -> None:
    workflows = workflow_files(root)
    if not workflows:
        return
    for path in workflows:
        text = safe_read(path, root, findings)
        if text is None:
            continue
        for value in USES.findall(text):
            value = value.strip("'\"")
            if value.startswith("./"):
                continue
            if value.startswith("docker://"):
                if not DOCKER_DIGEST.fullmatch(value):
                    findings.append(
                        Finding(
                            "error",
                            "docker-ref-mutable",
                            f"Docker Action must use a sha256 digest: {value}",
                            str(path.relative_to(root)),
                        )
                    )
                continue
            if "@" not in value:
                findings.append(
                    Finding(
                        "error",
                        "action-ref-missing",
                        f"Action reference has no immutable revision: {value}",
                        str(path.relative_to(root)),
                    )
                )
                continue
            revision = value.rsplit("@", 1)[1]
            if not FULL_SHA.fullmatch(revision):
                findings.append(
                    Finding(
                        "error",
                        "action-ref-mutable",
                        f"Action must use a full commit SHA: {value}",
                        str(path.relative_to(root)),
                    )
                )

    pinact_config = any(
        (root / name).exists() for name in (".pinact.yaml", ".pinact.yml", ".github/pinact.yaml", ".github/pinact.yml")
    )
    scripts = package.get("scripts", {}) if package else {}
    pinact_script = isinstance(scripts, dict) and any(
        "pinact" in key or "pinact" in str(value) for key, value in scripts.items()
    )
    integration_files = [root / "lefthook.yml", root / "lefthook.yaml", *workflows]
    pinact_integration = pinact_script
    for path in integration_files:
        if path.exists():
            text = safe_read(path, root, findings)
            pinact_integration = pinact_integration or (text is not None and "pinact" in text)
    if not pinact_config:
        findings.append(Finding("error", "pinact-config-missing", "GitHub Actions requires a Pinact configuration"))
    if not pinact_integration:
        findings.append(
            Finding("error", "pinact-check-missing", "Lefthook, package scripts, or CI must run a Pinact check")
        )

    dependabot = root / ".github" / "dependabot.yml"
    dependabot_text = safe_read(dependabot, root, findings) if dependabot.exists() else None
    if dependabot_text is None or "github-actions" not in dependabot_text:
        findings.append(
            Finding(
                "error",
                "dependabot-actions-missing",
                "Dependabot must update the github-actions ecosystem",
                ".github/dependabot.yml",
            )
        )


def check_foundation_record(root: Path, findings: list[Finding]) -> None:
    candidates = [
        root / "docs" / "architecture" / "foundation.md",
        root / "docs" / "adr" / "README.md",
        root / "docs" / "adrs" / "README.md",
    ]
    if not any(path.exists() for path in candidates):
        findings.append(
            Finding(
                "warning", "foundation-record-missing", "no conventional foundation/architecture decision record found"
            )
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    findings: list[Finding] = []
    package = check_package(root, findings)
    check_lockfile(root, findings)
    check_typescript(root, findings)
    check_formatter(root, package, findings)
    check_pnpm_policy(root, findings)
    check_actions(root, package, findings)
    check_foundation_record(root, findings)

    errors = sum(finding.severity == "error" for finding in findings)
    warnings = sum(finding.severity == "warning" for finding in findings)
    if args.format == "json":
        print(
            json.dumps(
                {
                    "root": str(root),
                    "errors": errors,
                    "warnings": warnings,
                    "findings": [asdict(item) for item in findings],
                },
                indent=2,
            )
        )
    else:
        for finding in findings:
            location = f" ({finding.path})" if finding.path else ""
            print(f"{finding.severity.upper()} [{finding.code}]{location}: {finding.message}")
        print(f"Summary: {errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
