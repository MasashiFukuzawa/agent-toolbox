"""Behavioral checks for the approved owner-board lifecycle and offline content contract."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

SKILL = Path(__file__).resolve().parents[1] / "plugins/toolbox/skills/owner-board"
SCRIPT = SKILL / "scripts/owner_board.py"
spec = importlib.util.spec_from_file_location("owner_board", SCRIPT)
board = importlib.util.module_from_spec(spec)
spec.loader.exec_module(board)


class Document(HTMLParser):
    def __init__(self, source: str):
        super().__init__()
        self.ids = []
        self.sections = []
        self.links = []
        self.tags = []
        self.visible_text = []
        self.code_text = []
        self._details = 0
        self._code = False
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.tags.append(tag)
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "section" and "id" in values:
            self.sections.append(values["id"])
        if tag == "a":
            self.links.append(values["href"])
        if tag == "details":
            self._details += 1
        if tag == "code":
            self._code = True

    def handle_endtag(self, tag):
        if tag == "details":
            self._details -= 1
        if tag == "code":
            self._code = False

    def handle_data(self, value):
        if not self._details:
            self.visible_text.append(value)
        if self._code:
            self.code_text.append(value)


@pytest.fixture
def sample(tmp_path):
    root = tmp_path / "source"
    shutil.copytree(SKILL / "assets", root)
    return json.loads((root / "example-board.json").read_text()), root


def render(data, root, output=None):
    return board.render_board(data, root, output or root, "2026-01-01T10:00:00+00:00")


def test_example_keeps_flexible_diagrams_tables_and_code_offline(sample):
    data, root = sample
    document = Document(render(data, root))
    assert document.tags.count("svg") == 2
    assert document.tags.count("table") == 6
    assert "img" not in document.tags and "iframe" not in document.tags
    assert len(document.ids) == len(set(document.ids))
    command = data["items"][1]["steps"][0]["blocks"][1]["text"]
    assert command in document.code_text


def test_recommendation_is_first_even_when_source_order_differs(sample):
    data, root = sample
    document = render(data, root)
    assert document.index("1 · 少人数で先に確認") < document.index("2 · 最初から広く確認")


def test_answer_moves_out_of_requests_but_pending_relays_stay_visible(sample):
    data, root = sample
    item = data["items"][0]
    item["state"] = "answered"
    item["answer"] = {
        "text": "1",
        "at": "2026-01-01T10:00:00+00:00",
        "follow_up": {"state": "done", "summary": "確認対象の準備済み"},
        "relays": [{"to": "設計担当", "state": "pending"}],
    }
    document = Document(render(data, root))
    assert "Q12" not in document.sections
    assert "Q12" in document.ids
    assert any("中継待ち：設計担当" in text for text in document.visible_text)


def test_completed_followups_do_not_leave_a_pending_banner(sample):
    data, root = sample
    for item in data["items"]:
        if item["state"] == "answered":
            item["answer"]["follow_up"]["state"] = "done"
            for relay in item["answer"]["relays"]:
                relay["state"] = "sent"
    assert "回答は受領済み · 対応が残っています" not in "".join(Document(render(data, root)).visible_text)


def test_no_requests_shows_empty_state_without_an_empty_table(sample):
    data, root = sample
    data["items"] = []
    document = Document(render(data, root))
    assert "table" not in document.tags
    assert "いま回答が必要な項目はありません。" in document.visible_text


def test_preparation_does_not_count_as_an_answer_request(sample):
    data, root = sample
    data["items"] = [data["items"][2]]
    source = render(data, root)
    assert "回答待ち 0 件 · 準備中 1 件" in source
    assert "準備中 · 回答不要" in source


def test_plain_text_cannot_inject_markup_or_template_tokens(sample):
    data, root = sample
    payload = '<img src="https://example.org/image" onerror="alert(1)">{{BODY}}'
    data["items"][0]["blocks"] = [{"type": "paragraph", "text": payload}]
    document = Document(render(data, root))
    assert "img" not in document.tags
    assert payload in document.visible_text


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "%6aavascript:alert(1)",
        "//example.org/",
        "data:text/html,test",
        f"https://user:placeholder{chr(64)}example.org/",
    ],
)
def test_active_links_and_embedded_credentials_are_rejected(sample, href):
    data, root = sample
    data["related"] = [{"label": "資料", "href": href}]
    with pytest.raises(board.BoardError):
        render(data, root)


@pytest.mark.parametrize(
    "content",
    [
        "<script>alert(1)</script>",
        "<foreignObject><div>label</div></foreignObject>",
        '<rect onclick="alert(1)"/>',
        '<use href="https://example.org/image.svg#x"/>',
        "<style>text { fill: red }</style>",
        '<rect fill="url(https://example.org/color.svg#x)"/>',
    ],
)
def test_active_or_external_svg_content_is_rejected(sample, content):
    data, root = sample
    (root / "unsafe.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">{content}</svg>')
    data["items"][0]["blocks"] = [{"type": "svg", "path": "unsafe.svg", "alt": "図の要点"}]
    with pytest.raises(board.BoardError):
        render(data, root)


def test_repeated_svg_keeps_internal_references_local_and_unique(sample):
    data, root = sample
    (root / "reusable.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10">'
        '<path d="M0 0 L10 5 L0 10 Z"/></marker></defs>'
        '<path d="M10 10 L90 90" marker-end="url(#arrow)"/></svg>'
    )
    data["items"][0]["blocks"] = [{"type": "svg", "path": "reusable.svg", "alt": "進む向き"}] * 2
    source = render(data, root)
    document = Document(source)
    assert len(document.ids) == len(set(document.ids))
    for svg_id in [value for value in document.ids if value.endswith("-arrow")]:
        assert f"url(#{svg_id})" in source


def test_svg_symlinks_cannot_embed_files_outside_data_directory(sample):
    data, root = sample
    outside = root.parent / "outside.svg"
    outside.write_text('<svg viewBox="0 0 100 100"><text>outside</text></svg>')
    (root / "link.svg").symlink_to(outside)
    data["items"][0]["blocks"] = [{"type": "svg", "path": "link.svg", "alt": "図"}]
    with pytest.raises(board.BoardError):
        render(data, root)


def test_supplementary_material_links_back_to_the_published_board(sample):
    data, root = sample
    source = root / "owner-board.json"
    output = root / "owner-board.html"
    source.write_text(json.dumps(data))
    assert (
        subprocess.run(
            [sys.executable, str(SCRIPT), "render", "--data", str(source), "--output", str(output)],
            capture_output=True,
        ).returncode
        == 0
    )
    link = next(link for link in Document(output.read_text()).links if link.endswith("explanation.html#comparison"))
    explanation = root / unquote(urlsplit(link).path)
    backlink = next(link for link in Document(explanation.read_text()).links if link.startswith("owner-board.html"))
    assert (explanation.parent / unquote(urlsplit(backlink).path)).resolve() == output


@pytest.mark.parametrize("mutation", ["duplicate", "orphan", "collision", "incomplete-task", "invalid-answer-state"])
def test_request_invariants_are_validated(sample, mutation):
    data, root = sample
    if mutation == "duplicate":
        data["items"].append(data["items"][0])
    elif mutation == "orphan":
        data["items"][0]["id"] = "Q99-1"
    elif mutation == "collision":
        data["session_names"].append("1")
    elif mutation == "incomplete-task":
        del data["items"][1]["return_expected"]
    else:
        data["items"][3]["state"] = "preparing"
    with pytest.raises(board.BoardError):
        render(data, root)


def test_failed_cli_render_preserves_existing_html_and_data(sample):
    data, root = sample
    source = root / "owner-board.json"
    output = root / "owner-board.html"
    source.write_text(json.dumps(data))
    command = [sys.executable, str(SCRIPT), "render", "--data", str(source), "--output", str(output)]
    assert subprocess.run(command, capture_output=True).returncode == 0
    previous = output.read_bytes()
    source.write_text('{"version":1,"version":2}')
    bad_data = source.read_bytes()
    result = subprocess.run(command, capture_output=True)
    assert result.returncode == 1
    assert output.read_bytes() == previous
    assert source.read_bytes() == bad_data


@pytest.mark.parametrize("reply", ["1", "Q99: 1", "Q120: 1"])
def test_reply_examples_cannot_target_a_different_question(sample, reply):
    data, root = sample
    data["items"][0]["reply"] = reply
    with pytest.raises(board.BoardError):
        render(data, root)


@pytest.mark.parametrize("index", [0, 1])
def test_history_preserves_the_request_that_the_answer_authorized(sample, index):
    data, root = sample
    item = data["items"][index]
    item["state"] = "answered"
    item["answer"] = {
        "text": "1" if index == 0 else "確認済み",
        "at": "2026-01-01T10:00:00+00:00",
        "follow_up": {"state": "done", "summary": "対応済み"},
        "relays": [],
    }
    source = render(data, root)
    assert item["question"] in source
    if index == 0:
        assert all(option["label"] in source for option in item["options"])
    else:
        assert item["return_expected"] in source
        assert item["steps"][0]["blocks"][1]["text"] in Document(source).code_text
    assert len(Document(source).ids) == len(set(Document(source).ids))
    assert item["id"] not in Document(source).sections


@pytest.mark.parametrize("destination", ["source", "elsewhere"])
def test_cli_rejects_source_overwrite_and_detached_publication(sample, destination):
    data, root = sample
    source = root / "source.html"
    source.write_text(json.dumps(data))
    previous = source.read_bytes()
    output = source if destination == "source" else root.parent / "published.html"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "render", "--data", str(source), "--output", str(output)],
        capture_output=True,
    )
    assert result.returncode == 1
    assert source.read_bytes() == previous
    if destination != "source":
        assert not output.exists()


def test_withdrawn_preparation_can_archive_partial_task_information(sample):
    data, root = sample
    item = data["items"][1]
    item["state"] = "withdrawn"
    item["withdrawal"] = "準備中に不要と判断したため"
    del item["return_expected"]
    del item["reply"]
    source = render(data, root)
    assert item["withdrawal"] in source
    assert item["question"] in source
    assert item["steps"][0]["blocks"][1]["text"] in Document(source).code_text
    assert item["id"] not in Document(source).sections


def test_passive_exporter_svg_metadata_is_removed_and_labels_are_kept(sample):
    data, root = sample
    (root / "export.svg").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" version="1.1" content="editor-only">'
        '<metadata><document xmlns="urn:editor">not-visible-editor-data</document></metadata>'
        '<g class="card" data-cell-id="editor-node" pointer-events="all">'
        '<text xml:space="preserve" style="font-family: &quot;Example Sans&quot;">Flow label</text></g>'
        "</svg>"
    )
    data["items"][0]["blocks"] = [{"type": "svg", "path": "export.svg", "alt": "図の要点"}]
    result = render(data, root)
    assert "Flow label" in result
    assert "not-visible-editor-data" not in result and "editor-only" not in result
    assert '<g class="card"' not in result


@pytest.mark.parametrize(
    "declaration", ['<?xml-stylesheet href="outside.css"?>', '<!DOCTYPE svg [<!ENTITY x "payload">]>']
)
def test_accepting_xml_prologue_does_not_accept_active_declarations(sample, declaration):
    data, root = sample
    (root / "active.svg").write_text(
        '<?xml version="1.0"?>' + declaration + '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"/>'
    )
    data["items"][0]["blocks"] = [{"type": "svg", "path": "active.svg", "alt": "図"}]
    with pytest.raises(board.BoardError):
        render(data, root)


def test_answer_correction_does_not_claim_no_response_is_needed(sample):
    data, root = sample
    data["items"][3]["answer"]["follow_up"]["summary"] = "訂正の確認が必要。新しいQで確認します"
    source = render(data, root)
    assert "訂正の確認が必要" in source
    assert "追加の回答は不要です" not in source


def test_encoded_filename_delimiters_remain_part_of_the_local_path(sample):
    data, root = sample
    (root / "a b#c?.html").write_text("<!doctype html><title>Example</title>")
    data["related"] = [{"label": "資料", "href": "a%20b%23c%3F.html#section"}]
    link = next(link for link in Document(render(data, root)).links if link.endswith("#section"))
    assert (root / unquote(urlsplit(link).path)).resolve() == root / "a b#c?.html"


def test_cli_keeps_existing_publication_permissions(sample):
    data, root = sample
    source = root / "owner-board.json"
    output = root / "owner-board.html"
    source.write_text(json.dumps(data))
    output.write_text("previous")
    output.chmod(0o640)
    assert board.main(["render", "--data", str(source), "--output", str(output)]) == 0
    assert output.stat().st_mode & 0o777 == 0o640


def test_svg_ids_cannot_collide_with_namespaced_question_or_heading_ids(sample):
    data, root = sample
    (root / "collision.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<g id="Q1"><text id="Q1-title">Diagram</text></g></svg>'
    )
    data["namespace"] = "diagram-1"
    data["items"] = [data["items"][0]]
    data["items"][0].update(id="diagram-1-Q1", reply="diagram-1-Q1: 1")
    data["context"] = [{"type": "svg", "path": "collision.svg", "alt": "図"}]
    document = Document(render(data, root))
    assert len(document.ids) == len(set(document.ids))
    assert "diagram-1-Q1" in document.sections
    assert "diagram-1-Q1-title" in document.ids


@pytest.mark.parametrize("index,field,value", [(0, "steps", []), (1, "options", []), (2, "reply", "Q14: 1")])
def test_inputs_that_would_be_silently_hidden_are_rejected(sample, index, field, value):
    data, root = sample
    data["items"][index][field] = value
    with pytest.raises(board.BoardError):
        render(data, root)


def test_preparing_task_displays_supplied_draft_steps_and_impact(sample):
    data, root = sample
    item = data["items"][1]
    item["state"] = "preparing"
    del item["reply"]
    source = render(data, root)
    assert "準備中の草案" in source
    assert item["return_expected"] in source and item["consequence"] in source
    assert item["steps"][0]["blocks"][1]["text"] in Document(source).code_text


def test_duplicate_relay_destinations_cannot_have_conflicting_statuses(sample):
    data, root = sample
    relays = data["items"][3]["answer"]["relays"]
    relays.append({"to": relays[0]["to"], "state": "pending"})
    with pytest.raises(board.BoardError):
        render(data, root)


def test_svg_error_identifies_input_position_without_echoing_private_names(sample):
    data, root = sample
    (root / "rejected.svg").write_text(
        '\ufeff<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        "<private-demo-element/></svg>"
    )
    data["items"][0]["blocks"] = [{"type": "svg", "path": "rejected.svg", "alt": "図"}]
    with pytest.raises(board.BoardError) as error:
        render(data, root)
    assert "items[0].blocks[0]" in str(error.value)
    assert "private-demo-element" not in str(error.value)
    assert "position 1" in str(error.value)


def test_passive_svg_bom_and_text_metrics_are_accepted(sample):
    data, root = sample
    (root / "metrics.svg").write_text(
        '\ufeff<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"'
        ' contentStyleType="text/css" shape-rendering="geometricPrecision" xml:lang="en">'
        '<text textLength="90" lengthAdjust="spacing" text-decoration="underline">Example</text></svg>'
    )
    data["items"][0]["blocks"] = [{"type": "svg", "path": "metrics.svg", "alt": "図"}]
    assert "Example" in render(data, root)


def test_url_validation_rejects_a_scheme_that_differs_from_emitted_href(sample):
    data, root = sample
    data["related"] = [{"label": "資料", "href": "https%3A//example.org/reference"}]
    with pytest.raises(board.BoardError):
        render(data, root)
