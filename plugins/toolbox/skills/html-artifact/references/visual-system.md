# Field Review visual system

This is an optional visual starting point, not a required palette or layout. Adapt or omit its components to serve the reader. SKILL.md and references/accessibility.md take precedence over these examples.

## Design intent

The page should feel like a carefully edited technical field report: warm, calm, authoritative, and dense without becoming cramped. The reader should notice the conclusion and structure before noticing the decoration.

Avoid generic dashboard styling. Do not use cool gray application backgrounds, blue as the default accent, pill-heavy interfaces, gradients, glass effects, oversized empty hero areas, or a grid of interchangeable white cards.

## Core tokens

```css
:root {
  --paper: #f6f2e9;
  --paper-deep: #eee7da;
  --surface: #fffdf8;
  --ink: #171410;
  --text: #302b25;
  --muted: #6d655b;
  --line: #d2c8b4;
  --line-soft: #e4dccd;
  --green: #16715e;
  --green-dark: #0f4f41;
  --green-bg: #edf6f2;
  --amber: #a96716;
  --amber-bg: #fbf2df;
  --red: #a33d32;
  --red-bg: #fbefec;
  --slate: #52616b;
  --shadow: 0 1px 2px rgba(40,30,12,.05), 0 8px 24px rgba(40,30,12,.06);
  --radius: 14px;
  --content: 1120px;
}
```

- Green means recommendation, progress, or the primary path—not decoration.
- Amber means caution or unresolved work. Red means blocking risk or failure. Slate is neutral context.
- Never rely on color alone: pair it with text, icons, patterns, or labels. Maintain WCAG AA contrast for normal text.

## Typography

Use three roles, not one font everywhere:

1. **Display:** a high-contrast editorial serif for the main title, verdict, and large KPI values. Stack: `Fraunces, 'Hiragino Mincho ProN', 'Yu Mincho', Georgia, 'Times New Roman', serif`.
2. **Body:** a plain humanist sans for prose, tables, and labels. Stack: `'Public Sans', -apple-system, BlinkMacSystemFont, 'Hiragino Sans', 'Yu Gothic Medium', 'Yu Gothic', 'Segoe UI', sans-serif`.
3. **Metadata:** monospace for eyebrow text, section labels, sequence numbers, and compact metadata. Stack: `'IBM Plex Mono', 'SFMono-Regular', Consolas, 'Hiragino Kaku Gothic ProN', monospace`.

For Japanese, keep the role distinction through weight, size, tracking, and surrounding Latin text even when Japanese glyphs use a local fallback. Never apply negative letter-spacing to Japanese headings or letter-spacing to Japanese body copy; scope tight display tracking to English with `html:lang(en)`. Use `line-height: 1.65–1.8` for Japanese prose. Set the correct document `lang`; test Japanese, English, mixed text, numbers, and long unbroken tokens.

**Never put `text-transform: uppercase` on a selector that can contain Japanese.** It leaves Japanese glyphs untouched while shouting the Latin fragments, so a mixed eyebrow renders as 「認証SESSION」. Mono eyebrows and section labels are exactly where this bites. If an all-caps look is wanted, either write the label in caps yourself (Latin-only labels) or scope the rule with `html:lang(en)`.

**`ch` units are Latin-derived** — `max-width: 66ch` wraps Japanese far earlier than intended. For Japanese prose, widen the value (~80ch) or set the measure in `rem`/`em`.

Google Fonts are optional Tier 2 enhancement. Default templates must remain legible offline and list complete fallbacks. When loading fonts from a CDN, add the required top-of-file dependency comment and use `display=swap`.

## Page grammar

Use this order when the content supports it; omit irrelevant regions rather than filling placeholders:

1. **Mast:** metadata eyebrow, decisive serif title, short deck, and a recommendation/answer card.
2. **Thesis band:** a full-width dark-ink strip for 2–4 decisive facts, criteria, or KPIs. This is not mandatory when there are no meaningful summary facts. **It also loses to the primary figure when both cannot fit the first view** — drop the band and absorb its facts as rows of the recommendation card rather than pushing the main visual below the fold (see SKILL.md, 情報設計: lead with the conclusion and decision). Never state the same fact in both the band and the card.
3. **Evidence sections:** figures, tables, comparisons, or diagrams on paper/surface cards.
4. **Progressive detail:** supporting evidence and raw material in `<details>`.

The first viewport must answer the key question. The title states the issue; the recommendation card states the answer; the thesis band explains why. Do not make the reader infer the verdict from decorative metrics.

## Components

- **Mast background:** paper with an optional 34px line grid at low opacity, faded with a radial mask. Texture must never reduce text contrast.
- **Recommendation card:** surface background, 1px line, 4px green left rule, 12–14px radius, restrained shadow.
- **Thesis band:** `--ink` background, light text, serif values, thin translucent separators.
- **Cards:** use only for bounded evidence. Prefer one strong container over many tiny cards. Radius 14–16px; border plus subtle shadow.
- **Tables:** surface background, separate borders when rounded corners matter, mono column headings, generous horizontal padding.
- **Diagrams:** paper/surface nodes with semantic accents; dark ink edges; arrowheads; explicit labels. Keep decorative grid behind, never inside, the data layer.
- **Details:** serif or strong sans summary, clear focus style, compact body. Collapsed detail must not contain the only statement of the conclusion.
- **Term chip / glossary (optional):** use only when a short inline explanation is insufficient and a glossary helps the reader. The example below is not a requirement for first occurrences.

## Optional terminology links

Prefer an inline explanation. If a glossary link helps, use a normal anchor and visible explanation; the example below uses a visible inline explanation rather than a hover-only popup.

Only explain terms the reader needs. No chip/glossary count invariant is required; resolve every link that is actually used.

```css
/* inline term chip — first occurrence only */
.term { position:relative; color:var(--green-dark); text-decoration:none;
  border-bottom:1px dashed var(--green); cursor:help; font-weight:600; }
.term:hover, .term:focus-visible { background:var(--green-bg); }
.term:focus-visible { outline:3px solid var(--green); outline-offset:2px; }
.term-gloss { display:inline; color:inherit; font:inherit; }
.term-gloss::before { content:'（'; }
.term-gloss::after { content:'）'; }

/* glossary — canonical definitions */
.glossary { margin:0; }
.glossary dt { font-weight:700; color:var(--ink); margin-top:.9rem;
  font-family:'IBM Plex Mono','SFMono-Regular',Consolas,monospace; font-size:.9rem;
  scroll-margin-top:1rem; }
.glossary dt:first-child { margin-top:0; }
.glossary dt:target { background:var(--green-bg); box-shadow:-.5rem 0 0 var(--green-bg), .5rem 0 0 var(--green-bg); }
.glossary dd { margin:.25rem 0 0; color:var(--text); font-size:.9rem; }
@media print {
  .term-gloss { display:none; }
  .term { border-bottom-style:solid; }
}
```

```html
<p>鍵は <a class="term" href="#g-hkdf">HKDF<span class="term-gloss">鍵導出関数</span></a> で用途ごとに分ける。</p>

<details>
  <summary>用語集（2件）</summary>
  <dl class="glossary">
    <dt id="g-hkdf">HKDF — HMAC-based Key Derivation Function</dt>
    <dd>1つの秘密から用途別の鍵を導出する標準手順（RFC 5869）。同じ鍵を複数用途で使い回さずに済む。</dd>
    <dt id="g-idp">IdP — Identity Provider</dt>
    <dd>認証を担う外部サービス。アプリはIdPの発行したtokenを検証するだけで済み、資格情報を自前で保持しない。</dd>
  </dl>
</details>
```

Because the glossary lives inside a collapsed `<details>`, add this so the chip's anchor still lands on the right entry in browsers without native details-auto-expand:

```js
function openAncestorDetails(hash) {
  const target = hash && document.getElementById(hash.slice(1));
  if (!target) return;
  for (let el = target.parentElement; el; el = el.parentElement) {
    if (el.tagName === 'DETAILS') el.open = true;
  }
  target.scrollIntoView({ block: 'center' });
}
document.addEventListener('click', event => {
  const link = event.target.closest('a[href^="#"]');
  if (link) openAncestorDetails(link.hash);
});
if (location.hash) openAncestorDetails(location.hash);
```

Rules:
- The example keeps explanations inline so they do not require hover. In SVG, use an adjacent caption or text alternative.
- If a glossary is useful, choose inline or collapsible presentation for the reader. Add print handling only when printing is required.
- `dt:target` highlighting confirms to the reader that the anchor jump landed on the right entry.
- The anchor is reachable by Tab; the explanation is visible without interacting.

## Desktop scope, interaction, and print

- Even desktop artifacts must remain readable when enlarged or narrowed. Adapt layouts as needed for reflow; a separate mobile app design is not required.
- Keep body text at 16px where practical, secondary text at least 12–14px, and interactive text at least 14px.
- Add visible `:focus-visible` styles. Honor `prefers-reduced-motion`; motion is optional and must not carry meaning.
- Tables use `<caption>` when context is not otherwise explicit and `scope` on row/column headers.
- Clipboard actions need success and failure feedback; do not assume `navigator.clipboard` is available from `file://`.
- For print, expand `<details>` content, remove texture and shadow, use white backgrounds where ink-heavy regions are not essential, prevent cards/figures from splitting where practical, and expose URLs after external links when useful. CSS alone does not reliably reveal a closed `<details>`; use `beforeprint` to remember and open closed elements, then restore them in `afterprint`.

## Controlled variation

These compositions are optional. Keep a coherent hierarchy while adapting palette, typography and layout to the question:

- **Plan/comparison:** recommendation mast + criteria band + side-by-side options + dependency path.
- **Report:** verdict/status mast + evidence table/timeline. Add a KPI band only when meaningful measures clarify the decision without duplicating other content.
- **Review:** verdict mast + severity band + findings grouped by file or theme.
- **Diagram/explainer:** thesis mast + large primary figure + legend + annotations.
- **Compact explainer:** omit the thesis band and texture when there are fewer than three meaningful summary facts. Keep the same typography and surfaces; simplicity is a content-driven variant, not a separate visual style.
