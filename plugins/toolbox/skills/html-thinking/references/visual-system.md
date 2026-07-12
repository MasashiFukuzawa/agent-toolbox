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

Google Fonts are optional Tier 2 enhancement. Default templates must remain legible offline and list complete fallbacks. When loading fonts from a CDN, add the required top-of-file dependency comment and use `display=swap`.

## Page grammar

Use this order when the content supports it; omit irrelevant regions rather than filling placeholders:

1. **Mast:** metadata eyebrow, decisive serif title, short deck, and a recommendation/answer card.
2. **Thesis band:** a full-width dark-ink strip for 2–4 decisive facts, criteria, or KPIs. This is not mandatory when there are no meaningful summary facts.
3. **Evidence sections:** figures, tables, comparisons, or diagrams on paper/surface cards.
4. **Progressive detail:** supporting evidence and raw material in `<details>`.

The first viewport must answer the key question. The title states the issue; the recommendation card states the answer; the thesis band explains why. Do not make the reader infer the verdict from decorative metrics.

## Components

- **Mast background:** paper with an optional 34px line grid at low opacity, faded with a radial mask. Texture must never reduce text contrast.
- **Recommendation card:** surface background, 1px line, 4px green left rule, 12–14px radius, restrained shadow.
- **Thesis band:** `--ink` background, light text, serif values, thin translucent separators.
- **Cards:** use only for bounded evidence. Prefer one strong container over many tiny cards. Radius 14–16px; border plus subtle shadow.
- **Tables:** surface background, separate borders when rounded corners matter, mono column headings, generous horizontal padding. Wrap in an overflow container on narrow screens.
- **Diagrams:** paper/surface nodes with semantic accents; dark ink edges; arrowheads; explicit labels. Keep decorative grid behind, never inside, the data layer.
- **Details:** serif or strong sans summary, clear focus style, compact body. Collapsed detail must not contain the only statement of the conclusion.

## Responsive, interaction, and print

- At `max-width: 760px`, collapse mast and multi-column evidence to one column; reduce outer padding to 24px; keep touch targets at least 44px.
- Keep body text at 16px where practical, secondary text at least 12–14px, and interactive text at least 14px.
- Never preserve a desktop side rail at the cost of a narrow main column. Tables and code may scroll horizontally inside their own region.
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
- Does 375px preserve reading order, labels, tables, and controls?
- Does print preview remain legible without clipped content or unnecessary ink?
