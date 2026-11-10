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
            self._card = {"id": attributes.get("id"), "labels": []}
            self._card_depth = len(self._stack)
        if tag == "div" and "asks" in classes:
            self._in_asks = True
        if self._in_asks and tag == "a" and attributes.get("href", "").startswith("#"):
            self.ask_rows.append(attributes["href"][1:])
        if self._card is not None and tag == "span" and "label" in classes:
            self._in_label = True
        if tag not in {"meta", "br", "line", "rect", "path"}:
            self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False
        if tag == "span":
            self._in_label = False
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        if tag == "article" and self._card is not None and len(self._stack) == self._card_depth:
            self.cards.append(self._card)
            self._card = None
        if tag == "table" and self._in_asks:
            self._in_asks = False

    def handle_data(self, data):
        if self._in_style:
            self.styles.append(data)
        if self._in_label and self._card is not None and data.strip():
            self._card["labels"].append(data.strip())


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


def test_request_table_lists_exactly_the_open_cards_in_display_order():
    page = load(BOARD)

    assert page.ask_rows == [card["id"] for card in page.cards]


def test_a_question_number_lives_on_only_one_page():
    open_ids = {i for i in load(BOARD).ids if QUESTION_ID.fullmatch(i)}
    archived_ids = {i for i in load(ARCHIVE).ids if QUESTION_ID.fullmatch(i)}

    assert open_ids and archived_ids
    assert open_ids.isdisjoint(archived_ids)
