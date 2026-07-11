from scripts.trigger_eval import build_matrix, check_matrix


def test_trigger_matrix_is_complete() -> None:
    matrix = build_matrix()
    assert check_matrix(matrix) == []
    assert matrix["hosts"] == ["claude-code", "codex"]


def test_every_case_has_an_expected_result() -> None:
    assert all(case["expected"] for case in build_matrix()["cases"])
