from scripts.model_trigger_adapter import load_skill_catalog
from scripts.trigger_eval import build_matrix, check_matrix, matrix_sha256


def test_trigger_matrix_is_complete() -> None:
    matrix = build_matrix()
    assert check_matrix(matrix) == []
    assert matrix["hosts"] == ["claude-code", "codex"]


def test_codex_only_skills_are_scoped_out_of_other_host_cases() -> None:
    matrix = build_matrix()
    codex_only = [case for case in matrix["cases"] if case["skill"] == "plugin-release"]
    assert codex_only
    assert all(case["supported_hosts"] == ["codex"] for case in codex_only)


def test_host_specific_skill_catalogs_include_only_supported_skills() -> None:
    assert "plugin-release" not in load_skill_catalog("claude-code")
    assert "model-selection" in load_skill_catalog("claude-code")
    assert "plugin-release" in load_skill_catalog("codex")


def test_baseline_fingerprint_covers_prompt_and_host_matrix() -> None:
    matrix = build_matrix()
    changed = {**matrix, "cases": [{**matrix["cases"][0], "prompt": "changed"}, *matrix["cases"][1:]]}
    assert matrix_sha256(changed) != matrix_sha256(matrix)


def test_every_case_has_an_expected_result() -> None:
    assert all(case["expected"] for case in build_matrix()["cases"])
