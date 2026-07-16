from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "check_invariants.py"
SPEC = importlib.util.spec_from_file_location("check_invariants", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CheckInvariantsTest(unittest.TestCase):
    def fixture(self, mutable_action: bool = False) -> tempfile.TemporaryDirectory[str]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        (root / "package.json").write_text(
            json.dumps(
                {
                    "type": "module",
                    "packageManager": "pnpm@11.2.0",
                    "devDependencies": {"typescript": "7.0.2", "oxlint": "1.0.0", "oxfmt": "1.0.0"},
                    "scripts": {"pinact:check": "pinact run -check"},
                }
            ),
            encoding="utf-8",
        )
        (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
        (root / "pnpm-workspace.yaml").write_text(
            "minimumReleaseAge: 10080\n"
            "minimumReleaseAgeStrict: true\n"
            "blockExoticSubdeps: true\n"
            "allowBuilds:\n"
            "  esbuild: true\n",
            encoding="utf-8",
        )
        (root / "tsconfig.json").write_text('{"compilerOptions":{"strict":true}}\n', encoding="utf-8")
        (root / ".pinact.yaml").write_text("version: 3\nmin_age:\n  value: 3\n  always: false\n", encoding="utf-8")
        (root / "docs/architecture").mkdir(parents=True)
        (root / "docs/architecture/foundation.md").write_text("# Foundation\n", encoding="utf-8")
        (root / ".github/workflows").mkdir(parents=True)
        revision = "v5" if mutable_action else "a" * 40
        (root / ".github/workflows/ci.yml").write_text(
            f"steps:\n  - uses: actions/checkout@{revision}\n", encoding="utf-8"
        )
        (root / ".github/dependabot.yml").write_text("package-ecosystem: github-actions\n", encoding="utf-8")
        return temporary

    def test_complete_fixture_passes(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(MODULE.main(["--root", temporary.name]), 0)

    def test_mutable_action_fails(self) -> None:
        temporary = self.fixture(mutable_action=True)
        self.addCleanup(temporary.cleanup)
        self.assertEqual(MODULE.main(["--root", temporary.name]), 1)

    def test_overlapping_formatters_fail(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        package["devDependencies"]["@biomejs/biome"] = "2.0.0"
        (root / "package.json").write_text(json.dumps(package), encoding="utf-8")
        self.assertEqual(MODULE.main(["--root", temporary.name]), 1)

    def test_stricter_cooling_period_passes(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "pnpm-workspace.yaml"
        path.write_text(path.read_text(encoding="utf-8").replace("10080", "20160"), encoding="utf-8")
        self.assertEqual(MODULE.main(["--root", temporary.name]), 0)

    def test_quoted_pnpm_values_with_comments_pass(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "pnpm-workspace.yaml"
        path.write_text(
            'minimumReleaseAge: "10080" # seven days\n'
            "minimumReleaseAgeStrict: 'true' # fail closed\n"
            "blockExoticSubdeps: true # explicit\n"
            "allowBuilds: {esbuild: true} # narrow allowlist\n",
            encoding="utf-8",
        )
        self.assertEqual(MODULE.main(["--root", temporary.name]), 0)

    def test_missing_allow_builds_is_warning_only(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "pnpm-workspace.yaml"
        path.write_text(
            "minimumReleaseAge: 10080\nminimumReleaseAgeStrict: true\nblockExoticSubdeps: true\n", encoding="utf-8"
        )
        self.assertEqual(MODULE.main(["--root", temporary.name]), 0)

    def test_external_tsconfig_base_is_warning_only(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "tsconfig.json").write_text('{"extends":"@tsconfig/strictest/tsconfig.json"}\n', encoding="utf-8")
        self.assertEqual(MODULE.main(["--root", temporary.name]), 0)

    def test_external_tsconfig_base_array_is_warning_only(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "tsconfig.json").write_text('{"extends":["@tsconfig/strictest/tsconfig.json"]}\n', encoding="utf-8")
        self.assertEqual(MODULE.main(["--root", temporary.name]), 0)

    def test_quoted_sha_action_passes(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / ".github/workflows/ci.yml"
        path.write_text(f'steps:\n  - uses: "actions/checkout@{"a" * 40}"\n', encoding="utf-8")
        self.assertEqual(MODULE.main(["--root", temporary.name]), 0)

    def test_mutable_docker_action_fails(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / ".github/workflows/ci.yml"
        path.write_text("steps:\n  - uses: docker://alpine:latest\n", encoding="utf-8")
        self.assertEqual(MODULE.main(["--root", temporary.name]), 1)

    def test_pinact_in_lefthook_does_not_require_package_script(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        package["scripts"] = {}
        (root / "package.json").write_text(json.dumps(package), encoding="utf-8")
        (root / "lefthook.yml").write_text(
            "pre-commit:\n  commands:\n    pinact:\n      run: pinact run -check\n", encoding="utf-8"
        )
        self.assertEqual(MODULE.main(["--root", temporary.name]), 0)


if __name__ == "__main__":
    unittest.main()
