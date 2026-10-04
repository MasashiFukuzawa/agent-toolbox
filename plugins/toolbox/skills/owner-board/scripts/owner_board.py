#!/usr/bin/env python3
"""Validate owner-board data and atomically render an offline HTML document."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import stat
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

ASSETS = Path(__file__).resolve().parents[1] / "assets"
SVG_NS = "http://www.w3.org/2000/svg"
SVG_TAGS = {
    "svg",
    "g",
    "defs",
    "marker",
    "path",
    "rect",
    "line",
    "polyline",
    "polygon",
    "circle",
    "ellipse",
    "text",
    "tspan",
    "title",
    "desc",
    "clipPath",
    "linearGradient",
    "radialGradient",
    "stop",
    "use",
}
SVG_ATTRS = {
    "id",
    "viewBox",
    "width",
    "height",
    "x",
    "y",
    "x1",
    "y1",
    "x2",
    "y2",
    "cx",
    "cy",
    "r",
    "rx",
    "ry",
    "d",
    "dx",
    "dy",
    "points",
    "transform",
    "fill",
    "fill-opacity",
    "fill-rule",
    "stroke",
    "stroke-width",
    "stroke-opacity",
    "stroke-dasharray",
    "stroke-dashoffset",
    "stroke-linecap",
    "stroke-linejoin",
    "stroke-miterlimit",
    "opacity",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "text-anchor",
    "dominant-baseline",
    "alignment-baseline",
    "preserveAspectRatio",
    "marker-start",
    "marker-mid",
    "marker-end",
    "markerWidth",
    "markerHeight",
    "markerUnits",
    "refX",
    "refY",
    "orient",
    "clip-path",
    "clipPathUnits",
    "gradientUnits",
    "gradientTransform",
    "offset",
    "stop-color",
    "stop-opacity",
    "spreadMethod",
    "href",
    "role",
    "aria-labelledby",
    "aria-describedby",
    "aria-hidden",
    "style",
    "version",
    "shape-rendering",
    "text-rendering",
    "text-decoration",
    "textLength",
    "lengthAdjust",
    "{http://www.w3.org/XML/1998/namespace}lang",
    "{http://www.w3.org/XML/1998/namespace}space",
}
STYLE_PROPS = {
    "background",
    "background-color",
    "color-scheme",
    "fill",
    "stroke",
    "stroke-width",
    "fill-opacity",
    "stroke-opacity",
    "opacity",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "text-anchor",
    "dominant-baseline",
}
ITEM_ID = re.compile(r"(?:[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*-)?Q[1-9][0-9]*(?:-[1-9][0-9]*)?\Z")
SVG_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*\Z")
REF = re.compile(r"url\(#([A-Za-z_][A-Za-z0-9_.-]*)\)")
KINDS = {"decision": "判断", "task": "作業"}
STATES = {"open", "preparing", "answered", "withdrawn"}
URGENCY = {"today": ("now", "今日"), "soon": ("soon", "近日"), "none": ("preparing", "期限なし")}


class BoardError(ValueError):
    """An input or publication failure without echoing potentially private values."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BoardError(message)


def fields(value: object, required: set[str], optional: set[str], where: str) -> dict:
    require(isinstance(value, dict), f"{where}: expected an object")
    require(required <= value.keys(), f"{where}: missing required fields")
    require(value.keys() <= required | optional, f"{where}: unknown fields")
    return value


def text(value: object, where: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{where}: expected non-empty text")
    return value


def texts(value: object, where: str) -> list[str]:
    require(isinstance(value, list), f"{where}: expected a list")
    return [text(v, where) for v in value]


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    obj = {}
    for key, value in pairs:
        require(key not in obj, "JSON: duplicate object key")
        obj[key] = value
    return obj


def safe_link(value: object, root: Path, output_dir: Path) -> str:
    link = text(value, "link")
    decoded = unquote(link)
    require(not any(ord(c) < 32 for c in decoded) and "\\" not in decoded, "link: unsafe characters")
    parts = urlsplit(decoded)
    if parts.scheme:
        require(urlsplit(link).scheme == parts.scheme, "link: encoded schemes are forbidden")
        require(parts.scheme in {"https", "http"} and bool(parts.hostname), "link: unsupported scheme")
        require(parts.username is None and parts.password is None, "link: embedded credentials are forbidden")
        return link
    require(not parts.netloc and not parts.path.startswith("/"), "link: expected a relative path")
    if not parts.path:
        require(bool(parts.fragment) and not parts.query, "link: expected a fragment or file")
        return link
    parts = urlsplit(link)
    target = (root / unquote(parts.path)).resolve()
    require(target.is_file(), "link: local target is missing")
    relative = Path(os.path.relpath(target, output_dir)).as_posix()
    # Encode filenames so a literal # or ? is not mistaken for a URL delimiter.
    return urlunsplit(("", "", quote(relative, safe="/"), parts.query, parts.fragment))


def svg_document(value: object, root: Path, prefix: str, alt: str) -> str:
    source = text(value, "svg.path")
    require(not Path(source).is_absolute(), "svg.path: expected a relative path")
    path = (root / source).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(), "svg.path: missing or outside data directory")
    raw = path.read_text(encoding="utf-8-sig")
    # A leading XML declaration is passive; reject all other processing instructions and entities.
    raw = re.sub(r"\A\s*<\?xml\s+[^?]*\?>", "", raw, count=1)
    # Strip only the fixed SVG 1.1 declaration emitted by exporters, without fetching its DTD.
    raw = re.sub(
        r"<!DOCTYPE\s+svg\s+PUBLIC\s+['\"]-//W3C//DTD SVG 1\.1//EN['\"]\s+"
        r"['\"]https?://www\.w3\.org/Graphics/SVG/1\.1/DTD/svg11\.dtd['\"]\s*>",
        "",
        raw,
        count=1,
    )
    require(
        not re.search(r"<!\s*(?:DOCTYPE|ENTITY)|<\?", raw, re.I),
        "svg: DTD, entities and processing instructions are forbidden",
    )
    try:
        document = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise BoardError("svg: malformed XML") from exc
    require(document.tag in {"svg", f"{{{SVG_NS}}}svg"}, "svg: expected an SVG root")
    try:
        viewbox = [float(v) for v in document.get("viewBox", "").replace(",", " ").split()]
    except ValueError as exc:
        raise BoardError("svg: invalid viewBox") from exc
    require(len(viewbox) == 4 and all(abs(v) < float("inf") for v in viewbox), "svg: invalid viewBox")
    require(viewbox[2] > 0 and viewbox[3] > 0, "svg: viewBox size must be positive")
    # Editor metadata is not visible content and can contain private source documents.
    for parent in document.iter():
        for child in list(parent):
            if child.tag == f"{{{SVG_NS}}}metadata" or child.tag == "metadata":
                parent.remove(child)
    ids = set()
    for element_index, element in enumerate(document.iter()):
        tag = element.tag.removeprefix(f"{{{SVG_NS}}}")
        require(
            tag in SVG_TAGS,
            f"svg: unsupported or active element at position {element_index}; use static SVG text labels",
        )
        element.tag = f"{{{SVG_NS}}}{tag}"
        # Exporter classes must not inherit unrelated board CSS.
        for passive in ("class", "data-cell-id", "pointer-events", "contentStyleType"):
            element.attrib.pop(passive, None)
        if element is document:
            element.attrib.pop("content", None)
        for attribute_index, (key, val) in enumerate(element.attrib.items()):
            name = key.removeprefix("{http://www.w3.org/1999/xlink}")
            require(name in SVG_ATTRS, f"svg: unsupported attribute {attribute_index} at element {element_index}")
            if name == "id":
                require(bool(SVG_ID.fullmatch(val)) and val not in ids, "svg: invalid or duplicate ID")
                ids.add(val)
            elif name == "href":
                require(val.startswith("#") and bool(SVG_ID.fullmatch(val[1:])), "svg: only internal references")
            elif name == "style":
                for declaration in val.split(";"):
                    if not declaration.strip():
                        continue
                    prop, sep, css = declaration.partition(":")
                    require(bool(sep) and prop.strip() in STYLE_PROPS, "svg: unsupported style property")
                    clean = REF.sub("", css)
                    if prop.strip() == "font-family":
                        clean = clean.replace('"', "").replace("'", "")
                    require(bool(re.fullmatch(r"[A-Za-z0-9#.,()%+\-\s]*", clean)), "svg: unsafe style value")
                    require(not re.search(r"url|expression|var\s*\(", clean, re.I), "svg: unsafe style reference")
            else:
                clean = REF.sub("", val)
                require(not re.search(r"url\s*\(|://|\\|[<>]", clean, re.I), "svg: external or unsafe value")
    for element in document.iter():
        for key, val in list(element.attrib.items()):
            name = key.removeprefix("{http://www.w3.org/1999/xlink}")
            if name == "id":
                element.set(key, prefix + val)
            elif name == "href":
                require(val[1:] in ids, "svg: missing internal reference")
                element.set(key, "#" + prefix + val[1:])
            elif name in {"aria-labelledby", "aria-describedby"}:
                require(all(ref in ids for ref in val.split()), "svg: missing accessible label")
                element.set(key, " ".join(prefix + ref for ref in val.split()))
            else:
                refs = REF.findall(val)
                require(all(ref in ids for ref in refs), "svg: missing internal reference")
                element.set(key, REF.sub(lambda m: "url(#" + prefix + m[1] + ")", val))
    label = prefix + "board-label"
    require("board-label" not in ids, "svg: reserved label ID")
    title = ET.Element(f"{{{SVG_NS}}}title", id=label)
    title.text = alt
    document.insert(0, title)
    document.set("role", "img")
    document.set("aria-labelledby", label)
    document.attrib.pop("aria-hidden", None)
    ET.register_namespace("", SVG_NS)
    return ET.tostring(document, encoding="unicode")


def validate_blocks(value: object, root: Path, where: str) -> None:
    require(isinstance(value, list), f"{where}: expected a list of blocks")
    for block_index, block in enumerate(value):
        require(isinstance(block, dict), f"{where}: expected a block object")
        kind = block.get("type")
        if kind in {"paragraph", "heading"}:
            fields(block, {"type", "text"}, set(), where)
            text(block["text"], where)
        elif kind == "list":
            fields(block, {"type", "items"}, {"ordered"}, where)
            require(bool(texts(block["items"], where)), f"{where}: empty list")
            require(isinstance(block.get("ordered", False), bool), f"{where}: ordered must be boolean")
        elif kind == "table":
            fields(block, {"type", "caption", "columns", "rows"}, set(), where)
            text(block["caption"], where)
            columns = texts(block["columns"], where)
            require(bool(columns) and isinstance(block["rows"], list), f"{where}: invalid table")
            for row in block["rows"]:
                cells = texts(row, where)
                require(len(cells) == len(columns), f"{where}: table row/column mismatch")
        elif kind == "code":
            fields(block, {"type", "text"}, {"label"}, where)
            text(block["text"], where)
            if "label" in block:
                text(block["label"], where)
        elif kind == "svg":
            fields(block, {"type", "path", "alt"}, {"caption"}, where)
            try:
                svg_document(block["path"], root, "_check-", text(block["alt"], where))
            except BoardError as exc:
                raise BoardError(f"{where}[{block_index}]: {exc}") from exc
            if "caption" in block:
                text(block["caption"], where)
        elif kind == "link":
            fields(block, {"type", "href", "label"}, set(), where)
            safe_link(block["href"], root, root)
            text(block["label"], where)
        else:
            raise BoardError(f"{where}: unknown block type")


def validate_board(data: object, root: Path) -> dict:
    fields(
        data,
        {"version", "title", "maintainer", "namespace", "items"},
        {"session_names", "terms", "context", "related"},
        "board",
    )
    require(type(data["version"]) is int and data["version"] == 1, "board: unsupported version")
    for key in ("title", "maintainer"):
        text(data[key], "board." + key)
    namespace = data["namespace"]
    require(isinstance(namespace, str), "board.namespace: expected text")
    require(
        not namespace or bool(re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", namespace)), "board: invalid namespace"
    )
    names = {v.casefold() for v in texts(data.get("session_names", []), "session_names")}
    names.add(data["maintainer"].casefold())
    if namespace:
        names.add(namespace.casefold())
    terms = fields(data.get("terms", {}), set(), {"preferred_terms"}, "terms")
    require(isinstance(terms.get("preferred_terms", {}), dict), "preferred_terms: expected an object")
    for term, preferred in terms.get("preferred_terms", {}).items():
        text(term, "preferred_terms")
        text(preferred, "preferred_terms")
    validate_blocks(data.get("context", []), root, "context")
    require(isinstance(data.get("related", []), list), "related: expected a list")
    for link in data.get("related", []):
        fields(link, {"label", "href"}, set(), "related")
        text(link["label"], "related")
        safe_link(link["href"], root, root)
    require(isinstance(data["items"], list), "items: expected a list")
    ids = set()
    common = {"id", "title", "kind", "state", "urgency"}
    optional = {
        "question",
        "purpose",
        "background",
        "owner_reason",
        "consequence",
        "reply",
        "due",
        "blocks",
        "options",
        "recommended",
        "inputs",
        "steps",
        "return_expected",
        "answer",
        "withdrawal",
    }
    for i, item in enumerate(data["items"]):
        where = f"items[{i}]"
        fields(item, common, optional, where)
        item_id = text(item["id"], where + ".id")
        require(bool(ITEM_ID.fullmatch(item_id)) and item_id not in ids, where + ": invalid or duplicate ID")
        prefix = namespace + "-" if namespace else ""
        require(
            bool(re.fullmatch(re.escape(prefix) + r"Q[1-9][0-9]*(?:-[1-9][0-9]*)?", item_id)),
            where + ": wrong namespace",
        )
        ids.add(item_id)
        require(
            item["kind"] in KINDS and item["state"] in STATES and item["urgency"] in URGENCY,
            where + ": invalid kind/state/urgency",
        )
        text(item["title"], where)
        forbidden = {"options", "recommended"} if item["kind"] == "task" else {"inputs", "steps", "return_expected"}
        require(not forbidden.intersection(item), where + ": fields do not match request kind")
        require(
            item["state"] != "preparing" or "reply" not in item, where + ": preparing item must not request a reply"
        )
        require("answer" not in item or item["state"] == "answered", where + ": answer needs answered state")
        require("withdrawal" not in item or item["state"] == "withdrawn", where + ": withdrawal needs withdrawn state")
        require("recommended" not in item or "options" in item, where + ": recommendation needs options")
        for key in (
            "question",
            "purpose",
            "background",
            "owner_reason",
            "consequence",
            "reply",
            "due",
            "inputs",
            "return_expected",
            "withdrawal",
        ):
            if key in item:
                text(item[key], where + "." + key)
        if "reply" in item:
            require(
                bool(re.match(re.escape(item_id) + r"\s*[:：]", item["reply"])),
                where + ": reply must start with its ID and colon",
            )
        validate_blocks(item.get("blocks", []), root, where + ".blocks")
        if item["state"] in {"open", "answered"}:
            required = {"question", "purpose", "background", "owner_reason", "consequence", "reply"}
            require(required <= item.keys(), where + ": incomplete request")
            if item["state"] == "open":
                require("answer" not in item and "withdrawal" not in item, where + ": open item has a resolution")
        if "options" in item:
            require(
                isinstance(item["options"], list) and len(item["options"]) >= 2,
                where + ": provide at least two options",
            )
            codes = set()
            for option in item["options"]:
                fields(option, {"code", "label", "reason", "drawback"}, set(), where + ".options")
                for val in option.values():
                    text(val, where + ".options")
                code = option["code"]
                require(
                    bool(re.fullmatch(r"[A-Za-z0-9]+", code)) and code not in codes,
                    where + ": invalid or duplicate option code",
                )
                require(
                    code.casefold() not in names and option["label"].casefold() not in names,
                    where + ": option conflicts with session name",
                )
                codes.add(code)
            require(item.get("recommended") in codes, where + ": recommendation must identify an option")
        elif item["state"] in {"open", "answered"} and item["kind"] == "decision":
            raise BoardError(where + ": decision requires options and a recommendation")
        if "steps" in item:
            require(isinstance(item["steps"], list) and bool(item["steps"]), where + ": empty steps")
            for step in item["steps"]:
                fields(step, {"title", "blocks"}, set(), where + ".steps")
                text(step["title"], where + ".steps")
                validate_blocks(step["blocks"], root, where + ".steps")
        if item["state"] in {"open", "answered"} and item["kind"] == "task":
            require(
                {"inputs", "steps", "return_expected"} <= item.keys(),
                where + ": task requires inputs, steps and return information",
            )
        if item["state"] == "answered":
            answer = fields(item.get("answer"), {"text", "at", "follow_up", "relays"}, set(), where + ".answer")
            text(answer["text"], where + ".answer")
            try:
                stamp = datetime.fromisoformat(text(answer["at"], where + ".answer.at"))
            except ValueError as exc:
                raise BoardError(where + ": invalid answer timestamp") from exc
            require(stamp.utcoffset() is not None, where + ": answer timestamp needs a timezone")
            follow = fields(answer["follow_up"], {"state", "summary"}, set(), where + ".follow_up")
            require(follow["state"] in {"pending", "done"}, where + ": invalid follow-up state")
            text(follow["summary"], where + ".follow_up")
            require(isinstance(answer["relays"], list), where + ": relays must be a list")
            relay_targets = set()
            for relay in answer["relays"]:
                fields(relay, {"to", "state"}, set(), where + ".relays")
                text(relay["to"], where + ".relays")
                require(relay["to"] not in relay_targets, where + ": duplicate relay target")
                relay_targets.add(relay["to"])
                require(relay["state"] in {"pending", "sent"}, where + ": invalid relay state")
        if item["state"] == "withdrawn":
            require("withdrawal" in item, where + ": withdrawal needs a reason")
    for item_id in ids:
        if re.search(r"Q[0-9]+-[0-9]+$", item_id):
            require(item_id.rsplit("-", 1)[0] in ids, "items: subquestion needs its parent record")
    return data


def badge(css: str, label: str) -> str:
    return f'<span class="pill {css}">{html.escape(label)}</span>'


class Renderer:
    def __init__(self, root: Path, output_dir: Path):
        self.root = root
        self.output_dir = output_dir
        self.count = 0

    def table(
        self,
        caption: str,
        columns: list[str],
        rows: list[list[str]],
        css: str = "options",
        visible_caption: bool = False,
    ) -> str:
        heading = "".join(f'<th scope="col">{html.escape(v)}</th>' for v in columns)
        body = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>" for row in rows)
        caption_class = "" if visible_caption else ' class="sr-only"'
        return (
            f'<div class="table-wrap" tabindex="0" role="region" aria-label="{html.escape(caption, quote=True)}">'
            f'<table class="{css}"><caption{caption_class}>{html.escape(caption)}</caption>'
            f"<thead><tr>{heading}</tr></thead><tbody>{body}</tbody></table></div>"
        )

    def link(self, href: str, label: str) -> str:
        return (
            f'<a href="{html.escape(safe_link(href, self.root, self.output_dir), quote=True)}">{html.escape(label)}</a>'
        )

    def blocks(self, blocks: list[dict], heading_level: int = 4) -> str:
        output = []
        for block in blocks:
            kind = block["type"]
            self.count += 1
            if kind in {"paragraph", "heading"}:
                tag = "p" if kind == "paragraph" else f"h{heading_level}"
                output.append(f"<{tag}>{html.escape(block['text'])}</{tag}>")
            elif kind == "list":
                tag = "ol" if block.get("ordered") else "ul"
                output.append(f"<{tag}>" + "".join(f"<li>{html.escape(v)}</li>" for v in block["items"]) + f"</{tag}>")
            elif kind == "table":
                output.append(
                    self.table(
                        block["caption"],
                        block["columns"],
                        [[html.escape(v) for v in row] for row in block["rows"]],
                        visible_caption=True,
                    )
                )
            elif kind == "code":
                code_id = f"code-{self.count}"
                label = html.escape(block.get("label", "コマンド・コード"))
                output.append(
                    f'<div class="code-box"><div class="code-actions"><span>{label}</span>'
                    f'<button type="button" data-copy="{code_id}" hidden>コードをコピー</button></div>'
                    f'<pre><code id="{code_id}">{html.escape(block["text"])}</code></pre>'
                    '<p class="copy-status" aria-live="polite"></p></div>'
                )
            elif kind == "svg":
                svg = svg_document(block["path"], self.root, f"_diagram-{self.count}-", block["alt"])
                caption = html.escape(block.get("caption", block["alt"]))
                output.append(
                    '<figure class="visual"><div class="visual-scroll" tabindex="0" role="region" '
                    f'aria-label="{html.escape(block["alt"], quote=True)}">{svg}</div>'
                    f"<figcaption>{caption}</figcaption></figure>"
                )
            elif kind == "link":
                output.append("<p>" + self.link(block["href"], block["label"]) + "</p>")
        return "".join(output)

    def urgency(self, item: dict) -> str:
        if item["state"] == "preparing":
            return badge("preparing", "準備中 · 回答不要")
        return badge(*URGENCY[item["urgency"]])

    def card(self, item: dict, archived: bool = False) -> str:
        e = html.escape
        item_id = item["id"] + ("-request" if archived else "")
        preparing = item["state"] == "preparing"
        css = "card prep-card" if preparing else "card"
        result = (
            f'<section class="{css}" id="{item_id}" aria-labelledby="{item_id}-title">'
            f'<header class="card-header"><span class="id">{e(item["id"])}</span>'
            f'<h3 id="{item_id}-title">{e(item["title"])}</h3>'
            + badge(item["kind"], KINDS[item["kind"]])
            + (badge("preparing", "当時の依頼 · 回答不要") if archived else self.urgency(item))
            + '</header><div class="card-body">'
        )
        question = item.get("question", "まだ答えなくて構いません。準備が整ったら提示します。")
        result += f'<p class="ask">{e(question)}</p><dl class="facts">'
        labels = {
            "purpose": "何のために必要か",
            "background": "背景",
            "owner_reason": "あなたに聞く理由",
            "inputs": "入力値",
            "due": "期限",
        }
        result += "".join(f"<dt>{label}</dt><dd>{e(item[key])}</dd>" for key, label in labels.items() if key in item)
        result += "</dl>" + self.blocks(item.get("blocks", []))
        if preparing and ("options" in item or "steps" in item):
            result += "<h4>準備中の草案 · 回答・実行は不要です</h4>"
        if item["kind"] == "decision" and "options" in item:
            options = sorted(item["options"], key=lambda option: option["code"] != item["recommended"])
            rows = []
            for option in options:
                recommended = option["code"] == item["recommended"]
                label = f"<strong>{e(option['code'])} · {e(option['label'])}</strong>"
                if recommended:
                    label += '<br><span class="recommendation">推奨</span>'
                rows.append([label, e(option["reason"]), e(option["drawback"])])
            result += "<h4>選択肢</h4>" + self.table(
                item["id"] + " の選択肢", ["選択肢", "利点・理由", "欠点・条件"], rows
            )
        elif item["kind"] == "task" and "steps" in item:
            result += '<ol class="steps">'
            for step in item["steps"]:
                result += f"<li><strong>{e(step['title'])}</strong>{self.blocks(step['blocks'])}</li>"
            result += "</ol>"
        if "return_expected" in item:
            result += f"<p><strong>終わったら返すこと：</strong>{e(item['return_expected'])}</p>"
        label = "決めないとどうなるか" if item["kind"] == "decision" else "省いたらどうなるか"
        if "consequence" in item:
            result += f'<p class="impact"><strong>{label}：</strong>{e(item["consequence"])}</p>'
        if "reply" in item:
            result += (
                f'<div class="reply"><strong>当時の返信例</strong><code>{e(item["reply"])}</code></div>'
                if archived
                else f'<div class="reply"><strong>返信例</strong><code>{e(item["reply"])}</code></div>'
            )
        return result + "</div></section>"

    def body(self, data: dict, generated_at: str) -> str:
        e = html.escape
        example = next((i["reply"] for i in data["items"] if i["state"] == "open"), "Q番号: 回答")
        result = (
            '<header><p class="eyebrow">OWNER BOARD · オーナー連絡板</p>'
            f'<h1>{e(data["title"])}</h1><p class="meta">最終更新（HTML生成）：{e(generated_at)}'
            f" · 更新担当：{e(data['maintainer'])}</p></header>"
            '<section class="howto" aria-label="答え方と凡例"><div><h2>答え方</h2>'
            f"<p><code>{e(example)}</code> のように番号と回答を送ってください。"
            "連絡板の運用を共有したセッションで受け付けます。"
            "補足や「解説して」も歓迎します。</p>"
            '<p class="report-note">受け取ったセッションが統合役と関係担当への中継を担当します。'
            "中継できない場合は、更新担当へ渡す文と未送信の記録を残します。更新担当へ直接回答しても構いません。</p></div>"
            '<div><h2>急ぎと種類</h2><div class="legend">'
            + badge("now", "今日")
            + badge("soon", "近日")
            + badge("preparing", "準備中 · 回答不要")
            + '</div><div class="legend">'
            + badge("decision", "判断")
            + '<span class="muted">選んでほしい</span>'
            + badge("task", "作業")
            + '<span class="muted">手を動かしてほしい</span></div></div></section>'
        )
        result += self.blocks(data.get("context", []), heading_level=2)
        active = [i for i in data["items"] if i["state"] in {"open", "preparing"}]
        opened = sum(i["state"] == "open" for i in active)
        result += '<div class="section-heading"><h2>開いている項目</h2>'
        result += f'<span class="muted">回答待ち {opened} 件 · 準備中 {len(active) - opened} 件</span></div>'
        if not opened:
            result += '<p class="report-note">いま回答が必要な項目はありません。</p>'
        if active:
            rows = []
            for item in active:
                if item["state"] == "preparing":
                    next_action = "今は回答不要。準備中"
                elif item["kind"] == "decision":
                    option = next(o for o in item["options"] if o["code"] == item["recommended"])
                    next_action = option["code"] + "：" + option["label"]
                else:
                    next_action = f"{len(item['steps'])} 手順。確認結果を返信"
                due = "<br>" + e(item["due"]) if "due" in item and item["state"] != "preparing" else ""
                rows.append(
                    [
                        f'<a class="id" href="#{item["id"]}">{item["id"]}</a>',
                        self.urgency(item) + due,
                        badge(item["kind"], KINDS[item["kind"]]),
                        e(item["title"]),
                        e(next_action),
                    ]
                )
            result += self.table(
                "開いている項目の一覧", ["番号", "急ぎ", "種類", "お願いしたいこと", "推奨・次の対応"], rows, "overview"
            )
            result += "".join(self.card(i) for i in active)
        history = [i for i in data["items"] if i["state"] in {"answered", "withdrawn"}]
        pending = []
        for item in history:
            if item["state"] != "answered":
                continue
            answer = item["answer"]
            parts = []
            if answer["follow_up"]["state"] == "pending":
                parts.append("反映待ち：" + answer["follow_up"]["summary"])
            relays = [r["to"] for r in answer["relays"] if r["state"] == "pending"]
            if relays:
                parts.append("中継待ち：" + "、".join(relays))
            if parts:
                pending.append(f"<p><strong>{item['id']}：</strong>{e(' / '.join(parts))}。</p>")
        if pending:
            result += (
                '<section class="pending"><h2>回答は受領済み · 対応が残っています</h2>'
                + "".join(pending)
                + "</section>"
            )
        result += "<h2>回答済み・取り下げの記録</h2>"
        if history:
            rows = []
            for item in history:
                if item["state"] == "answered":
                    answer = item["answer"]
                    resolution = e(answer["text"]) + " → " + e(answer["follow_up"]["summary"])
                    resolution += f'<br><span class="muted">{e(answer["at"])}</span>'
                    if answer["relays"]:
                        resolution += "<br>" + e(
                            " / ".join(
                                r["to"] + ("：共有済み" if r["state"] == "sent" else "：中継待ち")
                                for r in answer["relays"]
                            )
                        )
                else:
                    resolution = "取り下げ：" + e(item["withdrawal"])
                rows.append([f'<span id="{item["id"]}" class="id">{item["id"]}</span>', e(item["title"]), resolution])
            result += f'<details class="archive"><summary>回答と、その後の対応を見る · {len(history)} 件</summary>'
            result += self.table("回答・取り下げと対応結果", ["番号", "項目", "回答と、その後の対応"], rows)
            for item in history:
                if "question" in item:
                    result += (
                        "<details><summary>"
                        + e(item["id"])
                        + "：当時の問い・選択肢・手順を見る</summary>"
                        + self.card(item, archived=True)
                        + "</details>"
                    )
            result += "</details>"
        else:
            result += '<p class="muted">記録はまだありません。</p>'
        if data.get("related"):
            result += '<h2>関連資料</h2><div class="related">'
            result += (
                "".join("<p>" + self.link(link["href"], link["label"]) + "</p>" for link in data["related"]) + "</div>"
            )
        return result


def render_board(data: dict, root: Path, output_dir: Path, generated_at: str | None = None) -> str:
    validate_board(data, root)
    stamp = generated_at or datetime.now().astimezone().isoformat(timespec="seconds")
    body = Renderer(root, output_dir).body(data, stamp)
    template = (ASSETS / "board-template.html").read_text(encoding="utf-8")
    # Replace template tokens in one pass; data containing token text stays literal.
    values = {"TITLE": html.escape(data["title"]), "BODY": body}
    return re.sub(r"\{\{(TITLE|BODY)\}\}", lambda match: values[match[1]], template)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "render"):
        child = sub.add_parser(command)
        child.add_argument("--data", required=True, type=Path)
        if command == "render":
            child.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        source = args.data.resolve()
        try:
            data = json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
        except json.JSONDecodeError as exc:
            raise BoardError(f"data: malformed JSON at line {exc.lineno}, column {exc.colno}") from exc
        validate_board(data, source.parent)
        if args.command == "render":
            require(
                args.output.suffix.lower() == ".html" and not args.output.is_symlink(),
                "output: expected a regular HTML path",
            )
            output = args.output.resolve()
            require(output != source, "output: cannot overwrite source data")
            require(output.parent == source.parent, "output: keep HTML beside source data and supplementary materials")
            document = render_board(data, source.parent, output.parent)
            output.parent.mkdir(parents=True, exist_ok=True)
            publication_mode = stat.S_IMODE(output.stat().st_mode) if output.exists() else 0o600
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, delete=False) as file:
                    temporary = Path(file.name)
                    file.write(document)
                temporary.chmod(publication_mode)
                os.replace(temporary, output)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            print(output)
        else:
            print("owner-board validation: PASS")
        return 0
    except (BoardError, OSError, ValueError, TypeError) as exc:
        # Avoid printing JSON/XML payloads in parser errors.
        message = str(exc) if isinstance(exc, BoardError) else "cannot read or process board data"
        print("owner-board error: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
