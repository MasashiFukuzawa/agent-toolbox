---
name: html-artifact
description: >-
  計画、比較、図解、レビューを自己完結 HTML の一枚物として可視化する。表や SVG、並列レイアウトが理解を助ける時に使う。会話内の小さな図には ascii-diagram を使う。「HTML一枚物で」「比較を視覚化して」を正のトリガーとし、production UIや対話内ですぐ読む小さな図には使わない。
---
# HTML Artifact

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

- The **first view** (validate at 1440×900 desktop without scrolling) is composed ONLY of content that answers the key question — verdict, comparison, map. Everything else goes below or into `<details>`.
- Write the key question as an HTML comment at the top of the file (`<!-- key question: ... -->`) so later edits stay anchored to it.
- Self-check after writing: open the page cold and ask "does the first screen answer the key question in 5 seconds?" If the reader must scroll or expand to get the point, restructure.
- **first viewの席が足りないときの優先順位（迷ったらこの順）:** ①結論・推奨（必須） ②key questionに直接答える主要visual（比較表・主図） ③要約factの帯（thesis band）。**②と③が両立しないなら②を採り、factは結論cardの行として吸収する**（同じfactをbandとcardに二重に書かない）。席を空けるために結論や主要visualを下げてはいけない。

## 基本原則

### Default visual language: Field Review

Every artifact uses the Field Review visual system unless the user explicitly requests another style. Treat it as a stable editorial grammar, not a rigid template: warm paper, dark ink, forest-green primary accent, serif display type, plain sans body type, mono metadata, one decisive recommendation, and a small number of strong evidence surfaces.

Before writing CSS, read `references/visual-system.md`. Start from the nearest file in `assets/templates/`; do not invent an unrelated palette or generic dashboard aesthetic. Content determines whether a thesis band, texture, cards, or motion are present—the tokens and hierarchy remain consistent.

**templateから始めるときの手順（templateは「動くサンプル」なので、そのまま残すと壊れる）:**

| templateの部分 | 扱い |
|---|---|
| CSS tokens・typography・`.term`/`.glossary` のCSS | **正本。そのまま使う** |
| `<script>`（print用の `beforeprint`/`afterprint`、anchor用の `openAncestorDetails`） | **正本。そのまま使う** |
| body構造・section構成・placeholder文 | **例示。内容に合わせて作り替える** |
| サンプルのchipと用語集項目 | **最初に全削除してから自分の語で作り直す** |

- **サンプルchipと用語集は部分置換しない。** 片方だけ残すとdangling linkか未参照項目になり、原則8の1:1不変条件を自分で破る。**先に全部消す**
- `lang` を本文の主言語に変える（日本語本文なら `lang="ja"`）
- `<summary>用語集（N件）</summary>` の N を実項目数に合わせる
- 使わないplaceholder sectionは**削除する**。中身のないまま残すと空accordion・図のないsectionになり、原則6/7に違反する

1. **Information density over word count.** A well-structured 80-line HTML page carries more than a 300-line Markdown doc. Prefer tables, side-by-side columns, and SVG over prose repetition.

2. **Self-contained.** One `.html` file, openable in any browser with no network required (unless a 2nd-tier CDN is explicitly needed — see Self-containment rules). The reader should be able to email it, open it offline, and have it still work in six months. Web fonts are enhancement only; Field Review must remain intentional with its serif/sans/mono fallback stacks.

3. **Spatial structure is the point.** Use the layout itself to communicate: parallel columns convey parity; hierarchy of font sizes conveys importance; a timeline SVG conveys sequence. Do not default to a single linear column unless the content is genuinely linear.

4. **Desktop artifact by default.** Optimize and validate for desktop reading. Mobile-specific layout, breakpoints, and 375px testing are not required unless the user explicitly requests mobile support. Keep the viewport meta tag for sane browser behavior, but do not treat mobile compatibility as a completion criterion.

5. **Optimized for being read, not maintained.** This is a disposable artifact. Favor clarity over abstraction. Inline everything. A little duplication in CSS is fine.

6. **Visualize aggressively — prose is the fallback, not the default.** Hard rules, not suggestions:
   - **3+ parallel items → table or parallel columns** — 表と「1案=1カラム」の並列レイアウトは**同格の正解**。禁止しているのは*同じ形の項目を箇条書きで縦に並べること*。性質の違う3項目（目的・推奨・期限など）の箇条書きは該当しない
   - **Any relationship, flow, sequence, or structure → diagram (SVG)** — boxes and arrows, timeline, layered map
   - **Process/phases → timeline or step visual**, states → color-coded badges
   - **Prose is limited to what visuals cannot carry**: rationale, nuance, caveats — attached to the visual it explains, 1-3 sentences at a time
   - **First-view text budget: ~200 Japanese characters (or ~40 English words) of running prose.** If the first view has more, convert to visuals or demote into `<details>`.
     **数え方（これ以外は数えない）:** first viewに可視で入っている「文としての散文」だけ — `<p>` や card本文など。**除外**: `.term-gloss` などhoverで出る非表示テキスト、`<details>` 内、箇条書き・番号リストの項目、表のセル、SVG内の `<text>`、見出し・eyebrow・badge・KPI値。
     この数値は目安であり、**最終判定は「初見の読み手が5秒で答えを掴めるか」**。数えた結果と5秒判定が食い違ったら5秒判定を採る。(Cognitive basis: references/cognitive-load.md)

   **図解は「多め」が既定。** Per-content obligation, not a numeric quota: **構造・流れ・順序・比較・状態遷移を説明するsectionは、それぞれ自前のvisual（SVG図・表・timeline・badge）を持つ**。散文だけのsectionは例外であり、`references/cognitive-load.md` の「例外（散文が正しい場合）」に該当する場合のみ許される。折りたたんだ `<details>` の中も同じ扱い — 詳解side こそAs-Is → To-Be図やstep図が効く。
   逆に、関係が存在しない情報を箱と矢印にするのは装飾であり禁止（同ファイル参照）。**「図の数」ではなく「visualを持つべきsectionを取りこぼしていないか」で判定する。**

7. **Progressive disclosure is the core advantage of HTML — use it by default.** HTML's defining strength over Markdown is that detail can be *present but hidden*: collapsed in an accordion, revealed only on demand. So the goal is never "concise *or* complete" — it is **both at once**. Design every artifact as two layers:
   - **Surface layer (always visible):** a concise, scannable overview — the headlines, the verdict, the shape of the thing. A reader who only sees this layer should still understand the gist.
   - **Detail layer (collapsed by default):** the full supporting evidence, edge cases, raw data, long code, derivations, alternatives considered. **Do not cut detail to stay concise — push it into `<details>` instead.** Brevity comes from collapsing, not from deleting.

   Wrap each detail block in `<details>` (collapsed, i.e. no `open` attribute) with a `<summary>` that names what's inside and ideally hints at its scope ("Full migration steps (14)", "Why we rejected Option B"). The reader expands only what they need. This is not an optional flourish — it is the default information architecture for this skill.

   **既定の要求水準（原則6と同じく、section数に対する割当ではない）:** 表層は「結論と形」だけを載せ、**表層を読んで「なぜ？」「どうやって？」「根拠は？」が湧く箇所には、必ずその答えを開ける口を置く**。判断・変更・推奨・数値・リスクが出てくる箇所はほぼ全て該当する。逆に、疑問が湧かない箇所（自明な列挙、既に完結している表）に形だけの `<details>` を足すのは空accordionであり禁止。
   自己点検は「sectionの何割に詳解が付いたか」ではなく「**表層で湧いた疑問のうち、開ける口がないものが残っていないか**」で行う。

   **Drill-down template** — inside a `<details>`, structure substantive topics in this order so every expansion reads the same way:
   1. **背景・課題・目的** (why this exists, 1-3 lines)
   2. **As-Is → To-Be** (current vs target state — prefer a 2-column layout or before/after diagram)
   3. **詳細・根拠** (evidence, data, code, edge cases)

   Not every `<details>` needs all three (raw-data blocks don't), but any "explain this decision/change" block does.

8. **語彙で読者を止めない。** 読み手が語彙を知らないだけで読めなくなるのは、内容の難しさではなく単なる摩擦なので常に潰す。優先順位は「使わない → 先に定義 → 用語解説」の順。上位で解決できるものを下位で処理しない。

   **判定順（この順で止まったところが答え）:** ①**言い換えられるか** → 言い換える（chipにしない） ②**一般的なSWEの語彙を超えるか** → 超えなければ素のまま ③超えるなら **chip + 用語集**。
   **閾値の内外が判断できない境界語は、chip化ではなく①の言い換えで消すのが第一手。** 「迷ったら解説する側に倒す」は、言い換え不能で閾値の判断もつかない語に対する最後の指針であって、②の判断を飛ばす許可ではない。

   **(1) 内輪の略語・造語はそもそも使わない（第一選択）**
   組織固有の略語、そのプロジェクト内でだけ通じる呼称、内部システム名の略記、chat上の口語的な短縮形は、**一般名詞か正式名称に言い換える**。「解説を付ければ使ってよい」ではない — 言い換えられるなら言い換えるのが正解。正式名称が存在せず言い換え不能な場合に限り、(2) に従って初出で定義してから使う。

   **(2) 使うなら「先に定義、それから使用」**
   読み手が意味を知らない語に出会ってから用語集を探す、という順序にしない。**初出の位置で定義が読める状態**にする（次項のchipがこの役割）。chipが使えない位置（SVG内、`overflow` container内など）では、その語が最初に出る直前の文か、図直下のcaption/legendで定義する。

   **(3) 解説する／しないの線引き — 基準は「一般的なソフトウェアエンジニアの語彙」**
   - **解説しない（素のまま使う）:** 一般的なソフトウェアエンジニアが理解できる範囲。API・HTTP・cache・index・CI/CD・race condition・rollback・schema・token 等
   - **用語解説を作る:** その範囲を超える語すべて。①特定領域の専門用語（distributed tracing の span / context propagation、暗号の HKDF、会計の ARR 等）②標準仕様の略号（OTLP、W3C traceparent、SCIM 等）③特定product/serviceに固有の概念名 ④一般的でないlibrary/tool名 ⑤(1)で言い換え不能だった固有の略語
   - **判定軸は閾値ひとつ。①〜⑤は「閾値を超える語の典型例」であって独立した強制カテゴリではない。** カテゴリに当てはまっても閾値の内側ならchip化しない（例: JWT・TLS・SQL・REST は標準仕様の略号だが一般的なSWEの語彙内なので素のまま使う）。カテゴリと閾値の判定が食い違ったら**常に閾値が勝つ**
   - key question契約で宣言した読み手が一般的なSWEより語彙が狭いとき（非エンジニア、他領域のjunior等）は、**この閾値を下げる**。上げない
   - **迷ったら解説する側に倒す。** 用語集は折りたたまれているので、余分な1項目のコストはほぼゼロ。逆に説明のない専門用語は読者をその場で止める
   - ただし1文に2つ以上のchipが並ぶなら、その文自体を書き直す（原因は語彙ではなく文の詰め込み）

   **仕組みは2層。定義の正本は下部の用語集に1回だけ書く:**
   - **用語集（正本）:** ページ下部の `<details><summary>用語集（N件）</summary>` 内に `<dl>` で全項目。各 `<dt>` に `id="g-{slug}"`。ここに正式名称・展開形・1〜3文の説明を書く。**本文で参照されない項目は置かない**（逆に、chipのlink先が存在しないのも不可）。
   - **inline chip（初出のみ）:** 本文の初出箇所を `<a class="term" href="#g-hkdf">HKDF<span class="term-gloss">鍵導出関数</span></a>` の形にする。chipが運ぶのは**40字以内の短いgloss**だけで、詳細は用語集へ飛ばす。同じ語の2回目以降はchipにしない（ページが注釈だらけになる）。
   - CSS/HTMLの実装形は `references/visual-system.md` の Components を参照（コピペ可）。

   **やらないこと:**
   - **`<abbr title="...">` 単体は不可** — keyboardで開けず、touchで出ず、そこに情報があること自体が見えない。上のchip形式を使う。
   - **`overflow` を持つcontainerの内側とSVGの内側ではtooltip（hoverで浮く層）を使わない** — clipされる。その位置では用語集へのanchor linkだけにする（例: 図のnode名は図の直下のlegendやcaptionで解説する）。

## 規則が衝突したときの優先順位

上の原則は互いに競合しうる（例: 図解を増やすと初見1画面の席が足りない、結論を1文で言うと用語chipが2つ並ぶ）。**個別のペアを覚える必要はない。衝突したら常にこの順で上を採る。**

1. **読み手が初見で結論を掴める**（key question契約）
2. **内容が正しく、根拠が辿れる**
3. **表層は薄く、詳細は `<details>` に置く**（原則7）
4. **構造・関係はvisualで示す**（原則6）
5. **語彙で読者を止めない**（原則8）
6. **見た目の一貫性**（Field Review）

**上を守るために下を崩すのは正しい。下を守るために上を犠牲にするのは常に誤り。** 数値の目安（初見200字、1文あたりのchip数、thesis bandの有無、用語集の件数）はすべてこの序列の下位にある — 目安を満たすために結論を下げたり、根拠を削ったり、詳細を消したりしない。

**機構が位置的に使えない場所では、その規則の「予算」を消費しない。** ある規則の実装手段がその位置で使えないなら、規則違反ではなく**別手段で同じ目的を果たす**。判断に迷ったら「読み手はここで止まるか？」だけを見る。
- 例: 語の実際の初出がSVG内で、そこにchipを置けない → その出現は「初出slot」を消費しない。図直下のlegend/captionで定義するか、clipされない散文での最初の出現をchipにする。どちらでもよく、両方やらない
- 例: 結論を述べる短い行に用語が2つ必要 → 「1文に2chipまで」は下位規則。結論の明快さを優先し、chipは説明sectionの最初の出現に置き、結論側はgloss無しのanchor linkにする

**chipを置ける位置／置けない位置（初出slotの判定に使う）:**
- **置ける:** 本文の段落、リスト項目、表のセル、図の caption・figcaption・legend
- **置けない（＝その出現は初出slotを消費しない）:** `<svg>` の内側、`overflow` が visible 以外のcontainerの内側、`<head>`（`<title>`・`<meta>` はmarkupを持てない）、見出し（`<h1>`〜`<h6>`）、`<summary>`
- **見出しと `<summary>` の文言を用語規則で決めない。** 見出しは内容で決め、chipは本文側の最初の「置ける」位置に置く。`<title>` に専門用語が入るのは正常であり、違反ではない
- レイアウト設計の順序として、**用語の洗い出しを先に済ませ、clipされない散文sectionを対象語の初出より前に置く**。「chipを置く席がない」構成にしてから困らない

## 出力contract

Every HTML file produced by this skill must satisfy:

```
<!doctype html>
<html lang="{本文の主言語。日本語で書くなら ja}">
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
- `lang` は本文の主言語に合わせる（日本語本文なら `ja`）。`lang` が実際の言語と違うと、行間・禁則・読み上げがすべて崩れる
- **不変条件（機械的に確認できる）:** 本文のchip数 ＝ 用語集の `<dt>` 数 ＝ `<summary>` に書いた件数。3つが揃わないなら直す
- Inline `<style>` and `<script>` — no external `.css` or `.js` files
- **Field Review light theme only** — use the shared paper/ink/green tokens; do not add `@media (prefers-color-scheme: dark)` overrides
- **No file-size or length target.** 分かりやすさが最優先。長さを理由に図解・詳解・用語集を削らない。逆に、内容のない冗長さは長さの問題ではなく品質の問題として直す
- 用語集 `<details>` を持つ（解説対象語が0件のときのみ省略可）
- If any 2nd-tier external resource is used, add a comment at the very top: `<!-- requires: CDN: tailwind, chart.js — will not render offline -->`

## コスト規律（出力の長さではなく、生成の無駄を削る）

出力HTMLの長さは制約しない。削るのは**書くための無駄**であって、読み手が受け取る情報ではない。tokenは図解・詳解・用語集という実体に使い、以下には使わない。

**tokenを使わない対象:**
- **同じ内容の二重記述** — 用語の定義は用語集に1回だけ（chipは短gloss+link）。詳解に書いたことを表層で繰り返さない
- **繰り返す `style="..."` 属性** — 同じ装飾が3箇所以上に出たらclassを1つ定義する。「読むためのCSS重複」は基本原則5の通り許容だが、**書くために同じ属性列を何度も打つのは純粋な無駄**
- **verboseなinline SVG** — 同形状のnodeが多数あるなら `<symbol>` + `<use>`
- **ファイル全体の書き直し** — 修正はEditで差分適用する。全文再出力しない
- **referencesの全読み** — 下表の通り。「読まない」と決まっているものを読むのが無駄であり、必読を飛ばすのは無駄ではなく手抜き

  | file | 扱い |
  |---|---|
  | `references/visual-system.md` | **必読**（CSSを書く前に） |
  | `references/cognitive-load.md` | **必読**（原則6の数値と「散文が正しい場合」の例外判断の根拠。例外を使うなら必ず読む） |
  | `references/patterns-*.md` | **実際に描く構造に対応するものだけ**。本数の上限ではない（比較表＋SVG図解が両方中核なら planning と diagram の2つを読むのが正しい）。描かない構造のものは読まない |
  | `references/self-containment-checklist.md` | **Tier-2のCDNを使うとき、または納品前の最終確認をするときに読む**。Tier-1だけで完結する場合はSKILL.md内の要約で足りる |
- **人間判断の読み返しの重複** — 5秒判定・冗長さ・トーンのような主観的self-checkは1回。同じ観点で読み返さない（※機械検証の再実行はこれに含まれない。編集したら再実行する）
- **chatへのHTML貼り付け・長い自己説明** — pathと要点だけ報告する
- **中身のない引用** — code/diff/logは関係する数行だけ。ファイル全文を貼らない

**判定基準:** 「このtokenは読み手が受け取る理解を増やすか？」増やすなら長さを気にせず書く。増やさないなら1文字も書かない。

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

**納品前のvisual自己点検（主観判断なので読み返しは1回。コスト規律参照）:**
- web fontsがblockされてもfallback stackだけでintentionalに見えるか
- print previewがclipや不要なinkなしで読めるか
- すべての色が意味を持ち、semantic stateには色以外のlabelも付いているか

## interaction pattern（任意）

Add interactivity only when it solves one of these problems. If none apply, use static HTML.

**Problem → Pattern:**
- Reader needs to send a decision back to Claude → **send-as-prompt button**
- Artifact has more dimensions than fit on one screen → **toggle filters**
- Artifact mixes overview and detail → **`<details>/<summary>`**（既定。基本原則7）
- Reader may not know a term → **term chip + 用語集**（既定。基本原則8）

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
<label><input type="checkbox" onchange="toggleClass('row-experimental','hidden',!this.checked)" checked> Experimental</label>
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
No JS is required for screen use. For reliable print output, use `beforeprint` to remember and open closed `<details>`, then restore them in `afterprint`; CSS display rules alone are insufficient across browsers. Use `<details>` for long reference sections, raw data, supporting evidence, rejected alternatives, derivations, and any block that adds depth but would clutter the overview. The `<summary>` should name the content and hint at its scope so the reader can decide whether to expand. Nest `<details>` when detail has its own sub-detail.

### Pattern D: Term chip + 用語集
基本原則8の実装。正本は用語集、chipは短glossとanchorのみ。
```html
<!-- 本文の初出箇所 -->
<a class="term" href="#g-hkdf">HKDF<span class="term-gloss">鍵導出関数</span></a>

<!-- ページ下部（用語集が正本） -->
<details>
  <summary>用語集（4件）</summary>
  <dl class="glossary">
    <dt id="g-hkdf">HKDF — HMAC-based Key Derivation Function</dt>
    <dd>1つの秘密から用途別の鍵を導出する標準手順（RFC 5869）。同じ鍵を複数用途で使い回さずに済む。</dd>
  </dl>
</details>
```
CSSは `references/visual-system.md` の Components にある。`overflow` containerやSVGの内側ではtooltipがclipされるため、その位置ではchipを使わずanchor linkのみ、または図の直下のlegendで解説する。

## production frontendとの関係

| Aspect | html-artifact (this skill) | frontend-design |
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

語彙・詳解・報告の禁止事項（`<abbr>` 単体、毎回chip化、内輪略語、長さを理由の削除、サイズ報告など）は基本原則6〜8と「報告に含めないもの」に定めてある — この表には本文にない知見だけを載せる。

## File delivery & naming

**File name convention:** `{purpose}-{slug}.html`
- Examples: `plan-auth-rewrite.html`, `review-pr-1234.html`, `report-q2-incident.html`, `diagram-event-flow.html`

**Default save location（この順で決める）:**
1. ユーザーが指定した場所
2. project が `.claude/artifacts/` の慣習を持つならそこ
3. **cwd が git リポジトリなら、リポジトリ内には書かない** — session の一時directory（scratchpadなど）に置き、絶対パスで報告する。成果物は使い捨てなので、他人のリポジトリの作業ツリーを汚してcommit対象に混ぜてはいけない
4. cwd がリポジトリでなければ cwd

**After writing:** open the file automatically, then report the path. Run the platform's open command yourself so the reader sees the result immediately — do not just print the command and wait:
```bash
open /abs/path/to/plan-auth-rewrite.html        # macOS
xdg-open /abs/path/to/plan-auth-rewrite.html    # Linux
start /abs/path/to/plan-auth-rewrite.html       # Windows
```
Use the absolute path — a relative path is ambiguous once the file lives outside cwd. Then tell the user where it is:
```
Created and opened: /abs/path/to/plan-auth-rewrite.html
```
If opening fails (e.g. headless environment), fall back to printing the `open` command so the user can run it.

### 検証手段と証跡の置き場（自動検証する場合）

既定は `open` による目視まで。それ以上の自動検証（1440×900のfold確認、tooltipのclip確認など）を行うなら、手段と副産物の置き場をこう固定する。**発明しなくてよい。**

- **`file://` は使えない前提で始める。** browser自動化toolは `file:` protocolを拒否することが多い。成果物のdirectoryで `python3 -m http.server <port> --bind 127.0.0.1` を立て、`http://127.0.0.1:<port>/<file>.html` で開く。終わったらserverを止める
- **screenshotより `browser_evaluate` 相当の実測を優先する。** 「foldに入っているか」「clipされていないか」は数値（`getBoundingClientRect()`、`scrollWidth`、`getComputedStyle`）で確定でき、画像を保存する必要がない
- **危険なのは「何を出力するか」ではなく「出力先がどう決まるか」。** browser自動化toolは screenshot を撮らなくても、navigate や snapshot だけで **cwd相対のoutput directory**（`.playwright-mcp/` 等）にログを自動保存する。したがって:
  1. 作業開始時に `git status --porcelain` を保存してbaselineにする（提示済みのsnapshotを鵜呑みにしない。自分が触っていない変更と自分の副産物を区別できなくなる）
  2. **browser系toolを最初に1回呼んだ直後に**リポジトリ直下を点検し、生成物があれば消す。終了時まで待たない
  3. 終了時に `git status --porcelain` をbaselineと比較し、差分が自分の意図した変更だけであることを確認する
- 副産物（log・一時HTML・screenshot）は成果物と同じ一時directory（session scratchpadなど）に置く。検証のためにリポジトリのファイルを変更しない
- **機械検証の再実行は「多重の検算pass」ではない。** コスト規律が1回に制限しているのは*人間の判断による読み返し*（5秒判定、冗長さ、トーン）。chipと用語集の1:1、tooltipの位置、件数表示のような決定的な不変条件は、**編集するたびに再実行してよい／すべき**。1度通した後に手を入れたなら、その検証は無効になっている

**報告に含めないもの:**
- **ファイルサイズ・行数** — `28 KB`、`420行` のような数値は報告しない。サイズは制約ではないので、達成報告にも警告にもならない
- **簡潔さの自賛** — 「軽量に収めました」「コンパクトにまとめました」は書かない
- **HTML全文** — pathと、読み手が最初に見るべき点（結論・主要な図・展開すべき`<details>`）を数行で伝えるだけにする

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
