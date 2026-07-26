# Field Review visual system

Use this visual language by default. It is an editorial information system, not a fixed page layout: preserve its tokens and hierarchy while choosing structures that fit the question.

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
2. **Thesis band:** a full-width dark-ink strip for 2–4 decisive facts, criteria, or KPIs. This is not mandatory when there are no meaningful summary facts. **It also loses to the primary figure when both cannot fit the first view** — drop the band and absorb its facts as rows of the recommendation card rather than pushing the main visual below the fold (SKILL.md key question契約 holds the full priority order). Never state the same fact in both the band and the card.
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
- **Term chip / glossary:** first occurrence of a term gets a chip carrying a short gloss and an anchor to the glossary; the canonical definition lives once in a bottom `<dl>`. See below for the copy-paste implementation.

## Term chip and 用語集 (required by default)

Copy this block as-is. The chip is an `<a>`, so it works with keyboard, touch, and print; never substitute a bare `<abbr title>`.

Scope (SKILL.md 基本原則8 is canonical): rephrase insider abbreviations instead of glossing them; leave terms a general software engineer already knows plain; chip and define everything beyond that at first use. Chips and `<dt>` entries stay 1:1 — no dangling links, no unreferenced definitions.

```css
/* inline term chip — first occurrence only */
.term { position:relative; color:var(--green-dark); text-decoration:none;
  border-bottom:1px dashed var(--green); cursor:help; font-weight:600; }
.term:hover, .term:focus-visible { background:var(--green-bg); }
.term:focus-visible { outline:3px solid var(--green); outline-offset:2px; }
.term-gloss { position:absolute; left:0; top:calc(100% + 6px); z-index:20; width:max-content;
  max-width:20rem; padding:.4rem .6rem; background:var(--ink); color:#f6f2e9;
  font-family:'Public Sans',-apple-system,'Hiragino Sans','Yu Gothic',sans-serif;
  font-size:.8rem; font-weight:400; line-height:1.5; border-radius:8px;
  box-shadow:0 6px 18px rgba(40,30,12,.18); opacity:0; visibility:hidden; transition:opacity .12s; }
.term:hover .term-gloss, .term:focus-visible .term-gloss { opacity:1; visibility:visible; }

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
- The chip's `.term-gloss` is a hover/focus layer, so it is clipped inside any ancestor with `overflow` other than `visible`, and it cannot be used inside `<svg>`. In those positions use the anchor link alone (no `.term-gloss` child), or explain the term in a legend or caption directly below the figure.
- Keep the glossary inside `<details>` so the existing `beforeprint` handler expands it for print.
- `dt:target` highlighting confirms to the reader that the anchor jump landed on the right entry.
- The chip is an `<a>`, so it is reachable by Tab and `:focus-visible` reveals the gloss. `cursor: help` signals it is an explanation, not navigation away from the page.

## Desktop scope, interaction, and print

- Mobile support is outside the default scope. Do not add breakpoint-specific layouts or run mobile viewport QA unless the user explicitly requests it.
- Keep body text at 16px where practical, secondary text at least 12–14px, and interactive text at least 14px.
- Add visible `:focus-visible` styles. Honor `prefers-reduced-motion`; motion is optional and must not carry meaning.
- Tables use `<caption>` when context is not otherwise explicit and `scope` on row/column headers.
- Clipboard actions need success and failure feedback; do not assume `navigator.clipboard` is available from `file://`.
- For print, expand `<details>` content, remove texture and shadow, use white backgrounds where ink-heavy regions are not essential, prevent cards/figures from splitting where practical, and expose URLs after external links when useful. CSS alone does not reliably reveal a closed `<details>`; use `beforeprint` to remember and open closed elements, then restore them in `afterprint`.

## Controlled variation

Keep tokens, typography roles, spacing rhythm, and semantic colors stable. Vary composition by content:

- **Plan/comparison:** recommendation mast + criteria band + side-by-side options + dependency path.
- **Report:** verdict/status mast + KPI band + evidence table/timeline.
- **Review:** verdict mast + severity band + findings grouped by file or theme.
- **Diagram/explainer:** thesis mast + large primary figure + legend + annotations.
- **Compact explainer:** omit the thesis band and texture when there are fewer than three meaningful summary facts. Keep the same typography and surfaces; simplicity is a content-driven variant, not a separate visual style.

## Final visual check

- Can a cold reader identify the question, verdict, and strongest evidence in five seconds?
- Does the page still look intentional with web fonts blocked?
- Is every color meaningful, and is every semantic state also labeled?
- Are there fewer, stronger surfaces instead of a dashboard of cards?
- Does print preview remain legible without clipped content or unnecessary ink?
- Does every section describing structure, flow, sequence, or comparison carry its own visual?
- Does every major section have a `<details>` drill-down behind it?
- Were insider abbreviations rephrased rather than glossed, and is every term beyond a general software engineer's vocabulary defined at first use and once in the glossary — without chipping the same term twice or leaving an unreferenced entry?
