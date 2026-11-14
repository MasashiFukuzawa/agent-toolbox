"""The owner-board example is the page agents copy, so it must follow the board contract in SKILL.md."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

EXAMPLE = Path(__file__).resolve().parents[1] / "plugins/toolbox/skills/owner-board/assets/example"
BOARD = "owner-board.html"
ARCHIVE = "owner-board-archive.html"
QUESTION_ID = re.compile(r"Q\d+(?:-\d+)?")
FOLLOW_UP_QUESTIONS = {"変更の大きさ", "日々の使い勝手", "戻せるか", "待ち時間の根拠"}


class Page(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []
        self.resources: list[str] = []
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.cards: list[dict] = []
        self.ask_rows: list[str] = []
        self.styles: list[str] = []
        self._stack: list[str] = []
        self._card: dict | None = None
        self._card_depth = 0
        self._in_asks = False
        self._in_label = False
        self._in_style = False
        self._in_kind = False
        self._in_check = False
        self._checks_depth: int | None = None
        self._folded_depth: int | None = None
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        classes = (attributes.get("class") or "").split()
        if attributes.get("id"):
            self.ids.append(attributes["id"])
        if tag == "a" and attributes.get("href"):
            self.links.append(attributes["href"])
        if tag != "a" and (attributes.get("src") or attributes.get("href")):
            self.resources.append(attributes.get("src") or attributes.get("href"))
        if tag == "style":
            self._in_style = True
        if tag == "article" and "ask-card" in classes:
            self._card = {
                "id": attributes.get("id"),
                "labels": [],
                "kind": None,
                "sequence": [],
                "follow_ups": [],
                "replies": 0,
            }
            self._card_depth = len(self._stack)
        if tag == "div" and "asks" in classes:
            self._in_asks = True
        if self._in_asks and tag == "a" and attributes.get("href", "").startswith("#"):
            self.ask_rows.append(attributes["href"][1:])
        if self._card is not None and tag == "span" and "label" in classes:
            self._in_label = True
        if self._card is not None:
            self._read_card_part(tag, classes)
        if tag not in {"meta", "br", "line", "rect", "path"}:
            self._stack.append(tag)

    def _read_card_part(self, tag, classes):
        depth = len(self._stack)
        if tag == "span" and "pill" in classes and self._card["kind"] is None:
            self._in_kind = True
        if tag == "details" and self._folded_depth is None:
            self._folded_depth = depth
        if tag == "svg":
            self._card["sequence"].append("folded-figure" if self._folded_depth is not None else "figure")
        if tag == "table" and "opts" in classes:
            self._card["sequence"].append("options")
        if tag == "dl" and "checks" in classes:
            self._checks_depth = depth
        if tag == "dt" and self._checks_depth is not None:
            self._in_check = True
        if tag == "p" and "reply" in classes:
            self._card["replies"] += 1

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False
        if tag == "span":
            self._in_label = False
            self._in_kind = False
        if tag == "dt":
            self._in_check = False
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        if tag == "details" and self._folded_depth == len(self._stack):
            self._folded_depth = None
        if tag == "dl" and self._checks_depth == len(self._stack):
            self._checks_depth = None
        if tag == "article" and self._card is not None and len(self._stack) == self._card_depth:
            self.cards.append(self._card)
            self._card = None
        if tag == "table" and self._in_asks:
            self._in_asks = False

    def handle_data(self, data):
        if self._in_style:
            self.styles.append(data)
        if self._card is None or not data.strip():
            return
        if self._in_label:
            self._card["labels"].append(data.strip())
        if self._in_kind and data.strip() in {"判断", "作業"}:
            self._card["kind"] = data.strip()
        if self._in_check:
            self._card["follow_ups"].append(data.strip())


def load(name: str) -> Page:
    return Page((EXAMPLE / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", [BOARD, ARCHIVE])
def test_example_runs_offline_without_active_content(name):
    page = load(name)

    tag_names = {tag for tag, _ in page.tags}
    event_handlers = [key for _, attrs in page.tags for key in attrs if key.startswith("on")]
    css = "".join(page.styles)

    assert tag_names.isdisjoint({"script", "iframe", "foreignobject", "link", "img"})
    assert event_handlers == []
    assert page.resources == []
    assert "@media" not in css and "@import" not in css and "url(" not in css
    assert all(urlsplit(href).scheme in {"", "https"} for href in page.links)


def test_every_link_between_board_and_archive_lands_on_an_existing_anchor():
    pages = {BOARD: load(BOARD), ARCHIVE: load(ARCHIVE)}

    broken = []
    for name, page in pages.items():
        for href in page.links:
            target = urlsplit(href)
            if target.scheme:
                continue
            destination = pages.get(target.path or name)
            if destination is None or (target.fragment and target.fragment not in destination.ids):
                broken.append(f"{name}: {href}")

    assert broken == []
    assert any(urlsplit(href).path == ARCHIVE for href in pages[BOARD].links)
    assert any(urlsplit(href).path == BOARD for href in pages[ARCHIVE].links)


def test_every_open_request_is_written_as_background_problem_goal_and_ask():
    cards = load(BOARD).cards

    assert cards, "the example must show at least one open request"
    assert all(card["labels"] == ["背景", "課題", "目的", "相談事項"] for card in cards)


def decision_cards() -> list[dict]:
    cards = [card for card in load(BOARD).cards if card["kind"] == "判断"]
    assert cards, "the example must show at least one decision request"
    return cards


def test_a_decision_shows_its_figure_before_the_options_without_unfolding():
    for card in decision_cards():
        sequence = card["sequence"]

        assert "figure" in sequence, f"{card['id']} has no figure that is visible without opening anything"
        assert sequence.index("figure") < sequence.index("options"), f"{card['id']} shows options before the figure"


def test_a_decision_card_asks_one_decision_with_one_way_to_reply():
    for card in decision_cards():
        assert card["sequence"].count("options") == 1, f"{card['id']} must ask exactly one decision"
        assert card["replies"] == 1, f"{card['id']} must show exactly one reply example"


def test_a_decision_card_answers_the_questions_an_owner_asks_before_replying():
    for card in decision_cards():
        answered = set(card["follow_ups"])

        assert answered, f"{card['id']} answers none of the usual follow-up questions"
        assert answered <= FOLLOW_UP_QUESTIONS, f"{card['id']} uses unknown labels: {answered - FOLLOW_UP_QUESTIONS}"


def test_request_table_lists_exactly_the_open_cards_in_display_order():
    page = load(BOARD)

    assert page.ask_rows == [card["id"] for card in page.cards]


def test_a_question_number_lives_on_only_one_page():
    open_ids = {i for i in load(BOARD).ids if QUESTION_ID.fullmatch(i)}
    archived_ids = {i for i in load(ARCHIVE).ids if QUESTION_ID.fullmatch(i)}

    assert open_ids and archived_ids
    assert open_ids.isdisjoint(archived_ids)


def test_an_archived_request_keeps_what_the_owner_was_shown():
    cards = load(ARCHIVE).cards

    assert cards, "the archive example must show at least one answered or withdrawn request"
    for card in cards:
        assert card["labels"] == ["背景", "課題", "目的", "相談事項"], f"{card['id']} lost a row of the request"
        if card["kind"] == "判断":
            sequence = card["sequence"]
            assert "folded-figure" in sequence, f"{card['id']} dropped the figure the owner decided from"
            assert sequence.index("folded-figure") < sequence.index("options"), f"{card['id']} reordered the request"
            assert sequence.count("options") == 1 and card["replies"] == 1, f"{card['id']} dropped options or reply"
