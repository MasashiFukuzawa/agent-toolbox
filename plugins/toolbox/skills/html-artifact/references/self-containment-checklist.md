# Self-Containment Checklist

A self-contained HTML file opens in any browser, works offline, and is still readable six months later. Use this checklist before delivering any html-artifact output.

## Tier 1 — Always OK (no comment required)

These never break self-containment:

- [x] Pure HTML5 elements
- [x] Inline `<style>` block in `<head>`
- [x] Inline `<script>` block (at end of `<body>` or in `<head>` with `defer`)
- [x] Inline SVG (`<svg>...</svg>` directly in HTML)
- [x] `data:image/png;base64,...` or `data:image/svg+xml;base64,...` for images
- [x] CSS Custom Properties (variables)
- [x] CSS animations and transitions
- [x] System font stacks: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- [x] `prefers-reduced-motion` media query
- [x] `<details>/<summary>` for progressive disclosure
- [x] `navigator.clipboard.writeText()` (Tier 1 because it's a browser API, not a network request)

## Tier 2 — Allowed only when the task clearly requires it

If you use any of these, add this comment at the very top of the `<html>` (before `<!doctype>`... wait, after `<!doctype html>`, as the first child of `<head>`):

```html
<!-- requires: CDN: [list what you use] — will not render correctly offline -->
```

| Resource | CDN URL | When to use |
|---|---|---|
| Tailwind CSS | `https://cdn.tailwindcss.com` | Dense layout-heavy reports with many utility classes |
| Chart.js | `https://cdn.jsdelivr.net/npm/chart.js` | Time-series or multi-dataset charts where SVG would be 200+ lines |
| mermaid.js | `https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js` | When the user provides or requests Mermaid diagram syntax |
| Google Fonts | `https://fonts.googleapis.com/css2?family=...` | When a specific named font is part of the design intent |
| highlight.js | `https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.x/highlight.min.js` | Code blocks with syntax highlighting (>5 languages or complex grammar) |

**Tier 2 rules:**
1. Pick at most one charting library and one CSS utility framework — never both Chart.js and D3, never both Tailwind and Bootstrap
2. Always include a system-font fallback in `font-family` even when loading a Google Font
3. When using Chart.js, also include the canvas accessibility pattern: `<canvas role="img" aria-label="..."><p>Data: ...</p></canvas>`

## Tier 3 — Prohibited

These break the artifact's self-containment promise:

| Prohibited pattern | Why | Alternative |
|---|---|---|
| `fetch('/api/...')` | Requires a running server | Embed the data inline as a JS variable |
| `import ... from 'https://...'` | ES module with network dep; may fail on some CSP | Use script tag CDN or inline the library |
| `<iframe src="https://external.com">` | External content, not self-contained | Describe the content as text/table instead |
| Any API key, token, or credential | Readable in source; security risk | Never include — describe the call pattern instead |
| `<link rel="stylesheet" href="external.css">` | External file, breaks offline | Inline the relevant CSS |
| `<script src="./local-script.js">` | Separate file, breaks single-file sharing | Inline the script |

## CSP-safe patterns

If the artifact will be served with a Content Security Policy (e.g., embedded in a dashboard):

- Avoid `style="..."` inline attributes for complex styles (use `<style>` block instead, which a `style-src 'unsafe-inline'` or nonce allows)
- Avoid `onclick="..."` inline event handlers — use `addEventListener` in the `<script>` block
- Avoid `javascript:` URIs

## File size guide

| Size | Assessment | Action |
|---|---|---|
| < 15 KB | Excellent | Deliver as-is |
| 15–30 KB | Good | Acceptable, check for unnecessary repetition |
| 30–60 KB | Large | Review: are templates being duplicated? Can data be represented as a table? |
| > 60 KB | Too large | Split into 2–3 linked files, or cut scope |

**Common bloat causes:**
- Base64 images (prefer omitting images if not essential)
- Duplicated CSS across many sections (extract to one `<style>` block at the top)
- Verbose inline SVG that could use `<use>` with `<symbol>` definitions
- Pasting entire file contents instead of relevant diff snippets

## Quick checklist before delivery

- [ ] `<!doctype html>` present
- [ ] `<meta charset="utf-8">` present
- [ ] `<meta name="viewport" content="width=device-width, initial-scale=1">` present
- [ ] `<title>` is descriptive (not "Document" or empty)
- [ ] All styles in `<style>` block (no external `.css` file references)
- [ ] All scripts in `<script>` block (no external `.js` file references)
- [ ] Light theme only — no `@media (prefers-color-scheme: dark)` overrides; assumes a white/light background
- [ ] Overview is scannable on its own; supporting detail is pushed into collapsed `<details>` rather than cut
- [ ] SVG has `role="img"` and `aria-label` if it conveys information
- [ ] No API keys, tokens, or credentials in source
- [ ] If Tier 2 CDN used: `<!-- requires: CDN: ... -->` comment added
- [ ] File opens correctly with `open ./filename.html` from the terminal
