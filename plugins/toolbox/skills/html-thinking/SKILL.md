---
name: html-thinking
description: >-
  計画、比較、図解、レビューを自己完結 HTML の一枚物として可視化する。表や SVG、並列レイアウトが理解を助ける時に使う。会話内の小さな図には ascii-diagram を使う。「HTML一枚物で」「比較を視覚化して」を正のトリガーとし、production UIや対話内ですぐ読む小さな図には使わない。
---
# 思考・伝達媒体としてのHTML

Markdownでは平坦になる並列案、階層、timeline、依存graphを、自己完結HTMLの空間構造で読みやすくする。本Skillはproduction UIを作るものではなく、意思決定や説明のための一枚物を作る。

## 使う時・使わない時

**Use this skill when:**
- Comparing multiple approaches, architectures, or designs side by side
- Writing an implementation plan with phases, dependencies, or code sketches
- Creating a research or status report that mixes prose, tables, and diagrams
- Producing a code-review walkthrough with annotated diffs
- Explaining a concept that needs a diagram (flowchart, data model, system topology)
- The honest answer would require a Markdown file over ~100 lines

**Do not use this skill when:**
- A few bullet points or a short table in a chat reply would suffice
- production UI、design system、出荷するcomponentが必要 → 本Skillの対象外。利用可能なら専用のfrontend design Skillを使う
- The user explicitly wants continuous-parameter tuning (live sliders, real-time preview) → that is a prototype, outside this skill's scope
- The output needs to be edited by a non-technical user in something other than a browser

## key question契約（HTMLを書く前に必須）

State in ONE line: **who** will read this page and **what single question** it must answer or what decision it must enable (e.g. "ユーザーが2つの設計案からどちらを採用するか決める"). If you cannot fill this line from context, ask the user exactly one clarifying question before generating.

- The **first view** (validate at 1440×900 desktop and 375×812 mobile without scrolling) is composed ONLY of content that answers the key question — verdict, comparison, map. On mobile, the question, verdict, and at least one decisive piece of evidence must appear before the fold. Everything else goes below or into `<details>`.
- Write the key question as an HTML comment at the top of the file (`<!-- key question: ... -->`) so later edits stay anchored to it.
- Self-check after writing: open the page cold and ask "does the first screen answer the key question in 5 seconds?" If the reader must scroll or expand to get the point, restructure.

## 基本原則

### Default visual language: Field Review

Every artifact uses the Field Review visual system unless the user explicitly requests another style. Treat it as a stable editorial grammar, not a rigid template: warm paper, dark ink, forest-green primary accent, serif display type, plain sans body type, mono metadata, one decisive recommendation, and a small number of strong evidence surfaces.

Before writing CSS, read `references/visual-system.md`. Start from the nearest file in `assets/templates/`; do not invent an unrelated palette or generic dashboard aesthetic. Content determines whether a thesis band, texture, cards, or motion are present—the tokens and hierarchy remain consistent.

1. **Information density over word count.** A well-structured 80-line HTML page carries more than a 300-line Markdown doc. Prefer tables, side-by-side columns, and SVG over prose repetition.

2. **Self-contained.** One `.html` file, openable in any browser with no network required (unless a 2nd-tier CDN is explicitly needed — see Self-containment rules). The reader should be able to email it, open it offline, and have it still work in six months. Web fonts are enhancement only; Field Review must remain intentional with its serif/sans/mono fallback stacks.

3. **Spatial structure is the point.** Use the layout itself to communicate: parallel columns convey parity; hierarchy of font sizes conveys importance; a timeline SVG conveys sequence. Do not default to a single linear column unless the content is genuinely linear.

4. **Mobile-readable.** Include `<meta name="viewport" content="width=device-width, initial-scale=1">`. Use `max-width` and readable font sizes. Test the mental model at 375px width.

5. **Optimized for being read, not maintained.** This is a disposable artifact. Favor clarity over abstraction. Inline everything. A little duplication in CSS is fine.

6. **Visualize aggressively — prose is the fallback, not the default.** Hard rules, not suggestions:
   - **3+ parallel items → table** (never a bulleted list of similar-shaped items)
   - **Any relationship, flow, sequence, or structure → diagram (SVG)** — boxes and arrows, timeline, layered map
   - **Process/phases → timeline or step visual**, states → color-coded badges
   - **Prose is limited to what visuals cannot carry**: rationale, nuance, caveats — attached to the visual it explains, 1-3 sentences at a time
   - **First-view text budget: ~200 Japanese characters (or ~40 English words) of running prose.** If the first view has more, convert to visuals or demote into `<details>`. Ask: "Could a reader grasp this in 5 seconds?" — if not, restructure. (Cognitive basis: references/cognitive-load.md)

7. **Progressive disclosure is the core advantage of HTML — use it by default.** HTML's defining strength over Markdown is that detail can be *present but hidden*: collapsed in an accordion, revealed only on demand. So the goal is never "concise *or* complete" — it is **both at once**. Design every artifact as two layers:
   - **Surface layer (always visible):** a concise, scannable overview — the headlines, the verdict, the shape of the thing. A reader who only sees this layer should still understand the gist.
   - **Detail layer (collapsed by default):** the full supporting evidence, edge cases, raw data, long code, derivations, alternatives considered. **Do not cut detail to stay concise — push it into `<details>` instead.** Brevity comes from collapsing, not from deleting.

   Wrap each detail block in `<details>` (collapsed, i.e. no `open` attribute) with a `<summary>` that names what's inside and ideally hints at its size ("Full migration steps (14)", "Why we rejected Option B"). The reader expands only what they need. This is not an optional flourish — it is the default information architecture for this skill.

   **Drill-down template** — inside a `<details>`, structure substantive topics in this order so every expansion reads the same way:
   1. **背景・課題・目的** (why this exists, 1-3 lines)
   2. **As-Is → To-Be** (current vs target state — prefer a 2-column layout or before/after diagram)
   3. **詳細・根拠** (evidence, data, code, edge cases)

   Not every `<details>` needs all three (raw-data blocks don't), but any "explain this decision/change" block does.

## 出力contract

Every HTML file produced by this skill must satisfy:

```
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>[Descriptive title — visible in browser tab and when shared]</title>
  <style>
    /* All styles inline here — Field Review light theme */
  </style>
</head>
<body>
  ...
  <script>/* All scripts inline here, if needed */</script>
</body>
</html>
```

- `<title>` is mandatory — it is the first thing a recipient sees when the file is shared
- Inline `<style>` and `<script>` — no external `.css` or `.js` files
- **Field Review light theme only** — use the shared paper/ink/green tokens; do not add `@media (prefers-color-scheme: dark)` overrides
- Target file size under 30 KB; if larger, split into multiple files or cut scope
- If any 2nd-tier external resource is used, add a comment at the very top: `<!-- requires: CDN: tailwind, chart.js — will not render offline -->`

## 用途別pattern

For each pattern, a minimal structural skeleton is shown. Read `references/` for fuller recipes.

### 1. Exploration & planning — parallel comparison
Use multi-column CSS grid. Each column = one approach. Put decision criteria as a pinned top row.
```html
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem">
  <div class="option"><h2>Option A</h2>...</div>
  <div class="option"><h2>Option B</h2>...</div>
  <div class="option"><h2>Option C</h2>...</div>
</div>
```
Reference: `references/patterns-planning.md`

### 2. Implementation plan
Combine a phase timeline (SVG or CSS steps) with a dependency graph and key code snippets per phase. Include a decision log section at the bottom.
Reference: `references/patterns-planning.md`

### 3. Code review walkthrough
Two-panel layout: file tree / diff on the left, annotation on the right. Color-code severity (critical / warning / info). Include a summary card at the top.
```html
<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
  <pre class="diff">...</pre>
  <div class="annotations">...</div>
</div>
```
Reference: `references/patterns-code-review.md`

### 4. Diagrams & explanations
Prefer inline SVG. Draw nodes as `<circle>` or `<rect>`, edges as `<line>` or `<path>`. For complex graphs, use a `<svg viewBox>` with a coordinate system. Annotate with `<text>` elements, not overlaid HTML.
```html
<svg viewBox="0 0 400 200" style="width:100%;max-width:600px">
  <rect x="10" y="80" width="80" height="40" rx="6" fill="#4f6"/>
  <text x="50" y="105" text-anchor="middle" font-size="13">Service A</text>
  <line x1="90" y1="100" x2="150" y2="100" stroke="#888" marker-end="url(#arrow)"/>
</svg>
```
Reference: `references/patterns-diagram-svg.md`

### 5. Status reports
KPI cards across the top, timeline or changelog below, risk table at the bottom. Use `<details>` for incident timelines. Avoid charts unless the data trend is the message — a table is often clearer.
Reference: `references/patterns-report.md`

### 6. Research summaries
Tabbed sections (pure CSS radio-button trick or minimal JS), collapsible references with `<details>`, a comparison table across sources. Each tab = one source or one angle.

### 7. Slides
`<section>` per slide, `scroll-snap-type: y mandatory` on the container, `scroll-snap-align: start` on each section. ~20 lines of JS for prev/next keyboard navigation.

### 8. Comparison tables
Dense HTML `<table>` with sticky first column, color-coded cells (green/yellow/red), a filter row using checkbox toggles. Aim for 8+ rows before switching from a prose list.

### 9. Custom editing UI (not a primary trigger)
Drag-and-drop card sorters, form editors for config — powerful but treat as a separate scope from thinking artifacts. Only build if the user explicitly asks for an interactive editor, not as a default.

## 自己完結rules

**Tier 1 — always OK:** Pure HTML/CSS/JS. Inline SVG. System font stacks. `data:` URIs for small images.

**Tier 2 — allowed only when the task clearly requires it** (add `<!-- requires: ... -->` comment at top):
- Tailwind CSS CDN (`https://cdn.tailwindcss.com`) — for dense layout-heavy reports
- Chart.js CDN — when trend over time is the message and SVG would be 200+ lines
- mermaid.js CDN — when the diagram is user-specified as Mermaid syntax
- Google Fonts — pair with system-font fallback in `font-family`

**Tier 3 — prohibited:**
- Fetch to a custom backend
- External ES module imports (`import ... from 'https://...'`)
- `<iframe>` embedding external sites
- Any API key or auth token in the HTML source

**Asset rules:**
- SVG: inline only, never `<img src="external.svg">`
- Images: `data:image/...;base64,...` or omit entirely
- Fonts: complete local/system fallback stacks are mandatory; named web fonts may precede them only as an optional enhancement

Full checklist: `references/self-containment-checklist.md`

## interaction pattern（任意）

Add interactivity only when it solves one of these problems. If none apply, use static HTML.

**Problem → Pattern:**
- Reader needs to send a decision back to Claude → **send-as-prompt button**
- Artifact has more dimensions than fit on one screen → **toggle filters**
- Artifact mixes overview and detail → **`<details>/<summary>`**

If you find yourself adding continuous sliders, live previews, or form submissions, stop — that artifact wants to be a prototype, not a thinking document.

### Pattern A: Send-as-prompt button
```html
<button onclick="navigator.clipboard.writeText(
  'I choose Option B because: ' + document.getElementById('reason-b').textContent
).then(() => this.textContent = 'Copied!')">
  Copy "Choose B" as prompt
</button>
```
Put one of these next to each option in a comparison view. The reader clicks, pastes into Claude, and the decision loop closes.

### Pattern B: Toggle filters
```html
<label><input type="checkbox" onchange="toggleClass('row-mobile','hidden',!this.checked)" checked> Mobile</label>
<script>
function toggleClass(cls, hidden, show) {
  document.querySelectorAll('.'+cls).forEach(el => el.style.display = show ? '' : 'none');
}
</script>
```
Use checkboxes or radio buttons (discrete choices), not sliders (continuous values).

### Pattern C: Progressive disclosure
This is the mechanism behind Core Principle 7 — apply it as the default, not as an afterthought. Keep the surface layer concise; collapse everything else.
```html
<details>
  <summary>Incident timeline (12 events)</summary>
  <ol>...</ol>
</details>
```
No JS is required for screen use. For reliable print output, use `beforeprint` to remember and open closed `<details>`, then restore them in `afterprint`; CSS display rules alone are insufficient across browsers. Use `<details>` for long reference sections, raw data, supporting evidence, rejected alternatives, derivations, and any block that adds depth but would clutter the overview. The `<summary>` should name the content and hint at its size so the reader can decide whether to expand. Nest `<details>` when detail has its own sub-detail.

## production frontendとの関係

| Aspect | html-thinking (this skill) | frontend-design |
|---|---|---|
| Purpose | Make ideas legible | Make products beautiful |
| Lifespan | Disposable — deleted within a week | Maintained production code |
| Aesthetic priority | Information density, scanability | Distinctive visual identity |
| Primary audience | Reviewer of an idea or plan | End user of a shipped product |
| Framework | Plain HTML/CSS/JS, no build step | React, Vue, etc. — full stack OK |
| Output | One `.html` file you can email | Files inside a project repo |

**目安:** 読まれて一週間以内に捨てる資料なら本Skillを使う。出荷・保守するUIなら利用可能な専用frontend design Skillを使う。後者は外部Skillであり、本pluginの必須依存ではない。

## Anti-patterns

| What you might write | Why it fails | Better |
|---|---|---|
| Adding `prefers-color-scheme: dark` | Dark theme is out of scope for this skill; adds CSS complexity with no benefit here | Light theme only — white/light background at all times |
| Purple gradient, blue-gray dashboard, Inter everywhere | Generic AI/dashboard aesthetic — reader notices the template before the argument | Use Field Review tokens and three typography roles |
| A card for every paragraph or metric | Flattens hierarchy and makes all evidence look equally important | Use one thesis band and a few bounded evidence surfaces |
| Import D3 + Chart.js + Three.js all at once | Tier-2 CDNs only when truly needed; piling on signals "I just added everything" | Pick one; if it is a diagram, write SVG by hand |
| Slider for every parameter | Sliders = prototype territory, outside this skill's intent | Use toggle filters or static side-by-side |
| 100-line Markdown... in an HTML `<pre>` | Defeats the purpose; this is just Markdown inside HTML | Structure it: tabs, collapsible sections, tables |
| Dump full HTML in chat reply | Walls of code are unreadable; reader cannot open it in a browser | Write to a `.html` file; give the path and an `open` command |
| Markdown would have been 40 lines | Over-engineering; HTML has a cost | Use Markdown for short, linear answers |

## File delivery & naming

**File name convention:** `{purpose}-{slug}.html`
- Examples: `plan-auth-rewrite.html`, `review-pr-1234.html`, `report-q2-incident.html`, `diagram-event-flow.html`

**Default save location:** current working directory (or `.claude/artifacts/` if the project uses that convention).

**After writing:** open the file automatically, then report the path. Run the platform's open command yourself so the reader sees the result immediately — do not just print the command and wait:
```bash
open ./plan-auth-rewrite.html        # macOS
xdg-open ./plan-auth-rewrite.html    # Linux
start ./plan-auth-rewrite.html       # Windows
```
Then tell the user the path:
```
Created and opened: ./plan-auth-rewrite.html
```
If opening fails (e.g. headless environment), fall back to printing the `open` command so the user can run it.

Do not paste the full HTML into the chat response. Give the path instead.

## References

Extended pattern recipes and templates — read these when the task calls for a specific category:

- `references/patterns-planning.md` — parallel comparison layouts, dependency graphs, decision matrices
- `references/patterns-diagram-svg.md` — SVG nodes/edges, flowcharts, sequence diagrams, timelines
- `references/patterns-code-review.md` — diff panels, severity coloring, file trees
- `references/patterns-report.md` — KPI cards, timelines, chapter structure, citation blocks
- `references/self-containment-checklist.md` — full Tier-1/2/3 list, CSP-safe patterns

Starter templates (copy and adapt rather than writing from scratch):

- `assets/templates/plan-skeleton.html`
- `assets/templates/diagram-skeleton.html`
- `assets/templates/review-skeleton.html`
- `assets/templates/report-skeleton.html`
