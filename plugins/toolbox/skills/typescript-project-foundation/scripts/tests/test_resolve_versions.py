from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "resolve_versions.py"
SPEC = importlib.util.spec_from_file_location("resolve_versions", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ResolveVersionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = dt.datetime(2026, 7, 16, tzinfo=dt.UTC)
        self.metadata = {
            "dist-tags": {"latest": "2.0.0"},
            "time": {
                "1.5.0": "2026-06-01T00:00:00.000Z",
                "2.0.0-beta.1": "2026-06-20T00:00:00.000Z",
                "2.0.0": "2026-07-14T00:00:00.000Z",
            },
            "versions": {
                "1.5.0": {"engines": {"node": ">=20"}},
                "2.0.0-beta.1": {},
                "2.0.0": {"peerDependencies": {"typescript": ">=7"}},
            },
        }

    def test_selects_newest_cooled_stable(self) -> None:
        candidate = MODULE.resolve_candidate("example", self.metadata, self.now, 7, False)
        self.assertEqual(candidate.version, "1.5.0")
        self.assertFalse(candidate.is_latest_tag)

    def test_approved_bypass_selects_latest_stable(self) -> None:
        candidate = MODULE.resolve_candidate("example", self.metadata, self.now, 7, True)
        self.assertEqual(candidate.version, "2.0.0")
        self.assertEqual(candidate.peer_dependencies, {"typescript": ">=7"})

    def test_prerelease_is_never_selected(self) -> None:
        metadata = {
            "dist-tags": {"latest": "2.0.0-beta.1"},
            "time": {"2.0.0-beta.1": "2026-06-01T00:00:00.000Z"},
            "versions": {"2.0.0-beta.1": {}},
        }
        with self.assertRaisesRegex(ValueError, "latest dist-tag is not a stable"):
            MODULE.resolve_candidate("example", metadata, self.now, 0, True)

    def test_profile_and_explicit_packages_are_deduplicated(self) -> None:
        packages = MODULE.selected_packages("base", ["typescript", "hono"])
        self.assertEqual(packages.count("typescript"), 1)
        self.assertIn("hono", packages)

    def test_deprecated_and_unpromoted_versions_are_not_selected(self) -> None:
        metadata = {
            "dist-tags": {"latest": "2.0.0"},
            "time": {
                "1.9.0": "2026-06-01T00:00:00.000Z",
                "2.0.0": "2026-06-02T00:00:00.000Z",
                "2.1.0": "2026-06-03T00:00:00.000Z",
            },
            "versions": {
                "1.9.0": {},
                "2.0.0": {"deprecated": "security issue"},
                "2.1.0": {},
            },
        }
        candidate = MODULE.resolve_candidate("example", metadata, self.now, 0, True)
        self.assertEqual(candidate.version, "1.9.0")

    def test_markdown_includes_compatibility_metadata(self) -> None:
        candidate = MODULE.resolve_candidate("example", self.metadata, self.now, 7, True)
        result = {
            "retrieved_at": "2026-07-16T00:00:00Z",
            "registry": "https://registry.npmjs.org",
            "cooling_days": 7,
            "allow_newer": True,
            "packages": [candidate.__dict__],
        }
        output = MODULE.render_markdown(result)
        self.assertIn("Peer dependencies", output)
        self.assertIn("typescript", output)

    def test_rejects_non_http_registry(self) -> None:
        self.assertEqual(MODULE.main(["--package", "example", "--registry", "file:///tmp/registry"]), 2)

    def test_http_registry_requires_explicit_override(self) -> None:
        self.assertEqual(MODULE.main(["--package", "example", "--registry", "http://registry.example.invalid"]), 2)


if __name__ == "__main__":
    unittest.main()
