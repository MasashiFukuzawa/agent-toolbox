"""Behavior of the daily-plan page renderer, as seen by the person reading the page."""

from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/toolbox/skills/daily-plan"
_spec = importlib.util.spec_from_file_location("daily_plan_render", SKILL / "scripts/render.py")
render_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(render_mod)

JST = dt.timezone(dt.timedelta(hours=9))


def no_gh(args):
    return None


def plan(**overrides):
    base = {
        "start": "2026-04-14T20:00:00+09:00",
        "end": "2026-04-15T08:00:00+09:00",
        "repo": "example-org/app",
        "lanes": [
            {
                "name": "Lane A",
                "steps": [
                    {"label": "first", "state": "done"},
                    {"label": "second", "state": "doing", "note": "halfway"},
                    {"label": "third"},
                ],
            }
        ],
    }
    base.update(overrides)
    return base


def page(day, goals=None, *, now=dt.datetime(2026, 4, 15, 1, 30, tzinfo=JST), gh=no_gh, base=None):
    return render_mod.render(day, goals, now=now, gh=gh, base=base or Path("."))


def text_of(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html)


class TestStateJudgement:
    def judge(self, step, gh=no_gh, repo="example-org/app", base=Path(".")):
        return render_mod.judge(step, repo=repo, base=base, gh=gh)

    def test_unreachable_github_falls_back_to_the_manual_state(self):
        assert self.judge({"check": "pr-merged:1", "state": "doing"})[0] == "doing"

    def test_without_a_manual_state_the_step_is_not_started(self):
        assert self.judge({"check": "pr-ci:1"})[0] == "todo"

    def test_a_crashing_gh_does_not_stop_rendering(self):
        def broken(args):
            return "not json"

        assert self.judge({"check": "run-success:9", "state": "waiting"})[0] == "waiting"
        assert self.judge({"check": "run-success:9"}, gh=broken)[0] == "todo"

    def test_missing_repo_skips_github_checks(self):
        called = []
        state, note = self.judge({"check": "pr-merged:1", "state": "doing"}, gh=called.append, repo=None)
        assert (state, called) == ("doing", [])
        assert "repo" in note

    def test_merged_pr_is_done_and_closed_unmerged_is_blocked(self):
        assert self.judge({"check": "pr-merged:5"}, gh=lambda a: '{"state":"MERGED"}')[0] == "done"
        assert self.judge({"check": "pr-merged:5"}, gh=lambda a: '{"state":"CLOSED"}')[0] == "blocked"

    def test_open_pr_with_wait_label_shows_the_wait_reason(self):
        step = {"check": "pr-merged:5", "waitLabel": "review pending"}
        assert self.judge(step, gh=lambda a: '{"state":"OPEN"}') == ("waiting", "review pending")

    def test_carried_over_reason_stays_visible_while_waiting(self, tmp_path):
        step = {"check": "file-nonempty:watch.txt", "waitLabel": "release pending", "note": "carried over"}
        assert self.judge(step, base=tmp_path) == ("waiting", "release pending・carried over")

    def test_ci_failure_blocks_and_pending_is_in_progress(self):
        assert self.judge({"check": "pr-ci:5"}, gh=lambda a: '[{"bucket":"pass"},{"bucket":"fail"}]')[0] == "blocked"
        assert self.judge({"check": "pr-ci:5"}, gh=lambda a: '[{"bucket":"pending"}]')[0] == "doing"
        assert self.judge({"check": "pr-ci:5"}, gh=lambda a: '[{"bucket":"pass"}]')[0] == "done"

    def test_watched_file_turns_done_once_it_has_content(self, tmp_path):
        step = {"check": "file-nonempty:watch.txt", "waitLabel": "release pending"}
        assert self.judge(step, base=tmp_path) == ("waiting", "release pending")
        (tmp_path / "watch.txt").write_text("v1.2.3 found\nv1.2.4 found\n")
        assert self.judge(step, base=tmp_path) == ("done", "v1.2.4 found")


class TestProgress:
    def test_counts_and_next_step_follow_the_step_states(self):
        out = text_of(page(plan()))
        assert "作業の進捗：3手順のうち1が完了" in out
        assert "33%" in out
        assert "完了 1・進行中 1・待ち 0・止まっている 0・未着手 1" in out
        assert "second（進行中・halfway）" in out

    def test_lane_with_everything_done_says_so(self):
        day = plan(lanes=[{"name": "Done lane", "steps": [{"label": "only", "state": "done"}]}])
        assert "すべて完了" in text_of(page(day))

    def test_every_state_is_shown_as_text_not_only_color(self):
        steps = [{"label": s, "state": s} for s in render_mod.STATE_ORDER]
        html = page(plan(lanes=[{"name": "All", "steps": steps}]))
        for state, label in render_mod.STATE_LABELS.items():
            assert f'<span class="chip s-{state}">{label}</span>' in html


class TestGoals:
    GOALS = {
        "title": "April",
        "stages": ["design", "build", "staging", "prod"],
        "goals": [
            {"id": "search", "name": "Search", "reached": "build", "target": "prod"},
            {"id": "audit", "name": "Audit", "reached": "prod", "target": "prod"},
        ],
    }

    def test_shows_the_gap_and_how_many_goals_are_met(self):
        out = text_of(page(plan(), self.GOALS))
        assert "April：期限の目標に届いたのは 1/2" in out
        assert "あと2段階" in out and "目標に到達" in out

    def test_stage_advanced_by_this_plan_links_to_the_lane(self):
        day = plan()
        day["lanes"][0]["advances"] = {"goal": "search", "stage": "staging"}
        html = page(day, self.GOALS)
        assert '<a class="today" href="#lane-1">▲今回：Lane A</a>' in html
        assert 'id="lane-1"' in html

    def test_unknown_goal_or_stage_is_rejected(self):
        day = plan()
        day["lanes"][0]["advances"] = {"goal": "search", "stage": "launch"}
        with pytest.raises(render_mod.PlanError):
            page(day, self.GOALS)


class TestTimeline:
    def bar_style(self, html, cls):
        return re.findall(rf'class="tl-bar {cls}" style="left:([\d.]+)%;width:([\d.]+)%"', html)

    def test_overnight_plan_is_one_continuous_axis(self):
        day = plan()
        day["lanes"][0]["plan"] = {"start": "23:00", "end": "02:00"}
        html = page(day)
        # 20:00–08:00 is 720 minutes; 23:00 is 180 in, 02:00 is 360 in.
        assert self.bar_style(html, "tl-plan") == [("25.000", "25.000")]
        assert "4/15 0:00" in html
        assert "4/14 20:00〜4/15 08:00" in text_of(html)

    def test_open_actual_runs_until_now(self):
        day = plan()
        day["lanes"][0]["actual"] = {"start": "23:00"}
        # now is 01:30 → 330 minutes in.
        assert self.bar_style(page(day), "tl-actual") == [("25.000", "20.833")]

    def test_paused_and_resumed_work_shows_each_actual_interval(self):
        day = plan()
        day["lanes"][0]["actual"] = [{"start": "21:00", "end": "23:00"}, {"start": "01:00"}]
        html = page(day)
        # 21:00–23:00 is 60–180 in; 01:00 until now (01:30) is 300–330 in.
        assert self.bar_style(html, "tl-actual") == [("8.333", "16.667"), ("41.667", "4.167")]
        assert "実績 21:00–23:00、01:00–" in text_of(html)

    def test_bars_outside_the_period_are_clipped(self):
        day = plan()
        day["lanes"][0]["plan"] = {"start": "06:00", "end": "10:00"}
        left, width = self.bar_style(page(day), "tl-plan")[0]
        assert float(left) + float(width) == pytest.approx(100.0)

    def test_constraints_are_drawn_and_listed(self):
        day = plan(constraints=[{"start": "06:00", "end": "09:00", "label": "no downtime"}])
        html = page(day)
        assert 'class="tl-constraint"' in html
        assert "no downtime 06:00–09:00" in text_of(html)

    def test_now_line_only_inside_the_period(self):
        day = plan()
        day["lanes"][0]["plan"] = {"start": "21:00", "end": "23:00"}
        assert "現在 01:30" in page(day)
        later = dt.datetime(2026, 4, 15, 9, 0, tzinfo=JST)
        html = page(day, now=later)
        assert "タイムライン" in html
        assert "tl-now" not in html.split("<style>")[1].split("</style>")[1]
        assert "を過ぎた" in text_of(html)

    def test_plan_longer_than_a_day_is_rejected(self):
        with pytest.raises(render_mod.PlanError):
            page(plan(end="2026-04-15T21:00:00+09:00"))


class TestOwnerBoardReferences:
    def test_question_number_links_to_the_board_without_its_content(self):
        day = plan(ownerBoard="../board/owner-board.html")
        day["lanes"][0]["steps"][2].update(state="waiting", ref="Q14")
        html = page(day)
        assert '<a href="../board/owner-board.html#Q14">Q14</a>' in html

    def test_malformed_reference_is_rejected(self):
        day = plan(ownerBoard="board.html")
        day["lanes"][0]["steps"][0]["ref"] = 'Q1"><script>'
        with pytest.raises(render_mod.PlanError):
            page(day)


class TestSafety:
    def test_untrusted_text_is_escaped_and_page_is_self_contained(self):
        evil = '<img src=x onerror="alert(1)">'
        day = plan(title=evil, source={"label": evil, "href": "javascript:alert(1)"})
        day["lanes"][0]["name"] = evil
        day["lanes"][0]["steps"][0]["note"] = evil
        html = page(day)
        assert "<img" not in html
        assert "javascript:" not in html
        # 自動の読み込み直しのための固定の script だけを許す。
        assert re.findall(r"<script[^>]*>.*?</script>", html, re.S) == [render_mod.reload_script(300)]
        assert not re.search(r"<script[^>]*\bsrc=", html)
        assert not re.search(r'(src|href)="(https?:)?//', html)


class TestReload:
    def test_page_never_reloads_itself_with_meta_refresh(self):
        # meta refresh は読んでいる途中でもページを差し替えるので使わない。
        assert 'http-equiv="refresh"' not in page(plan())

    def test_reload_can_be_turned_off(self):
        assert "<script" not in page(plan(refreshSeconds=0))


class TestCommandLine:
    def write(self, tmp_path, day):
        path = tmp_path / "2026-04-14_2000.json"
        path.write_text(json.dumps(day))
        return path

    def test_writes_html_next_to_the_plan(self, tmp_path):
        path = self.write(tmp_path, plan(repo=None))
        assert render_mod.main([str(path)]) == 0
        assert "<!doctype html>" in (tmp_path / "2026-04-14_2000.html").read_text()

    def test_invalid_plan_keeps_the_previous_page(self, tmp_path, capsys):
        path = self.write(tmp_path, plan(repo=None))
        render_mod.main([str(path)])
        before = (tmp_path / "2026-04-14_2000.html").read_text()
        broken = copy.deepcopy(plan())
        broken["lanes"][0]["steps"][0]["state"] = "finished"
        path.write_text(json.dumps(broken))
        assert render_mod.main([str(path)]) == 1
        assert (tmp_path / "2026-04-14_2000.html").read_text() == before
        assert "finished" in capsys.readouterr().err

    def test_watch_stops_by_itself_after_the_plan_ends(self, tmp_path):
        now = dt.datetime.now(JST)
        day = plan(
            repo=None, start=(now - dt.timedelta(hours=1)).isoformat(), end=(now + dt.timedelta(minutes=5)).isoformat()
        )
        path = self.write(tmp_path, day)
        sleeps = []

        def fake_sleep(seconds):
            sleeps.append(seconds)
            # Jump the plan into the past so the next check sees it as finished.
            ended = copy.deepcopy(day)
            ended["end"] = (dt.datetime.now(JST) - dt.timedelta(minutes=1)).isoformat()
            path.write_text(json.dumps(ended))

        assert render_mod.main([str(path), "--watch", "10"], sleep=fake_sleep) == 0
        assert sleeps == [600]


def test_bundled_example_renders():
    example = SKILL / "assets/example"
    day = json.loads((example / "2026-04-14_2000.json").read_text())
    goals = json.loads((example / day["goals"]).read_text())
    html = page(day, goals, base=example)
    assert "4/14 夜〜4/15 朝の作業" in html


def test_timeline_is_omitted_when_nothing_is_scheduled():
    assert "タイムライン" not in page(plan())


def test_progress_comes_first_and_period_goals_come_last():
    goals = {"stages": ["design", "build"], "goals": [{"id": "g", "name": "G", "reached": None, "target": "build"}]}
    day = plan()
    day["lanes"][0]["plan"] = {"start": "21:00", "end": "23:00"}
    headings = re.findall(r"<h2>([^<：（]+)", page(day, goals))
    assert headings == ["作業の進捗", "タイムライン", "作業ごとの手順", "期間の目標"]
