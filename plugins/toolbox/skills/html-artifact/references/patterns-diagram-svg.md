# SVG Diagram Patterns

All diagrams use inline SVG — never `<img src="external.svg">`. Set a `viewBox` with a logical coordinate system (not pixels), then let CSS scale it with `width: 100%; max-width: Xpx`.

## SVG boilerplate

```html
<svg viewBox="0 0 600 300" style="width:100%;max-width:700px;display:block;margin:0 auto"
     role="img" aria-label="[Description of the diagram]">
  <defs>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#52616b"/>
    </marker>
    <style>
      text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
      .label { font-size: 12px; fill: #171410; }
      .node { fill: #eee7da; stroke: #6d655b; stroke-width: 1.5; }
      .node-highlight { fill: #dcece6; stroke: #16715e; stroke-width: 2; }
      .edge { stroke: #52616b; stroke-width: 1.5; fill: none; marker-end: url(#arrow); }
      .edge-label { font-size: 10px; fill: #52616b; }
    </style>
  </defs>
  <!-- diagram elements here -->
</svg>
```

---

## Pattern 1: Node-edge graph (services, dependencies, data flow)

Lay out nodes manually — avoid auto-layout libraries for small diagrams. Use a grid coordinate system (multiples of 80 or 100).

```html
<!-- Node -->
<rect x="20" y="120" width="100" height="44" rx="6" class="node"/>
<text x="70" y="147" text-anchor="middle" class="label">Service A</text>

<!-- Edge from right of node A to left of node B -->
<line x1="120" y1="142" x2="200" y2="142" class="edge"/>

<!-- Edge with a label -->
<g>
  <path d="M120,142 C160,142 160,220 200,220" class="edge"/>
  <text x="155" y="185" class="edge-label">async</text>
</g>
```

**Layout tips:**
- 3–7 nodes: horizontal left-to-right layout, nodes at x = 20, 180, 340, 500
- 8–15 nodes: layer layout (left column = inputs, middle = processors, right = outputs)
- More than 15 nodes: use Mermaid via CDN (Tier 2) rather than hand-drawing

---

## Pattern 2: Flowchart (decision tree, process flow)

```html
<!-- Start/End: rounded rect -->
<rect x="250" y="10" width="100" height="36" rx="18" class="node-highlight"/>
<text x="300" y="33" text-anchor="middle" class="label">Start</text>

<!-- Decision: diamond -->
<polygon points="300,80 360,120 300,160 240,120" class="node"/>
<text x="300" y="125" text-anchor="middle" class="label">Valid?</text>

<!-- Yes / No branch labels -->
<text x="365" y="115" class="edge-label">Yes</text>
<text x="305" y="170" class="edge-label">No</text>
```

**Diamond helper:** `points="cx,cy-r cx+r,cy cx,cy+r cx-r,cy"` where r is half-height/width.

---

## Pattern 3: Sequence diagram (simplified)

Use horizontal swim lanes (one per actor), vertical time axis.

```html
<svg viewBox="0 0 500 300" style="width:100%;max-width:600px">
  <!-- Actor columns: Client x=80, Server x=260, DB x=440 -->
  <!-- Lifeline -->
  <line x1="80" y1="40" x2="80" y2="280" stroke="#d2c8b4" stroke-dasharray="4"/>
  <line x1="260" y1="40" x2="260" y2="280" stroke="#d2c8b4" stroke-dasharray="4"/>
  <!-- Message arrow -->
  <line x1="80" y1="80" x2="260" y2="80" class="edge"/>
  <text x="170" y="74" text-anchor="middle" class="edge-label">POST /login</text>
  <!-- Return arrow (dashed) -->
  <line x1="260" y1="120" x2="80" y2="120" stroke="#52616b" stroke-width="1.5" stroke-dasharray="5" marker-end="url(#arrow)"/>
  <text x="170" y="114" text-anchor="middle" class="edge-label">200 OK + token</text>
</svg>
```

---

## Pattern 4: Timeline / Gantt strip

Use a `<rect>` per task on a shared time axis. Annotate milestones with `<circle>`.

```html
<!-- Time axis: Jan=0 ... Dec=550, each month=~46px wide -->
<!-- Task bar: y-position separates tasks, height=24 -->
<rect x="0"   y="20" width="140" height="24" rx="4" fill="#85b8aa" opacity=".8"/>
<text x="70"  y="37" text-anchor="middle" class="label" font-size="11">Phase 1</text>
<rect x="130" y="20" width="180" height="24" rx="4" fill="#d7b36a" opacity=".8"/>
<!-- Milestone -->
<circle cx="310" cy="32" r="7" fill="#a33d32"/>
<text x="310" y="58" text-anchor="middle" class="edge-label">v1.0 launch</text>
```

---

## Dos and don'ts for SVG diagrams

- **Do** define `<marker id="arrow">` in `<defs>` and reuse with `marker-end="url(#arrow)"`
- **Do** use `text-anchor="middle"` + explicit x/y for centered labels
- **Do** set `role="img" aria-label="..."` for accessibility
- **Don't** overlap text with edges — offset edge labels with a small y adjustment
- **Don't** go below font-size 10px — illegible at reduced display sizes
- **Don't** use raster images (PNG/JPG) inside SVG — they break self-containment (unless base64)
- **Don't** reach for D3 or mermaid unless the diagram has 15+ nodes or the user specified Mermaid
