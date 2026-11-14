from __future__ import annotations

import contextlib
import importlib.util
import io
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
                    "scripts": {
                        "lint": "oxlint",
                        "typecheck": "tsc --noEmit",
                        "test": "vitest run",
                        "build": "tsc -p tsconfig.build.json",
                        "verify": "pnpm lint && pnpm typecheck && pnpm test && pnpm build",
                        "pinact:check": "pinact run -check",
                    },
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
        (root / "tsconfig.json").write_text(
            '{"compilerOptions":{"strict":true,"noUncheckedIndexedAccess":true}}\n', encoding="utf-8"
        )
        (root / "AGENTS.md").write_text("Run `pnpm verify` before reporting completion.\n", encoding="utf-8")
        (root / "lefthook.yml").write_text(
            "pre-commit:\n  commands:\n    secrets:\n      run: gitleaks protect --staged\n", encoding="utf-8"
        )
        (root / ".pinact.yaml").write_text("version: 3\nmin_age:\n  value: 3\n  always: false\n", encoding="utf-8")
        (root / "docs/architecture").mkdir(parents=True)
        (root / "docs/architecture/foundation.md").write_text("# Foundation\n", encoding="utf-8")
        (root / ".github/workflows").mkdir(parents=True)
        revision = "v5" if mutable_action else "a" * 40
        (root / ".github/workflows/ci.yml").write_text(
            f"permissions:\n  contents: read\nsteps:\n  - uses: actions/checkout@{revision}\n", encoding="utf-8"
        )
        (root / ".github/dependabot.yml").write_text(
            "updates:\n  - package-ecosystem: github-actions\n  - package-ecosystem: npm\n", encoding="utf-8"
        )
        return temporary

    def report(self, root: str) -> tuple[int, list[dict[str, str]]]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = MODULE.main(["--root", root, "--format", "json"])
        return exit_code, json.loads(output.getvalue())["findings"]

    def rewrite_package(self, root: Path, change) -> None:
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        change(package)
        (root / "package.json").write_text(json.dumps(package), encoding="utf-8")

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

    def test_complete_fixture_reports_no_findings(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(self.report(temporary.name), (0, []))

    def test_missing_agent_ready_controls_warn_without_failing(self) -> None:
        def drop_verify(root: Path) -> None:
            self.rewrite_package(root, lambda package: package["scripts"].pop("verify"))

        def drop_instructions(root: Path) -> None:
            (root / "AGENTS.md").unlink()

        def instructions_without_verify(root: Path) -> None:
            (root / "AGENTS.md").write_text("See docs/adr/ for decisions.\n", encoding="utf-8")

        def hooks_without_secret_scan(root: Path) -> None:
            (root / "lefthook.yml").write_text("pre-commit:\n  commands:\n    lint:\n      run: oxlint\n", "utf-8")

        def drop_hooks(root: Path) -> None:
            (root / "lefthook.yml").unlink()

        def actions_only_updates(root: Path) -> None:
            (root / ".github/dependabot.yml").write_text("package-ecosystem: github-actions\n", encoding="utf-8")

        def workflow_without_permissions(root: Path) -> None:
            (root / ".github/workflows/ci.yml").write_text(
                f"steps:\n  - uses: actions/checkout@{'a' * 40}\n", encoding="utf-8"
            )

        def indexed_access_unchecked(root: Path) -> None:
            (root / "tsconfig.json").write_text('{"compilerOptions":{"strict":true}}\n', encoding="utf-8")

        cases = [
            (drop_verify, "package-script-missing"),
            (drop_instructions, "agent-instructions-missing"),
            (instructions_without_verify, "agent-instructions-verify-missing"),
            (hooks_without_secret_scan, "secret-scan-missing"),
            (drop_hooks, "hooks-missing"),
            (actions_only_updates, "dependency-updates-package-missing"),
            (workflow_without_permissions, "workflow-permissions-missing"),
            (indexed_access_unchecked, "no-unchecked-indexed-access-missing"),
        ]
        for mutate, code in cases:
            with self.subTest(code=code):
                temporary = self.fixture()
                self.addCleanup(temporary.cleanup)
                mutate(Path(temporary.name))
                exit_code, findings = self.report(temporary.name)
                self.assertEqual(exit_code, 0)
                self.assertIn(code, [finding["code"] for finding in findings])
                self.assertEqual({finding["severity"] for finding in findings}, {"warning"})

    def test_equivalent_tools_satisfy_agent_ready_controls(self) -> None:
        def host_specific_instructions(root: Path) -> None:
            (root / "AGENTS.md").unlink()
            (root / "CLAUDE.md").write_text("Run `pnpm verify` before finishing.\n", encoding="utf-8")

        def renovate_updates(root: Path) -> None:
            (root / ".github/dependabot.yml").write_text("package-ecosystem: github-actions\n", encoding="utf-8")
            (root / "renovate.json").write_text("{}\n", encoding="utf-8")

        def secret_scan_in_ci_only(root: Path) -> None:
            (root / "lefthook.yml").write_text("pre-commit:\n  commands:\n    lint:\n      run: oxlint\n", "utf-8")
            workflow = root / ".github/workflows/ci.yml"
            workflow.write_text(workflow.read_text(encoding="utf-8") + "  - run: gitleaks detect\n", encoding="utf-8")

        for mutate in (host_specific_instructions, renovate_updates, secret_scan_in_ci_only):
            with self.subTest(case=mutate.__name__):
                temporary = self.fixture()
                self.addCleanup(temporary.cleanup)
                mutate(Path(temporary.name))
                self.assertEqual(self.report(temporary.name), (0, []))

    def test_repository_scaffolded_before_agent_ready_checks_still_passes(self) -> None:
        temporary = self.fixture()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "AGENTS.md").unlink()
        (root / "lefthook.yml").unlink()
        self.rewrite_package(root, lambda package: package.update(scripts={"pinact:check": "pinact run -check"}))
        (root / "tsconfig.json").write_text('{"compilerOptions":{"strict":true}}\n', encoding="utf-8")
        (root / ".github/workflows/ci.yml").write_text(
            f"steps:\n  - uses: actions/checkout@{'a' * 40}\n", encoding="utf-8"
        )
        (root / ".github/dependabot.yml").write_text("package-ecosystem: github-actions\n", encoding="utf-8")
        exit_code, findings = self.report(temporary.name)
        self.assertEqual(exit_code, 0)
        self.assertEqual([finding for finding in findings if finding["severity"] == "error"], [])


if __name__ == "__main__":
    unittest.main()
