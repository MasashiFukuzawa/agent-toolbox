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

## Write-cost, not file size

There is no file-size target — a long file that is clear is fine, and size is never reported to the user. What is worth avoiding is output that costs tokens to write without adding understanding (see SKILL.md「コスト規律」):

- Repeated `style="..."` attribute lists — define a class once the same decoration appears 3+ times
- Verbose inline SVG that could use `<use>` with `<symbol>` definitions
- Pasting entire file contents instead of the relevant diff snippets
- Base64 images that carry no information the page needs

## Quick checklist before delivery

- [ ] `<!doctype html>` present
- [ ] `<meta charset="utf-8">` present
- [ ] `<meta name="viewport" content="width=device-width, initial-scale=1">` present
- [ ] `<title>` is descriptive (not "Document" or empty)
- [ ] All styles in `<style>` block (no external `.css` file references)
- [ ] All scripts in `<script>` block (no external `.js` file references)
- [ ] Light theme only — no `@media (prefers-color-scheme: dark)` overrides; assumes a white/light background
- [ ] Overview is scannable on its own; supporting detail is pushed into collapsed `<details>` rather than cut
- [ ] Every major section has a `<details>` drill-down; nothing was cut for length
- [ ] Sections about structure / flow / comparison each carry a visual
- [ ] No insider abbreviations or project-local coinages left unrephrased (rewrite beats glossing)
- [ ] Terms beyond a general software engineer's vocabulary are defined at first use; API/HTTP/cache-level terms are left plain
- [ ] 用語集 `<details>` present; first occurrences chipped with `.term` (no bare `<abbr title>`); chips and `<dt>` entries are 1:1
- [ ] No `.term-gloss` tooltip inside an `overflow` container or inside `<svg>`
- [ ] SVG has `role="img"` and `aria-label` if it conveys information
- [ ] No API keys, tokens, or credentials in source
- [ ] If Tier 2 CDN used: `<!-- requires: CDN: ... -->` comment added
- [ ] File opens correctly with `open ./filename.html` from the terminal
