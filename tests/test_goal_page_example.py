"""The goal page example is what agents copy, so it must follow the page contract in the autopilot skill."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

EXAMPLE = Path(__file__).resolve().parents[1] / "plugins/toolbox/skills/autopilot/assets/example"
SECTIONS = ["now", "changes", "asks", "decisions", "evidence", "agreement", "handover", "record"]
STATES = {"進行中", "完了", "判断待ち", "作業待ち", "外部待ち", "中断"}
ROWS = ["背景", "課題", "目的", "相談事項"]
HANDOVER = {
    "ホストとセッション", "worktree", "ブランチ", "最後に検査した版", "PR", "実行中の処理",
    "このゴールで作ったもの", "再開時に照合すること",
}


class Page(HTMLParser):
    """Collects only what the contract talks about: sections, asks, links, and unsafe constructs."""

    def __init__(self, source: str) -> None:
        super().__init__()
        self.sections: list[str] = []
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.unsafe: list[str] = []
        self.text: dict[str, list[str]] = {}
        self.asks: list[dict] = []
        self.terms: dict[str, list[str]] = {}
        self._stack: list[tuple[str, dict[str, str]]] = []
        self._section: str | None = None
        self._ask: dict | None = None
        self._capture: tuple[str, list[str]] | None = None
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        self._stack.append((tag, values))
        if "id" in values:
            self.ids.add(values["id"])
        if tag in {"script", "iframe", "img", "link", "object", "embed"}:
            self.unsafe.append(tag)
        self.unsafe.extend(key for key in values if key.startswith("on"))
        if tag == "a" and "href" in values:
            self.links.append(values["href"])
        if tag == "section" and values.get("id"):
            self._section = values["id"]
            self.sections.append(self._section)
        if tag == "article" and "ask" in values.get("class", "").split():
            self._ask = {"id": values.get("id", ""), "labels": [], "terms": [], "comparison": False, "due": ""}
            self.asks.append(self._ask)
        if self._ask is not None and tag in {"table", "svg"} and not any(name == "details" for name, _ in self._stack):
            self._ask["comparison"] = True
        classes = values.get("class", "").split()
        if tag == "div" and "label" in classes and self._ask is not None:
            self._capture = ("label", [])
        elif tag == "dt":
            self._capture = ("term", [])
        elif tag == "span" and "due" in classes and self._ask is not None:
            self._capture = ("due", [])
        elif values.get("id") == "state":
            self._capture = ("state", [])
        elif tag == "td" and "t" in classes:
            self._capture = ("key", [])

    def handle_endtag(self, tag: str) -> None:
        if self._capture and tag in {"div", "dt", "span", "td"}:
            kind, parts = self._capture
            value = "".join(parts).strip()
            if kind == "label" and self._ask is not None:
                self._ask["labels"].append(value)
            elif kind == "term":
                self.terms.setdefault(self._section or "", []).append(value)
                if self._ask is not None:
                    self._ask["terms"].append(value)
            elif kind == "due" and self._ask is not None:
                self._ask["due"] = value
            elif kind in {"state", "key"}:
                self.text.setdefault(kind if kind == "state" else f"key:{self._section}", []).append(value)
            self._capture = None
        if tag == "article":
            self._ask = None
        if tag == "section":
            self._section = None
        while self._stack and self._stack.pop()[0] != tag:
            pass

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._capture[1].append(data)


@pytest.fixture(scope="module")
def source() -> str:
    return (EXAMPLE / "goal-page.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def page(source: str) -> Page:
    return Page(source)


def test_the_page_reads_from_position_to_asks_to_evidence(page: Page) -> None:
    assert page.sections == SECTIONS


def test_the_state_is_one_of_the_named_stop_states(page: Page) -> None:
    assert page.text["state"] and set(page.text["state"]) <= STATES


def test_the_state_agrees_with_what_the_page_says_is_happening(page: Page) -> None:
    (state,) = page.text["state"]
    position = page.terms["now"]
    if state == "進行中":
        # An open ask holds only its own work: the page still says what is being done.
        assert "やっていること" in position
    elif state != "完了":
        assert "再開の条件" in position


def test_every_ask_can_be_answered_from_its_own_card(page: Page) -> None:
    assert page.asks, "the example must show at least one ask"
    for ask in page.asks:
        assert re.fullmatch(r"Q\d+", ask["id"])
        assert ask["labels"] == ROWS
        assert ask["comparison"], "a comparison must be visible without opening anything"
        assert {"戻せるか", "返信例"} <= set(ask["terms"])
        assert re.search(r"\d{1,2}:\d{2} [A-Z]{2,5}", ask["due"]), "a deadline needs a time and a time zone"


def test_the_ask_list_points_at_the_cards_in_the_same_order(page: Page) -> None:
    listed = [link[1:] for link in page.links if re.fullmatch(r"#Q\d+", link)]
    assert listed == [ask["id"] for ask in page.asks]


def test_every_agreed_condition_has_a_row_of_evidence(page: Page) -> None:
    agreed = [key for key in page.text["key:agreement"] if re.fullmatch(r"A\d+", key)]
    assert agreed, "the agreement must list numbered acceptance conditions"
    assert page.text["key:evidence"] == agreed


def test_another_session_can_take_over_from_the_page(page: Page) -> None:
    assert set(page.terms["handover"]) >= HANDOVER


@pytest.mark.parametrize("name", ["goal-page.html", "goal-entry.html"])
def test_examples_stay_self_contained(name: str) -> None:
    source = (EXAMPLE / name).read_text(encoding="utf-8")
    parsed = Page(source)
    assert parsed.unsafe == []
    assert "@media" not in source
    assert all(link.startswith(("#", "https://")) or "://" not in link for link in parsed.links)
