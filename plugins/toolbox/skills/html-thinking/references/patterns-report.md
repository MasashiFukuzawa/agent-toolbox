# Report & Research Summary Patterns

## Overall structure for a status / incident report

```
[Title + metadata: date, author, severity/status]
[TL;DR — 2–3 bullet executive summary]
[KPI cards row]
[Main body sections — prose + tables]
[Timeline (for incidents)]
[Risk / open issues table]
[Next steps / action items]
```

---

## Pattern 1: KPI cards row

Show 3–6 metrics at a glance. Use color to signal status (green/yellow/red).

```css
.kpi-row { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }
.kpi { flex: 1; min-width: 140px; padding: 1rem; border-radius: 8px; text-align: center; }
.kpi-value { font-size: 2rem; font-weight: 700; line-height: 1; }
.kpi-label { font-size: .8rem; color: #64748b; margin-top: .25rem; }
.kpi-green  { background: #f0fdf4; border: 1px solid #86efac; }
.kpi-yellow { background: #fefce8; border: 1px solid #fde047; }
.kpi-red    { background: #fff1f2; border: 1px solid #fda4af; }
```

```html
<div class="kpi-row">
  <div class="kpi kpi-green">
    <div class="kpi-value">99.7%</div>
    <div class="kpi-label">Uptime (30d)</div>
  </div>
  <div class="kpi kpi-yellow">
    <div class="kpi-value">412ms</div>
    <div class="kpi-label">P95 Latency</div>
  </div>
  <div class="kpi kpi-red">
    <div class="kpi-value">3</div>
    <div class="kpi-label">Open P1 Bugs</div>
  </div>
</div>
```

---

## Pattern 2: Incident timeline

Use `<details>` so the timeline is collapsed by default (executive readers skip it; responders expand it).

```html
<details>
  <summary>Incident timeline (8 events)</summary>
  <ol class="timeline">
    <li>
      <time>14:02 UTC</time>
      <span class="event-type alert">Alert</span>
      Error rate exceeded 5% threshold. PagerDuty fired.
    </li>
    <li>
      <time>14:08 UTC</time>
      <span class="event-type action">Action</span>
      On-call acknowledged. Started investigation.
    </li>
    <li>
      <time>14:31 UTC</time>
      <span class="event-type resolved">Resolved</span>
      Rolled back deployment v2.3.1 → v2.2.9. Error rate returned to baseline.
    </li>
  </ol>
</details>
```

```css
.timeline { list-style: none; padding: 0; border-left: 2px solid #e2e8f0; margin-left: 1rem; }
.timeline li { padding: .5rem 0 .5rem 1rem; position: relative; }
.timeline li::before { content: '●'; position: absolute; left: -1.1rem; color: #94a3b8; }
time { font-weight: 700; font-size: .875rem; margin-right: .5rem; }
.event-type { font-size: .7rem; font-weight: 700; border-radius: 3px; padding: .1em .4em; margin-right: .5rem; text-transform: uppercase; }
.event-type.alert    { background: #fee2e2; color: #991b1b; }
.event-type.action   { background: #eff6ff; color: #1d4ed8; }
.event-type.resolved { background: #f0fdf4; color: #166534; }
```

---

## Pattern 3: Risk / action items table

Use a `<table>` with: Item / Owner / Due / Status / Priority columns. Color-code the Status cell.

```css
.risk-table td.status-open   { color: #dc2626; font-weight: 600; }
.risk-table td.status-done   { color: #16a34a; }
.risk-table td.status-in-prog{ color: #d97706; }
.risk-table td.prio-p1 { font-weight: 700; }
```

---

## Pattern 4: Research summary with tabs

Use the CSS radio-button trick for zero-JS tabs (JS version is fine if SKILL.md interaction patterns apply).

```html
<style>
  .tab-radio { display: none; }
  .tab-label { cursor: pointer; padding: .4rem 1rem; border-bottom: 2px solid transparent; }
  #t1:checked ~ .tabs label[for="t1"],
  #t2:checked ~ .tabs label[for="t2"] { border-color: #3b82f6; font-weight: 600; }
  #t1:checked ~ .content #panel1 { display: block; }
  #t2:checked ~ .content #panel2 { display: block; }
  .tab-panel { display: none; padding: 1rem 0; }
</style>
<input class="tab-radio" type="radio" id="t1" name="tabs" checked>
<input class="tab-radio" type="radio" id="t2" name="tabs">
<div class="tabs">
  <label class="tab-label" for="t1">Source A</label>
  <label class="tab-label" for="t2">Source B</label>
</div>
<div class="content">
  <div class="tab-panel" id="panel1">Content for Source A...</div>
  <div class="tab-panel" id="panel2">Content for Source B...</div>
</div>
```

---

## Pattern 5: Citation / reference block

```html
<blockquote class="citation">
  <p>"The root cause was a missing index on the events table, causing full scans under load."</p>
  <footer>— Post-mortem, 2025-03-14, authored by Site Reliability team</footer>
</blockquote>
```

```css
blockquote.citation {
  border-left: 4px solid #3b82f6;
  margin: 1rem 0;
  padding: .75rem 1rem;
  background: #eff6ff;
  border-radius: 0 6px 6px 0;
}
blockquote.citation footer { font-size: .8rem; color: #64748b; margin-top: .5rem; }
```

---

## Dos and don'ts for reports

- **Do** put the TL;DR at the very top — busy readers decide in 10 seconds whether to read on
- **Do** use KPI cards instead of prose like "uptime was 99.7%"
- **Do** collapse incident timelines — they're reference, not narrative
- **Don't** use a pie chart for a single metric — a KPI card with a number is cleaner
- **Don't** end with "next steps" buried in the last paragraph — use an action table with owners
- **Don't** include raw log dumps — paste only the 3–5 relevant lines with timestamps
