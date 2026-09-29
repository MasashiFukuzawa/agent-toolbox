import json

import pytest

from scripts.model_trigger_adapter import load_skill_catalog, parse_selected_skill
from scripts.run_trigger_eval import _evaluate, main
from scripts.trigger_eval import build_matrix, check_matrix, is_valid_selection, matrix_sha256


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


def test_baseline_fingerprint_covers_skill_descriptions() -> None:
    matrix = build_matrix()
    changed = {**matrix, "skill_descriptions": {**matrix["skill_descriptions"], "plugin-release": "changed"}}
    assert matrix_sha256(changed) != matrix_sha256(matrix)


def test_nearest_negative_cases_cover_every_declared_neighbor() -> None:
    matrix = build_matrix()
    cases = [
        case for case in matrix["cases"]
        if case["skill"] == "plugin-release" and case["type"] == "nearest_negative"
    ]
    assert len(cases) == 2 * 2
    assert {case["expected"] for case in cases} == {"done", "cloudflare-worker-cd"}


def test_ambiguous_cases_cover_every_declared_neighbor() -> None:
    matrix = build_matrix()
    cases = [
        case for case in matrix["cases"] if case["skill"] == "plugin-release" and case["type"] == "ambiguous"
    ]
    assert len(cases) == 2 * 2
    assert all("done" in case["prompt"] or "cloudflare-worker-cd" in case["prompt"] for case in cases)


def test_negative_trigger_phrases_are_explicit_exclusion_cases() -> None:
    matrix = build_matrix()
    cases = [
        case for case in matrix["cases"]
        if case["skill"] == "plugin-release" and case["type"] == "negative_trigger"
    ]
    assert len(cases) == 2
    assert all(case["expected"] == "not:plugin-release" for case in cases)


def test_negative_trigger_expectation_rejects_only_the_named_skill(monkeypatch) -> None:
    class Process:
        returncode = 0
        stdout = '{"selected_skill":"done"}'
        stderr = ""

    monkeypatch.setattr("scripts.run_trigger_eval.subprocess.run", lambda *args, **kwargs: Process())
    case = {"skill": "plugin-release", "type": "negative_trigger", "id": 1, "expected": "not:plugin-release"}
    assert _evaluate("codex", "isolated", case, "fake")["status"] == "passed"
    Process.stdout = '{"selected_skill":"plugin-release"}'
    assert _evaluate("codex", "isolated", case, "fake")["status"] == "failed"
    Process.stdout = '{"selected_skill":"garbage"}'
    assert _evaluate("codex", "isolated", case, "fake")["status"] == "failed"
    for invalid in ("[]", "{}"):
        Process.stdout = json.dumps({"selected_skill": json.loads(invalid)})
        assert _evaluate("codex", "isolated", case, "fake")["status"] == "failed"
    for invalid_response in ("[]", "null", '"text"'):
        Process.stdout = invalid_response
        assert _evaluate("codex", "isolated", case, "fake")["status"] == "failed"


def test_valid_selection_accepts_only_known_host_skills_or_neutral_decisions() -> None:
    assert is_valid_selection("codex", "plugin-release")
    assert is_valid_selection("claude-code", "ask-provider")
    assert not is_valid_selection("claude-code", "plugin-release")
    assert not is_valid_selection("codex", "garbage")


def test_model_adapter_accepts_only_a_standalone_json_selection() -> None:
    assert parse_selected_skill('{"selected_skill":"done"}') == "done"
    for invalid in (
        'Here is my choice: {"selected_skill":"done"}',
        '```json\n{"selected_skill":"done"}\n```',
        '[]',
        '{"selected_skill":[]}',
    ):
        with pytest.raises(ValueError):
            parse_selected_skill(invalid)


def test_deterministic_baseline_generation_is_byte_reproducible(tmp_path, monkeypatch) -> None:
    output = tmp_path / "baseline.json"
    monkeypatch.setattr("sys.argv", ["run_trigger_eval", "--output", str(output), "--deterministic"])
    assert main() == 0
    first = output.read_bytes()
    assert "generated_at" not in json.loads(first)
    assert main() == 0
    assert output.read_bytes() == first


def test_every_case_has_an_expected_result() -> None:
    assert all(case["expected"] for case in build_matrix()["cases"])
