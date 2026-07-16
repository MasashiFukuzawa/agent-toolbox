#!/usr/bin/env python3
"""Resolve cooled stable npm package candidates without modifying a project."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

PROFILES: dict[str, tuple[str, ...]] = {
    "base": ("pnpm", "typescript", "vitest", "knip", "lefthook", "oxlint", "oxfmt"),
    "cloudflare-worker-api": (
        "pnpm",
        "typescript",
        "hono",
        "zod",
        "drizzle-orm",
        "drizzle-kit",
        "vitest",
        "@cloudflare/vitest-pool-workers",
        "wrangler",
        "knip",
        "lefthook",
        "oxlint",
        "oxfmt",
    ),
    "cloudflare-fullstack": (
        "pnpm",
        "typescript",
        "hono",
        "zod",
        "drizzle-orm",
        "drizzle-kit",
        "react",
        "react-dom",
        "@types/react",
        "@types/react-dom",
        "vite",
        "@vitejs/plugin-react",
        "@cloudflare/vite-plugin",
        "vitest",
        "@cloudflare/vitest-pool-workers",
        "wrangler",
        "knip",
        "lefthook",
        "oxlint",
        "oxfmt",
    ),
    "node-api": (
        "pnpm",
        "typescript",
        "@types/node",
        "hono",
        "@hono/node-server",
        "zod",
        "drizzle-orm",
        "drizzle-kit",
        "vitest",
        "knip",
        "lefthook",
        "oxlint",
        "oxfmt",
    ),
    "react-spa": (
        "pnpm",
        "typescript",
        "react",
        "react-dom",
        "@types/react",
        "@types/react-dom",
        "vite",
        "@vitejs/plugin-react",
        "vitest",
        "knip",
        "lefthook",
        "oxlint",
        "oxfmt",
    ),
    "library": ("pnpm", "typescript", "vitest", "knip", "lefthook", "oxlint", "oxfmt"),
    "cli": ("pnpm", "typescript", "@types/node", "zod", "vitest", "knip", "lefthook", "oxlint", "oxfmt"),
}

SEMVER = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)


@dataclass(frozen=True)
class Candidate:
    package: str
    version: str
    published_at: str
    age_days: float
    latest_tag: str | None
    is_latest_tag: bool
    deprecated: str | None
    engines: dict[str, str]
    peer_dependencies: dict[str, str]


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def stable_key(version: str) -> tuple[int, int, int] | None:
    match = SEMVER.fullmatch(version)
    if not match or match.group("pre") is not None:
        return None
    return int(match.group("major")), int(match.group("minor")), int(match.group("patch"))


def package_url(registry: str, package: str) -> str:
    encoded = urllib.parse.quote(package, safe="")
    return f"{registry.rstrip('/')}/{encoded}"


def fetch_metadata(registry: str, package: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        package_url(registry, package),
        # Cooling decisions need the full packument's per-version `time` map.
        headers={"Accept": "application/json", "User-Agent": "typescript-project-foundation/1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def resolve_candidate(
    package: str,
    metadata: dict[str, Any],
    now: dt.datetime,
    cooling_days: int,
    allow_newer: bool,
) -> Candidate:
    versions = metadata.get("versions", {})
    times = metadata.get("time", {})
    eligible: list[tuple[tuple[int, int, int], str, dt.datetime]] = []
    cutoff = now - dt.timedelta(days=cooling_days)
    latest_tag = metadata.get("dist-tags", {}).get("latest")
    latest_key = stable_key(latest_tag) if isinstance(latest_tag, str) else None
    if isinstance(latest_tag, str) and latest_key is None:
        raise ValueError(f"{package}: npm latest dist-tag is not a stable semantic version ({latest_tag})")

    for version in versions:
        key = stable_key(version)
        published = times.get(version)
        if key is None or not isinstance(published, str):
            continue
        package_version = versions.get(version, {})
        if package_version.get("deprecated"):
            continue
        if latest_key is not None and key > latest_key:
            # Do not select a version the maintainer has not promoted to `latest`.
            continue
        published_at = parse_time(published)
        if allow_newer or published_at <= cutoff:
            eligible.append((key, version, published_at))

    if not eligible:
        raise ValueError(f"{package}: no stable version satisfies the {cooling_days}-day cooling period")

    _, version, published_at = max(eligible)
    package_version = versions.get(version, {})
    return Candidate(
        package=package,
        version=version,
        published_at=published_at.isoformat().replace("+00:00", "Z"),
        age_days=round((now - published_at).total_seconds() / 86400, 2),
        latest_tag=latest_tag if isinstance(latest_tag, str) else None,
        is_latest_tag=latest_tag == version,
        deprecated=package_version.get("deprecated") if isinstance(package_version.get("deprecated"), str) else None,
        engines=dict(package_version.get("engines", {})),
        peer_dependencies=dict(package_version.get("peerDependencies", {})),
    )


def selected_packages(profile: str | None, explicit: list[str]) -> list[str]:
    packages: list[str] = list(PROFILES.get(profile or "", ()))
    packages.extend(explicit)
    return list(dict.fromkeys(packages))


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Version resolution snapshot",
        "",
        f"- Retrieved: {result['retrieved_at']}",
        f"- Registry: {result['registry']}",
        f"- Cooling period: {result['cooling_days']} days",
        f"- Cooling bypass: {'yes' if result['allow_newer'] else 'no'}",
        "",
        "| Package | Candidate | Published | Age (days) | npm latest |",
        "|---|---:|---|---:|---|",
    ]
    for item in result["packages"]:
        latest = item["latest_tag"] or "unknown"
        lines.append(
            f"| `{item['package']}` | `{item['version']}` | {item['published_at']} | {item['age_days']} | `{latest}` |"
        )
    lines.extend(["", "## Compatibility metadata", ""])
    for item in result["packages"]:
        engines = json.dumps(item["engines"], sort_keys=True) if item["engines"] else "none declared"
        peers = json.dumps(item["peer_dependencies"], sort_keys=True) if item["peer_dependencies"] else "none declared"
        lines.extend(
            [
                f"### `{item['package']}@{item['version']}`",
                "",
                f"- Engines: `{engines}`",
                f"- Peer dependencies: `{peers}`",
                "",
            ]
        )
    lines.extend(
        [
            "",
            "> Registry metadata is advisory. Verify official runtime and peer-tool compatibility before installation.",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILES))
    parser.add_argument("--package", action="append", default=[], dest="packages")
    parser.add_argument("--cooling-days", type=int, default=7)
    parser.add_argument("--allow-newer", action="store_true", help="Bypass cooling for an approved exception")
    parser.add_argument("--registry", default="https://registry.npmjs.org")
    parser.add_argument(
        "--allow-insecure-registry", action="store_true", help="Allow an explicitly approved http registry"
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.cooling_days < 0:
        print("--cooling-days must be non-negative", file=sys.stderr)
        return 2
    parsed_registry = urllib.parse.urlparse(args.registry)
    valid_scheme = parsed_registry.scheme == "https" or (
        parsed_registry.scheme == "http" and args.allow_insecure_registry
    )
    if not valid_scheme or not parsed_registry.netloc:
        print(
            "--registry must use https (or pass --allow-insecure-registry for an approved http registry)",
            file=sys.stderr,
        )
        return 2
    packages = selected_packages(args.profile, args.packages)
    if not packages:
        print("select --profile and/or provide at least one --package", file=sys.stderr)
        return 2

    now = dt.datetime.now(dt.UTC)
    candidates: list[Candidate] = []
    failures: list[str] = []
    for package in packages:
        try:
            metadata = fetch_metadata(args.registry, package, args.timeout)
            candidates.append(resolve_candidate(package, metadata, now, args.cooling_days, args.allow_newer))
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as error:
            failures.append(f"{package}: {error}")

    result = {
        "retrieved_at": now.isoformat().replace("+00:00", "Z"),
        "registry": args.registry,
        "profile": args.profile,
        "cooling_days": args.cooling_days,
        "allow_newer": args.allow_newer,
        "packages": [candidate.__dict__ for candidate in candidates],
        "failures": failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True) if args.format == "json" else render_markdown(result))
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
