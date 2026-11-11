#!/usr/bin/env python3
"""計画 JSON（最大24時間）と目標 JSON から、作業の進捗ページ（自己完結の HTML）を書き出す。

使い方: python3 render.py <YYYY-MM-DD_HHMM.json> [--out <path>] [--watch <分>]

手順の状態は check（GitHub・監視ファイルからの自動判定）→ 手動の state → 未着手 の順に決める。
入力が不正なときは理由を標準エラーに出して終了コード 1 で終わり、既存の HTML は書き換えない。
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import subprocess
import sys
import time
from collections.abc import Callable

STATE_ORDER = ("done", "doing", "waiting", "blocked", "todo")
STATE_LABELS = {
    "done": "完了",
    "doing": "進行中",
    "waiting": "待ち",
    "blocked": "止まっている",
    "todo": "未着手",
}
GhRunner = Callable[[list[str]], "str | None"]
REF_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
TIME_PATTERN = re.compile(r"(\d{1,2}):(\d{2})")


class PlanError(ValueError):
    """計画ファイルの内容が描画できない形のとき。"""


def run_gh(args: list[str]) -> str | None:
    try:
        out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


# ---------- 状態の判定 ----------


def _load_json(raw: str | None):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _join(*parts: str | None) -> str:
    return "・".join(p for p in parts if p)


def judge(step: dict, *, repo: str | None, base: pathlib.Path, gh: GhRunner) -> tuple[str, str]:
    """手順の状態と注記を返す。判定できないときは手動の state、それも無ければ未着手。"""
    manual = step.get("state")
    note = step.get("note", "")
    wait = step.get("waitLabel")
    fallback = manual or "todo"
    check = step.get("check")
    if not check:
        return fallback, note
    kind, _, arg = check.partition(":")
    if kind in ("pr-merged", "pr-closed", "pr-ci", "run-success") and not repo:
        return fallback, note or "repo が未指定のため自動判定できない"
    if kind == "pr-merged":
        pr = _load_json(gh(["pr", "view", arg, "--repo", repo, "--json", "state"]))
        if not pr:
            return fallback, note or "PRの状態を取得できない"
        if pr.get("state") == "MERGED":
            return "done", f"#{arg} merge済み"
        if pr.get("state") == "CLOSED":
            return "blocked", f"#{arg} がmergeされずに閉じた"
        if wait:
            return "waiting", _join(wait, note)
        return manual or "doing", note or f"#{arg} open"
    if kind == "pr-closed":
        pr = _load_json(gh(["pr", "view", arg, "--repo", repo, "--json", "state"]))
        if pr and pr.get("state") in ("CLOSED", "MERGED"):
            return "done", f"#{arg} close済み"
        return fallback, note
    if kind == "pr-ci":
        checks = _load_json(gh(["pr", "checks", arg, "--repo", repo, "--json", "bucket"]))
        if checks is None:
            return fallback, note or "CIの状態を取得できない"
        buckets = [c.get("bucket") for c in checks]
        if "fail" in buckets:
            return "blocked", "CI失敗あり"
        if "pending" in buckets:
            return "doing", "CI実行中"
        if buckets:
            return "done", "CI green"
        return fallback, note or "CI未実行"
    if kind == "run-success":
        run = _load_json(gh(["run", "view", arg, "--repo", repo, "--json", "status,conclusion"]))
        if not run:
            return fallback, note or "実行の状態を取得できない"
        if run.get("status") != "completed":
            return "doing", "実行中"
        if run.get("conclusion") == "success":
            return "done", f"run {arg} 成功"
        return "blocked", f"run {arg} {run.get('conclusion')}"
    if kind == "file-nonempty":
        path = pathlib.Path(arg).expanduser()
        if not path.is_absolute():
            path = base / path
        text = path.read_text(errors="replace").strip() if path.is_file() else ""
        if text:
            return "done", text.splitlines()[-1]
        return "waiting", _join(wait, note) or "待ち"
    return fallback, note or f"未知の check: {check}"


# ---------- 入力の検証 ----------


DAY = 24 * 60


def _clock(value: str, where: str) -> int:
    """HH:MM を 0 時からの分にする。"""
    match = TIME_PATTERN.fullmatch(str(value))
    if not match or int(match[1]) > 24 or int(match[2]) > 59 or int(match[1]) * 60 + int(match[2]) > DAY:
        raise PlanError(f"{where}: 時刻は HH:MM で書く（受け取った値: {value!r}）")
    return int(match[1]) * 60 + int(match[2])


def _datetime(value: str, where: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise PlanError(f"{where}: 日時はタイムゾーン付きの ISO 8601 で書く（受け取った値: {value!r}）") from exc
    if parsed.tzinfo is None:
        raise PlanError(f"{where}: タイムゾーンが無い（例 2026-11-11T20:00+09:00）")
    return parsed


class Period:
    """計画の期間（最大24時間）。HH:MM は開始以降で最初に来るその時刻として読む。"""

    def __init__(self, day: dict) -> None:
        for key in ("start", "end"):
            if key not in day:
                raise PlanError(f"計画に {key} が無い")
        self.start = _datetime(day["start"], "start")
        self.end = _datetime(day["end"], "end").astimezone(self.start.tzinfo)
        self.span = int((self.end - self.start).total_seconds() // 60)
        if not 0 < self.span <= DAY:
            raise PlanError("end は start より後で、24時間以内にする")
        self.origin = self.start.hour * 60 + self.start.minute

    def offset(self, value: str, where: str) -> int:
        """開始からの分。"""
        return (_clock(value, where) - self.origin) % DAY

    def interval(self, start: str, end: str, where: str) -> tuple[int, int]:
        a = self.offset(start, f"{where}.start")
        b = self.offset(end, f"{where}.end")
        return a, b if b > a else b + DAY

    def now_offset(self, now: dt.datetime) -> int | None:
        minutes = (now - self.start).total_seconds() / 60
        return int(minutes) if 0 <= minutes <= self.span else None


def _validate(day: dict, goals: dict | None) -> None:
    if "lanes" not in day:
        raise PlanError("計画に lanes が無い")
    Period(day)
    stages = goals.get("stages", []) if goals else []
    goal_ids = {g["id"] for g in goals.get("goals", [])} if goals else set()
    for goal in goals.get("goals", []) if goals else []:
        for key in ("reached", "target"):
            if goal.get(key) is not None and goal[key] not in stages:
                raise PlanError(f"目標 {goal['id']} の {key} が段階に無い: {goal[key]!r}")
    for lane in day["lanes"]:
        if not lane.get("steps"):
            raise PlanError(f"作業 {lane.get('name')!r} に手順が無い")
        for step in lane["steps"]:
            if step.get("state") and step["state"] not in STATE_LABELS:
                raise PlanError(f"手順 {step.get('label')!r} の state が不正: {step['state']!r}")
        advances = lane.get("advances")
        if advances:
            if advances.get("goal") not in goal_ids:
                raise PlanError(f"作業 {lane['name']!r} が進める目標が goals に無い: {advances.get('goal')!r}")
            if advances.get("stage") not in stages:
                raise PlanError(f"作業 {lane['name']!r} が進める段階が stages に無い: {advances.get('stage')!r}")


# ---------- 部品 ----------

esc = html.escape


_C0_AND_SPACE = "".join(map(chr, range(0x21)))


def safe_href(href: str | None) -> str | None:
    """https: と相対パスだけをリンクにする。

    ブラウザはURLの中のタブ・改行と、前後の制御文字・空白を捨て、\\ を / として読む。判定の前に同じ正規化をし、
    正規化した値を出す。そうしないと "java\\tscript:" のような値が相対パスとして通り抜ける。
    """
    if not href:
        return None
    cleaned = re.sub(r"[\t\n\r]", "", href).strip(_C0_AND_SPACE)
    cleaned = cleaned.replace("\\", "/")
    lowered = cleaned.lower()
    if lowered.startswith("https://"):
        return cleaned
    if ":" in lowered.split("/", 1)[0] or lowered.startswith("//"):
        return None
    return cleaned or None


def link(text: str, href: str | None) -> str:
    safe = safe_href(href)
    return f'<a href="{esc(safe)}">{esc(text)}</a>' if safe else esc(text)


def chip(state: str) -> str:
    return f'<span class="chip s-{state}">{STATE_LABELS[state]}</span>'


def stacked_bar(counts: dict[str, int], total: int, height: int) -> str:
    parts = "".join(
        f'<span class="seg s-{key}" style="width:{counts[key] / total * 100:.4f}%"></span>'
        for key in STATE_ORDER
        if counts.get(key)
    )
    label = "・".join(f"{STATE_LABELS[k]} {counts.get(k, 0)}" for k in STATE_ORDER)
    return f'<div class="bar" style="height:{height}px" role="img" aria-label="{label}">{parts}</div>'


def breakdown(counts: dict[str, int], total: int) -> str:
    return f"全{total}手順のうち " + "・".join(f"{STATE_LABELS[k]} {counts.get(k, 0)}" for k in STATE_ORDER)


def ref_link(ref: str | None, board: str | None) -> str:
    if not ref:
        return ""
    if not REF_PATTERN.fullmatch(ref):
        raise PlanError(f"ref は Q番号などの英数字とハイフンで書く（受け取った値: {ref!r}）")
    href = f"{board}#{ref}" if board else None
    return f'<span class="ref">（連絡板 {link(ref, href)}）</span>'


def period_label(period: Period) -> str:
    start, end = period.start, period.end
    head = f"{start.month}/{start.day} {start:%H:%M}"
    if end.date() == start.date():
        return f"{head}〜{end:%H:%M}"
    return f"{head}〜{end.month}/{end.day} {end:%H:%M}"


def lane_anchor(index: int) -> str:
    return f"lane-{index + 1}"


# ---------- 月の全体像 ----------


def render_goals(goals: dict, lanes: list[dict]) -> str:
    stages = goals["stages"]
    today_by_goal: dict[str, list[tuple[int, str, str]]] = {}
    for index, lane in enumerate(lanes):
        adv = lane.get("advances")
        if adv:
            today_by_goal.setdefault(adv["goal"], []).append((index, adv["stage"], lane["name"]))
    head = "".join(f'<th scope="col">{esc(s)}</th>' for s in stages)
    rows = []
    met = 0
    for goal in goals["goals"]:
        reached = stages.index(goal["reached"]) if goal.get("reached") else -1
        target = stages.index(goal["target"])
        if reached >= target:
            met += 1
        cells = []
        for i, stage in enumerate(stages):
            if i <= reached:
                cls, text = "g-done", "済"
            elif i == reached + 1:
                cls, text = "g-now", "いま"
            elif i <= target:
                cls, text = "g-left", "残り"
            else:
                cls, text = "g-out", "—"
            mark = '<span class="target">◆期限の目標</span>' if i == target else ""
            todays = "".join(
                f'<a class="today" href="#{lane_anchor(idx)}">▲今回：{esc(name)}</a>'
                for idx, st, name in today_by_goal.get(goal["id"], [])
                if st == stage
            )
            cells.append(f'<td class="{cls}"><span class="gs">{text}</span>{mark}{todays}</td>')
        gap = target - reached
        gap_text = "目標に到達" if gap <= 0 else f"あと{gap}段階"
        note = f'<div class="gnote">{esc(goal["note"])}</div>' if goal.get("note") else ""
        rows.append(
            f'<tr><th scope="row">{esc(goal["name"])}<div class="gap">{gap_text}</div>{note}</th>{"".join(cells)}</tr>'
        )
    source = goals.get("source") or {}
    source_html = f"・元の計画：{link(source.get('label', '計画'), source.get('href'))}" if source.get("href") else ""
    end = f"・期限 {esc(goals['periodEnd'])}" if goals.get("periodEnd") else ""
    return (
        f"<h2>{esc(goals.get('title', '期間の目標'))}：期限の目標に届いたのは {met}/{len(goals['goals'])}</h2>"
        f'<p class="meta">段階は左から順に進む{end}{source_html}</p>'
        f'<div class="card scroll"><table class="goals"><thead><tr><th scope="col">目標</th>{head}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>"
        '<p class="legend"><span class="key g-done">済</span><span class="key g-now">いま</span>'
        '<span class="key g-left">残り（期限までに進める）</span><span class="key g-out">—（今期は対象外）</span>'
        "◆は期限までに到達したい段階、▲はこの計画の作業が進める段階</p></div>"
    )


# ---------- タイムライン ----------


def render_timeline(day: dict, lanes: list[dict], period: Period, now_min: int | None) -> str:
    span = period.span

    def pos(minute: int) -> float:
        return min(max(minute, 0), span) / span * 100

    def band(cls: str, a: int, b: int, title: str) -> str:
        left, right = pos(a), pos(b)
        if right <= left:
            return ""
        return (
            f'<span class="tl-bar {cls}" style="left:{left:.3f}%;width:{right - left:.3f}%" '
            f'title="{esc(title)}"></span>'
        )

    def span_text(item: dict, where: str, open_end: int | None) -> tuple[int, int, str] | None:
        if not item or not item.get("start"):
            return None
        if item.get("end"):
            a, b = period.interval(item["start"], item["end"], where)
            return a, b, f"{item['start']}–{item['end']}"
        a = period.offset(item["start"], f"{where}.start")
        b = open_end if open_end is not None else a
        return a, max(a, b), f"{item['start']}–"

    # 目盛りは長い期間ほど間引き、ラベルが重ならないようにする。
    step = 60 if span <= 8 * 60 else 120 if span <= 16 * 60 else 180
    first_hour = (60 - period.origin % 60) % 60
    ticks = []
    for minute in range(first_hour, span + 1, step):
        at = period.start + dt.timedelta(minutes=minute)
        text = f"{at.month}/{at.day} 0:00" if at.hour == 0 else f"{at.hour}:00"
        edge = " at-start" if minute == 0 else " at-end" if minute == span else ""
        ticks.append(f'<span class="tick{edge}" style="left:{pos(minute):.3f}%">{text}</span>')
    overlay, constraint_texts = [], []
    for i, c in enumerate(day.get("constraints", [])):
        constraint_texts.append(f"{c['label']} {c['start']}–{c['end']}")
        a, b = period.interval(c["start"], c["end"], f"constraints[{i}]")
        # 制約は毎日繰り返す。期間の開始より前に始まった回も、期間に掛かる分を描く。
        for shift in (-DAY, 0):
            left, right = pos(a + shift), pos(b + shift)
            if right > left:
                overlay.append(
                    f'<span class="tl-constraint" style="left:{left:.3f}%;width:{right - left:.3f}%" '
                    f'title="{esc(constraint_texts[-1])}"></span>'
                )
    if now_min is not None:
        now_text = f"{period.start + dt.timedelta(minutes=now_min):%H:%M}"
        overlay.append(f'<span class="tl-now" style="left:{pos(now_min):.3f}%"><span>現在 {now_text}</span></span>')
    end = span

    rows = []
    for index, lane in enumerate(lanes):
        where = f"lanes[{index}]"
        plan = span_text(lane.get("plan") or {}, f"{where}.plan", None)
        # 実績は中断と再開を表せるよう、区間の配列でも書ける。
        raw = lane.get("actual") or []
        raw = raw if isinstance(raw, list) else [raw]
        actuals = [
            interval
            for i, item in enumerate(raw)
            if (interval := span_text(item or {}, f"{where}.actual[{i}]", now_min))
        ]
        if not plan and not actuals:
            continue
        bars, texts = [], []
        if plan:
            bars.append(band("tl-plan", plan[0], plan[1], f"予定 {plan[2]}"))
            texts.append(f"予定 {plan[2]}")
        for actual in actuals:
            bars.append(band("tl-actual", actual[0], actual[1], f"実績 {actual[2]}"))
        if actuals:
            texts.append("実績 " + "、".join(a[2] for a in actuals))
        rows.append(
            f'<div class="tl-row"><div class="tl-label"><a href="#{lane_anchor(index)}">{esc(lane["name"])}</a>'
            f'<span class="tl-time">{esc("・".join(texts))}</span></div>'
            f'<div class="tl-track">{"".join(bars)}</div></div>'
        )
    board = day.get("ownerBoard")
    for index, wait in enumerate(day.get("waits", [])):
        item = span_text(wait, f"waits[{index}]", end)
        if not item:
            continue
        rows.append(
            f'<div class="tl-row"><div class="tl-label"><span class="pill caution">待ち</span> {esc(wait["label"])}'
            f'{ref_link(wait.get("ref"), board)}<span class="tl-time">{esc(item[2])}</span></div>'
            f'<div class="tl-track">{band("tl-wait", item[0], item[1], "待ち " + item[2])}</div></div>'
        )
    if not rows and not constraint_texts:
        return ""
    constraint_html = (
        f'<p class="constraints"><span class="label">守る時間制約</span> {esc("、".join(constraint_texts))}</p>'
        if constraint_texts
        else ""
    )
    changes = day.get("changes", [])
    change_html = ""
    if changes:
        items = "".join(f'<li><span class="num">{esc(c["at"])}</span> {esc(c["text"])}</li>' for c in changes)
        change_html = f'<h3>計画の変更</h3><ul class="changes">{items}</ul>'
    return (
        f"<h2>タイムライン（{esc(period_label(period))}）</h2>"
        f'<div class="card scroll tl-card"><div class="tl">'
        f'<div class="tl-row tl-axis"><div class="tl-label"></div><div class="tl-track">{"".join(ticks)}</div></div>'
        f'<div class="tl-body"><div class="tl-overlay"><div class="tl-label"></div><div class="tl-track">'
        f"{''.join(overlay)}</div></div>{''.join(rows)}</div></div>"
        '<p class="legend"><span class="key tl-plan">予定</span><span class="key tl-actual">実績</span>'
        '<span class="key tl-wait">待ち（外部要因）</span><span class="key tl-constraint-key">守る時間制約</span>'
        f"縦線は現在時刻</p>{constraint_html}{change_html}</div>"
    )


# ---------- 作業の進捗 ----------


def render_lanes(day: dict, judged: list[list[tuple[dict, str, str]]], goals: dict | None) -> tuple[str, str]:
    board = day.get("ownerBoard")
    goal_names = {g["id"]: g["name"] for g in goals.get("goals", [])} if goals else {}
    total_counts: dict[str, int] = {}
    total = 0
    summary_rows, sections = [], []
    for index, (lane, steps) in enumerate(zip(day["lanes"], judged, strict=True)):
        counts: dict[str, int] = {}
        items = []
        next_step = None
        for step, state, note in steps:
            counts[state] = counts.get(state, 0) + 1
            if state != "done" and next_step is None:
                next_step = (step, state, note)
            items.append(
                f'<li>{chip(state)}<span class="step{" is-done" if state == "done" else ""}">'
                f"{esc(step['label'])}</span>"
                f'<span class="note">{esc(note)}{ref_link(step.get("ref"), board)}</span></li>'
            )
        n = len(steps)
        done = counts.get("done", 0)
        pct = round(done / n * 100)
        total += n
        for key, value in counts.items():
            total_counts[key] = total_counts.get(key, 0) + value
        if next_step is None:
            nxt = "すべて完了"
        else:
            step, state, note = next_step
            nxt = f"{esc(step['label'])}（{STATE_LABELS[state]}{'・' + esc(note) if note else ''}）"
            nxt += ref_link(step.get("ref"), board)
        adv = lane.get("advances")
        adv_html = ""
        if adv:
            goal_name = goal_names.get(adv["goal"], adv["goal"])
            adv_html = f'<p class="meta">進める目標：{esc(goal_name)} の {esc(adv["stage"])}</p>'
        anchor = lane_anchor(index)
        summary_rows.append(
            f'<tr><th scope="row"><a href="#{anchor}">{esc(lane["name"])}</a></th>'
            f'<td class="pct num">{pct}%</td><td class="barcell">{stacked_bar(counts, n, 12)}</td>'
            f'<td class="num nowrap">{done}/{n}</td><td class="next">{nxt}</td></tr>'
        )
        goal_line = f'<p class="goal">{esc(lane["goal"])}</p>' if lane.get("goal") else ""
        sections.append(
            f'<section class="card lane" id="{anchor}"><h3>{esc(lane["name"])} <span class="pct num">{pct}%</span></h3>'
            f"{goal_line}{adv_html}{stacked_bar(counts, n, 8)}<ol>{''.join(items)}</ol></section>"
        )
    overall = round(total_counts.get("done", 0) / total * 100)
    hero = (
        f"<h2>作業の進捗：{total}手順のうち{total_counts.get('done', 0)}が完了</h2>"
        f'<div class="card hero"><div class="big num">{overall}%</div><div class="hero-bar">'
        f'{stacked_bar(total_counts, total, 20)}<p class="meta">{breakdown(total_counts, total)}</p></div></div>'
        f'<p class="legend">{"".join(f"{chip(k)}" for k in STATE_ORDER)}</p>'
        '<div class="card table"><table class="summary"><thead><tr><th scope="col">作業</th><th scope="col">進捗</th>'
        '<th scope="col">内訳</th><th scope="col">手順</th><th scope="col">次の一手</th></tr></thead>'
        f"<tbody>{''.join(summary_rows)}</tbody></table></div>"
    )
    return hero, "".join(sections)


# ---------- ページ ----------

def reload_script(seconds: int) -> str:
    """見ていない間だけページを読み込み直す script。0以下なら読み込み直さない。

    meta refresh は読んでいる途中でもページを差し替え、読み上げ・フォーカス・スクロールの位置を失わせる
    （WCAG 2.2.1）。タブが裏にある間に古くなったら読み込み直し、前面に戻ったときに古ければそこで読み込み直す。
    外から来た値を含まない固定の文で、数値だけを埋め込む。
    """
    if seconds <= 0:
        return ""
    ms = seconds * 1000
    return (
        "<script>(()=>{const loaded=Date.now();"
        f"const stale=()=>Date.now()-loaded>={ms};"
        "const reload=()=>{if(stale())location.reload()};"
        f"setInterval(()=>{{if(document.hidden)reload()}},{min(ms, 60000)});"
        'document.addEventListener("visibilitychange",()=>{if(!document.hidden)reload()})})()</script>'
    )


CSS = """
:root{color-scheme:light;--accent:#2563eb;--accent-text:#1d4ed8;--accent-tint:#eff4ff;--accent-border:#bfd3fe;
--caution:#c2410c;--caution-text:#9a3412;--caution-tint:#fff4ec;--caution-border:#fed7aa;--text:#1f2937;
--text-2:#4b5563;--text-3:#6b7280;--line:#64748b;--border:#e5e7eb;--border-strong:#d1d5db;--node-border:#cbd5e1;
--neutral-tint:#f3f4f6;--neutral-text:#374151;--bg:#f6f7f9;--surface:#fff;
--shadow-1:0 1px 2px rgba(16,24,40,.04),0 1px 3px rgba(16,24,40,.06);
--font-sans:"Hiragino Sans","Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic UI",Meiryo,system-ui,sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.75 var(--font-sans);letter-spacing:.02em;
line-break:strict;overflow-wrap:anywhere}
main{max-width:1160px;margin:0 auto;padding:32px 40px 80px}
h1,h2,h3{font-feature-settings:"palt";text-wrap:balance;letter-spacing:.01em}
h1{font-size:28px;line-height:1.35;margin:0 0 4px}h2{font-size:20px;line-height:1.45;margin:40px 0 12px}
h3{font-size:16px;margin:0 0 4px}a{color:var(--accent-text)}
.meta{color:var(--text-2);font-size:14px;margin:0 0 8px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow-1);
padding:24px;margin-bottom:16px}
.scroll{overflow-x:auto}.num{font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse}
th,td{padding:10px 12px;border-bottom:1px solid var(--border);text-align:left;vertical-align:middle}
thead th{font-size:13px;font-weight:600;color:var(--text-2);border-bottom-color:var(--border-strong)}
.legend{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;font-size:13px;color:var(--text-2);margin:12px 0 0}
.chip,.pill{display:inline-block;border-radius:999px;padding:2px 8px;font-size:12px;font-weight:600;
text-align:center;white-space:nowrap;border:1px solid transparent}
.s-done{background:var(--accent);color:#fff}
.s-doing{background:var(--accent-tint);color:var(--accent-text);border-color:var(--accent-border)}
.s-waiting{background:var(--caution-tint);color:var(--caution-text);border-color:var(--caution-border)}
.s-blocked{background:var(--caution);color:#fff}
.s-todo{background:var(--neutral-tint);color:var(--neutral-text);border-color:var(--border-strong)}
.pill.caution{background:var(--caution-tint);color:var(--caution-text)}
.bar{display:flex;width:100%;background:var(--neutral-tint);border-radius:999px;overflow:hidden}
.seg{display:block;height:100%}.seg.s-doing{background:var(--accent-border)}.seg.s-waiting{background:var(--caution-border)}
.seg.s-todo{background:var(--border-strong)}
.hero{display:flex;align-items:center;gap:24px}.big{font-size:48px;font-weight:700;line-height:1}
.hero-bar{flex:1}.hero-bar .meta{margin:8px 0 0}
.card.table{padding:8px 24px}.nowrap{white-space:nowrap}.summary .pct{font-weight:700;width:72px;white-space:nowrap}
.barcell{width:26%}.next{font-size:14px}
.lane .pct{color:var(--text-2);font-size:14px;margin-left:4px}.goal{color:var(--text-2);font-size:14px;margin:0 0 4px}
.lane ol{list-style:none;padding:0;margin:12px 0 0}
.lane li{display:grid;grid-template-columns:104px minmax(0,1fr) minmax(0,1fr);gap:12px;padding:6px 0;align-items:center;
border-top:1px solid var(--border)}
.step.is-done{color:var(--text-3)}.note{color:var(--text-2);font-size:14px}.ref{font-size:14px}
.goals th[scope=row]{min-width:180px}.goals td{text-align:center;font-size:14px;min-width:120px}
.gs{display:block;font-weight:600}.gap{font-size:13px;color:var(--text-2);font-weight:400}
.gnote{font-size:13px;color:var(--text-3);font-weight:400}
.g-done{background:var(--accent);color:#fff}.g-now{background:var(--accent-tint);color:var(--accent-text);
box-shadow:inset 0 0 0 2px var(--accent)}.g-left{background:var(--surface);color:var(--text-2);
box-shadow:inset 0 0 0 1px var(--node-border)}.g-out{background:var(--neutral-tint);color:var(--text-2)}
.goals td+td{border-left:4px solid var(--surface)}
.target{display:block;font-size:12px;font-weight:600}.g-done .target{color:#fff}
.today{display:block;font-size:12px;font-weight:600;color:var(--caution-text)}.g-done .today{color:#fff}
.key{display:inline-block;border-radius:6px;padding:0 8px;font-size:12px;font-weight:600}
.tl{min-width:900px}.tl-row{display:grid;grid-template-columns:240px 1fr;gap:12px;align-items:center;min-height:40px}
.tl-label{font-size:14px;line-height:1.5}.tl-time{display:block;font-size:12px;color:var(--text-2)}
.tl-track{position:relative;height:28px}
.tl-axis .tl-track{height:20px;border-bottom:1px solid var(--line)}
.tick{position:absolute;bottom:2px;transform:translateX(-50%);font-size:12px;color:var(--text-2);white-space:nowrap}
.tick.at-start{transform:none}.tick.at-end{transform:translateX(-100%)}
.tl-body{position:relative;margin-bottom:20px}
.tl-overlay{position:absolute;inset:0;display:grid;grid-template-columns:240px 1fr;gap:12px;
pointer-events:none}
.tl-overlay .tl-track{height:100%}
.tl-bar{position:absolute;top:4px;height:20px;border-radius:4px}
.tl-plan{background:var(--surface);border:1.5px dashed var(--line)}
.tl-actual{top:9px;height:10px;background:var(--accent)}
.tl-wait{background:var(--caution-tint);border:1.5px solid var(--caution)}
.tl-constraint,.tl-constraint-key{
background:repeating-linear-gradient(135deg,var(--caution-border) 0 2px,transparent 2px 8px)}
.tl-constraint{position:absolute;top:0;bottom:0;border-left:1px solid var(--caution-border);
border-right:1px solid var(--caution-border)}
.tl-now{position:absolute;top:0;bottom:-20px;border-left:2px solid var(--text)}
.tl-now>span{position:absolute;bottom:0;left:4px;font-size:12px;font-weight:600;background:var(--surface);padding:0 4px;
white-space:nowrap}
.key.tl-plan,.key.tl-wait{position:static}.key.tl-actual{position:static;height:auto;color:#fff}
.key.tl-constraint-key{color:var(--caution-text)}
.changes{margin:0;padding-left:20px;font-size:14px}.tl-card h3{margin-top:16px}
.constraints{font-size:14px;margin:8px 0 0;color:var(--caution-text)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
"""


def render(
    day: dict,
    goals: dict | None,
    *,
    now: dt.datetime,
    gh: GhRunner = run_gh,
    base: pathlib.Path | None = None,
) -> str:
    """計画と目標から HTML 全体を返す。now は計画のタイムゾーンでの現在時刻。"""
    _validate(day, goals)
    base = base or pathlib.Path.cwd()
    judged = [
        [(step, *judge(step, repo=day.get("repo"), base=base, gh=gh)) for step in lane["steps"]]
        for lane in day["lanes"]
    ]
    period = Period(day)
    now = now.astimezone(period.start.tzinfo)
    left = period.end - now
    end_text = f"{period.end.month}/{period.end.day} {period.end:%H:%M}"
    if left.total_seconds() <= 0:
        left_text = f"計画の終わり（{end_text}）を過ぎた"
    else:
        hours, rest = divmod(int(left.total_seconds()) // 60, 60)
        left_text = f"計画の終わり（{end_text}）まで {hours}時間{rest}分"
    links = []
    source = day.get("source") or {}
    if source.get("href"):
        links.append("元の計画：" + link(source.get("label", "計画"), source["href"]))
    if day.get("ownerBoard"):
        links.append(link("連絡板", day["ownerBoard"]))
    title = day.get("title") or f"{period_label(period)} の作業"
    hero, sections = render_lanes(day, judged, goals)
    refresh = max(0, int(day.get("refreshSeconds", 300)))
    tz_name = now.strftime("%Z") or now.strftime("UTC%z")
    meta = "・".join([f"更新 {now.month}/{now.day} {now:%H:%M}（{esc(tz_name)}）", esc(left_text), *links])
    parts = [
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">',
        f'<meta name="color-scheme" content="light"><title>{esc(title)}</title><style>{CSS}</style></head><body><main>',
        f'<h1>{esc(title)}</h1><p class="meta">{meta}</p>',
        # 開いてすぐ見たいのは今回の進捗なので先頭に置き、取り組み全体の目標は最後に回す。
        hero,
        render_timeline(day, day["lanes"], period, period.now_offset(now)),
        "<h2>作業ごとの手順</h2>",
        sections,
        render_goals(goals, day["lanes"]) if goals else "",
        f"</main>{reload_script(refresh)}</body></html>",
    ]
    return "".join(parts)


def render_once(plan_path: pathlib.Path, out: pathlib.Path | None) -> tuple[int, dt.datetime | None]:
    """1回描画する。入力が不正なら既存の HTML を残して 1 を返す。2つ目は計画の終わり。"""
    try:
        day = json.loads(plan_path.read_text())
        goals = None
        if day.get("goals"):
            goals = json.loads((plan_path.parent / day["goals"]).read_text())
        period = Period(day)
        now = dt.datetime.now(period.start.tzinfo)
        page = render(day, goals, now=now, base=plan_path.parent)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f"描画できない: {exc}", file=sys.stderr)
        return 1, None
    out = out or plan_path.with_suffix(".html")
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(page)
    tmp.replace(out)
    print(f"{now:%H:%M} {out.name}", flush=True)
    return 0, period.end


def main(argv: list[str] | None = None, *, sleep: Callable[[float], None] = time.sleep) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=pathlib.Path, help="計画 JSON（YYYY-MM-DD_HHMM.json）")
    parser.add_argument("--out", type=pathlib.Path, help="出力先。既定は計画と同じ場所・同じ名前の .html")
    parser.add_argument(
        "--watch",
        type=int,
        metavar="MINUTES",
        help="指定した分ごとに描画し直し、計画の終わりを過ぎたら最後に1回描画して終わる",
    )
    args = parser.parse_args(argv)
    plan_path = args.plan.resolve()
    code, end = render_once(plan_path, args.out)
    if not args.watch:
        return code
    if args.watch <= 0:
        print("--watch は1以上の分で指定する", file=sys.stderr)
        return 1
    while True:
        # 途中で JSON が壊れても止めない。直されれば次の回で描画できる。
        if end is not None and dt.datetime.now(end.tzinfo) >= end:
            return code
        sleep(args.watch * 60)
        result, new_end = render_once(plan_path, args.out)
        code = result
        end = new_end or end


if __name__ == "__main__":
    sys.exit(main())
