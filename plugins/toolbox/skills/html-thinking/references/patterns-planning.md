# Planning & Exploration Patterns

## Pattern 1: Multi-column approach comparison

Use when the user wants 2–5 approaches evaluated in parallel. Each column gets identical rows so the reader can scan horizontally.

**Structure:**
```
[Header with decision context]
[Criteria pinned bar — e.g., Cost / Speed / Risk]
[Column grid: Option A | Option B | Option C]
  Each column:
    - h2: Option name + one-line summary
    - Pros list
    - Cons list
    - Code sketch or architecture note
    - Verdict badge (Recommended / Viable / Avoid)
[Decision log section at bottom]
[Send-as-prompt buttons]
```

**CSS skeleton:**
```css
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.25rem; }
.option { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; }
.option.recommended { border-color: #22c55e; background: #f0fdf4; }
.badge { display: inline-block; font-size: .75rem; font-weight: 700; border-radius: 4px; padding: .2em .5em; }
.badge-green { background: #dcfce7; color: #166534; }
.badge-red   { background: #fee2e2; color: #991b1b; }
```

**Decision log pattern:** A collapsible `<details>` at the bottom lets the reader record which option they chose and why, then copy it back as a prompt:
```html
<details>
  <summary>Decision log</summary>
  <textarea id="log" placeholder="We chose Option B because..."></textarea>
  <button onclick="navigator.clipboard.writeText(document.getElementById('log').value)">Copy as prompt</button>
</details>
```

---

## Pattern 2: Implementation plan with phases

Use when the user wants a phased plan with tasks, owners, and dependencies.

**Structure:**
```
[Phase timeline — horizontal CSS steps or SVG]
[Per-phase accordion sections]
  Each phase:
    - Goal statement
    - Task list with checkboxes (static, for scanning)
    - Key code snippets (collapsible)
    - Dependencies / blockers
    - Exit criteria
[Risk table]
[Open questions]
```

**Phase timeline CSS (horizontal steps):**
```css
.phases { display: flex; gap: 0; }
.phase { flex: 1; padding: .5rem 1rem; background: #e2e8f0; position: relative; }
.phase::after {
  content: ''; position: absolute; right: -12px; top: 0; width: 0; height: 100%;
  border: 20px solid transparent; border-left-color: #e2e8f0; z-index: 1;
}
.phase.active { background: #3b82f6; color: #fff; }
.phase.active::after { border-left-color: #3b82f6; }
```

**Task list with status:**
```html
<ul class="tasks">
  <li class="done">✓ Set up CI pipeline</li>
  <li class="in-progress">◐ Implement auth middleware</li>
  <li class="todo">○ Write migration scripts</li>
</ul>
```

---

## Pattern 3: Decision matrix

Use when the user wants to score N options against M criteria.

**Structure:**
- `<table>` with sticky first column (option names)
- Each cell: score 1–5 rendered as colored dots or a number
- Last column: weighted total
- Below the table: rationale for weights

**Sticky column trick:**
```css
table { border-collapse: collapse; }
td:first-child, th:first-child { position: sticky; left: 0; background: #fff; z-index: 1; }
```

**Score cell color coding:**
```css
.score-5 { background: #22c55e; color: #fff; }
.score-4 { background: #86efac; }
.score-3 { background: #fef08a; }
.score-2 { background: #fdba74; }
.score-1 { background: #f87171; color: #fff; }
```

---

## Dos and don'ts for planning HTML

- **Do** put the recommendation badge prominently — readers scan, not read
- **Do** include a "send-as-prompt" button beside the recommended option
- **Do** use a light background color per option to make columns scannable
- **Don't** put more than 5 options in a column grid — use a table instead
- **Don't** omit the decision log section — it closes the Claude ↔ human loop
- **Don't** hide the conclusion at the bottom; put a verdict at the top, details below
