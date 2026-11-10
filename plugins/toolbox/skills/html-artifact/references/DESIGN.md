# DESIGN.md — html-artifact

> html-artifactで作る一枚物HTMLのデザイン仕様。書式は [DESIGN.md](https://stitch.withgoogle.com/docs/design-md/overview/) と、日本語タイポグラフィを加えた [awesome-design-md-jp](https://github.com/kzhrknt/awesome-design-md-jp) のテンプレートに倣う。セクション見出しは英語、説明は日本語で書く。

---

## 1. Visual Theme & Atmosphere

- **デザイン方針**: 落ち着いた業務ドキュメント。余白と整列で階層を作り、装飾で目を引かない。
- **密度**: 情報密度は高く、見た目は軽く。罫線や色ではなく、余白・文字の太さ・面の明暗で区切る。
- **キーワード**: 静か、精密、明快、余白、一色のアクセント。
- **構成**: 薄いグレーのページ背景に、白い面（カード）を並べる。図・表・結論はカードに載せ、カードの外には見出しだけを置く。

---

## 2. Color Palette & Roles

コントラスト比は、記載した背景に対する実測値。意味を持たせる色は Accent・Caution・Neutral の3系統だけにする。赤と緑で意味を分けない。

### Accent（推奨・ToBe・強調）

- **Accent** (`#2563eb`): 矢印・強調枠・番号丸など、意味のある線と面。白に対して5.17:1
- **Accent Text** (`#1d4ed8`): Accent Tint上の文字。白に対して6.70:1、Tintに対して6.08:1
- **Accent Tint** (`#eff4ff`): 推奨列・実施事項・ToBeの面
- **Accent Border** (`#bfd3fe`): Accent Tintの面の枠（装飾）

### Caution（注意・リスク・AsIsの問題）

- **Caution** (`#c2410c`): 注意を示す線・破線枠。白に対して5.18:1
- **Caution Text** (`#9a3412`): 注意の文字。白に対して7.31:1、Tintに対して6.75:1
- **Caution Tint** (`#fff4ec`): リスクの吹き出し・問題箇所の面
- **Caution Border** (`#fed7aa`): Caution Tintの面の枠（装飾）

### Neutral

- **Text Primary** (`#1f2937`): 本文・図のラベル。白に対して14.68:1
- **Text Secondary** (`#4b5563`): 補足・凡例・表の見出し。白に対して7.56:1、ページ背景に対して7.05:1
- **Text Tertiary** (`#6b7280`): 白い面の上の注記だけ。白に対して4.83:1
- **Line** (`#64748b`): 意味を持つ中立の線（矢印・軸）。白に対して4.76:1
- **Border** (`#e5e7eb`): カードの枠・表の行区切り（装飾）
- **Node Border** (`#cbd5e1`): 図のノードの枠（装飾。ノードの意味は文字で伝える）
- **Neutral Tint** (`#f3f4f6`): 変わらない箇所・対象外の面。Neutral Text `#374151` で9.37:1
- **Background** (`#f6f7f9`): ページ背景
- **Surface** (`#ffffff`): カード・表・図の面
- **Tooltip** (`#1f2937` 背景 / `#f9fafb` 文字): 14.05:1

---

## 3. Typography Rules

### 3.1 和文フォント

- **ゴシック体**: ヒラギノ角ゴシック、Noto Sans JP、Yu Gothic UI、メイリオ（OSに入っているものだけを使う。Webフォントは読み込まない）

### 3.2 欧文フォント

- **サンセリフ**: 和文フォント内の欧文を使い、最後に system-ui
- **等幅**: ui-monospace, SFMono-Regular, Menlo, Consolas

### 3.3 font-family 指定

```css
--font-sans: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic UI", Meiryo, system-ui, sans-serif;
--font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
```

### 3.4 文字サイズ・ウェイト階層

| Role | Size | Weight | Line Height | Letter Spacing | 用途 |
|---|---|---|---|---|---|
| Title | 28px | 700 | 1.35 | 0.01em | ページタイトル（1つだけ） |
| Heading | 20px | 700 | 1.45 | 0.01em | 節の主張見出し |
| Subheading | 16px | 700 | 1.5 | 0.02em | カード内の小見出し |
| Body | 16px | 400 | 1.75 | 0.02em | 本文・結論ブロック |
| Label | 13px | 600 | 1.5 | 0.04em | 結論の行名・表の見出し・凡例 |
| Figure | 13〜14px | 400〜600 | 1.4 | 0 | SVG内の文字（12px未満にしない） |

- 太字は見出し・行名・強調したい数値だけに使う。本文の文単位の太字は使わない。
- 数値を並べる表・図は `font-variant-numeric: tabular-nums` で桁を揃える。

### 3.5 行間・字間

- 本文は `line-height: 1.75`、見出しは1.35〜1.45。
- 本文の字間は `0.02em`。見出しには `font-feature-settings: "palt"` を付けて詰める。本文には付けない。

### 3.6 禁則処理・改行ルール

```css
line-break: strict;
overflow-wrap: anywhere;
word-break: normal;
```

- 見出しは `text-wrap: balance`、本文は `text-wrap: pretty` で行末の1文字残りを避ける（未対応ブラウザでは無視されるだけ）。

---

## 4. Component Stylings

### Cards

- Background: Surface / Border: 1px solid Border / Radius: 12px / Padding: 24px / Shadow: Level 1
- 図・表・結論ブロックは必ずカードに載せる。カードの中にさらにカードを入れない。

### 結論ブロック

- 1枚のカードに3行（課題・目的・実施事項）。左に104px幅の行名（Label、Text Secondary）、右に本文（Body）。行の間は1px Borderで区切る。
- 実施事項の行だけ Accent Tint の面にし、左端に3px の Accent の帯を付ける。行名は Accent Text。面はカードの左右と下の端まで伸ばす。このためカードの上下余白は0にし、余白は各行に持たせる（下のベースCSSの `.conclusion`）。
- 直下に重大なリスクと推奨を覆す条件を Callout で置く。

### Callout（重大なリスク・注意）

- Background: Caution Tint / Border: 1px solid Caution Border / Radius: 10px / Padding: 12px 16px
- 先頭に16pxの線画アイコン（inline SVG、Caution）と、Caution Textの太字ラベル。本文は Text Primary。

### Tables

- 外枠はカードに任せ、表自体には縦線を引かない。行の区切りだけ1px Border。
- 見出し行: Label（13px/600、Text Secondary）、下に1px Border Strong（`#d1d5db`）。
- セル: padding 12px 16px。数値列は右寄せ・tabular-nums。
- 推奨列: 列全体を Accent Tint にし、見出しに「推奨」Pillを付ける。

### Pills

- Radius: 999px / Padding: 2px 8px / 12px 600
- Accent Tint＋Accent Text、Caution Tint＋Caution Text、Neutral Tint＋`#374151` の3種類。

### 「?」ボタンとツールチップ

- ボタン: 18px円、1px solid Node Border、Surface、Text Secondary、12px 600。
- ツールチップ: Tooltip の面、13px、line-height 1.6、Radius 8px、Padding 8px 10px、最大幅280px、Shadow Level 2。

### details

- summary: 14px 600 Text Secondary、先頭に回転する山括弧。開いた中身は15px。
- 枠は付けず、上に1px Borderだけを引く。

### Figures（inline SVG）

- ノード: Radius 8、塗りはSurfaceまたはNeutral Tint、枠は1px Node Border。文字14px Text Primary、補足13px Text Secondary。
- 強調ノード（ToBe・推奨）: 塗りAccent Tint、枠1.5px Accent。
- 問題ノード（AsIsの問題・欠落）: 塗りCaution Tint、枠1.5px Caution。存在しないものは破線（`stroke-dasharray="4 4"`）。
- 矢印: 1.5px Line。強調する流れだけ Accent 2px。矢じりは小さく（markerWidth 6〜7）。
- グループ（repo・層）: 塗りなしかBackground、枠1px Border、左上に13px 600 Text Secondaryのラベル。
- AsIsとToBeは同じ骨格で左右に並べ、変わった部分だけ色が変わるようにする。
- 影・グラデーション・3D表現は使わない。

---

## 5. Layout Principles

### Spacing Scale

| Token | Value | 用途 |
|---|---|---|
| XS | 4px | アイコンと文字 |
| S | 8px | Pill・凡例の間 |
| M | 12px | 表のセル・行間の区切り |
| L | 16px | カード内の要素間 |
| XL | 24px | カードの内側余白 |
| XXL | 48px | 節と節の間 |

### Container

- Max Width: 1160px / Padding: 32px 40px 80px / 中央寄せ
- 見出しとカードの左端を揃える。本文を中央寄せにしない。

### Grid

- 比較・並置は2〜3列のCSS Grid、gap 16px。4列以上は表か図にする。

---

## 6. Depth & Elevation

| Level | Shadow | 用途 |
|---|---|---|
| 0 | none | 図の中の要素すべて |
| 1 | `0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06)` | カード |
| 2 | `0 8px 24px rgba(16,24,40,.14)` | ツールチップ |

---

## 7. Do's and Don'ts

### Do

- 階層は余白・文字の太さ・面の明暗で作る。
- アクセントはAccent一色。Cautionは問題箇所だけに使う。
- 図の線と文字の色は、上の表の組み合わせだけを使う。

### Don't

- 黒や濃いグレーの太い枠線で囲まない。ブラウザ既定の格子状の表にしない。
- グラデーション、すりガラス、ネオン、強い影、角丸24px以上の多用をしない。
- 絵文字をアイコンや見出しの飾りに使わない（必要なアイコンは線画のinline SVG）。
- 彩度の高い面に白抜き文字を大きく置かない（番号丸・Pill程度に留める）。
- 色を4系統以上使わない。同じ意味に別の色、別の意味に同じ色を使わない。
- 文章全体を太字にしない。見出しを全幅の色帯にしない。

---

## 8. Responsive Behavior

- 対象外。1280×800前後のデスクトップだけを想定し、media queryは書かない。
- 幅が足りない図は、その図のカード内だけ横スクロールにする。

---

## 9. Agent Prompt Guide

### クイックリファレンス

```
Accent: #2563eb（文字は #1d4ed8、面は #eff4ff）
Caution: #c2410c（文字は #9a3412、面は #fff4ec）
Text: #1f2937 / #4b5563
Background: #f6f7f9 / Surface: #ffffff / Border: #e5e7eb
Font: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic UI", Meiryo, system-ui, sans-serif
Body: 16px / line-height 1.75 / letter-spacing 0.02em
```

### ベースCSS（そのまま使い、足りない部品だけ足す）

```css
:root {
  color-scheme: light;
  --accent: #2563eb; --accent-text: #1d4ed8; --accent-tint: #eff4ff; --accent-border: #bfd3fe;
  --caution: #c2410c; --caution-text: #9a3412; --caution-tint: #fff4ec; --caution-border: #fed7aa;
  --text: #1f2937; --text-2: #4b5563; --text-3: #6b7280; --line: #64748b;
  --border: #e5e7eb; --border-strong: #d1d5db; --node-border: #cbd5e1;
  --neutral-tint: #f3f4f6; --bg: #f6f7f9; --surface: #ffffff;
  --shadow-1: 0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.06);
  --shadow-2: 0 8px 24px rgba(16,24,40,.14);
  --font-sans: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic UI", Meiryo, system-ui, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.75 var(--font-sans);
  letter-spacing: .02em; line-break: strict; overflow-wrap: anywhere; -webkit-font-smoothing: antialiased; }
main { max-width: 1160px; margin: 0 auto; padding: 32px 40px 80px; }
figure { margin: 0; }
h1, h2, h3 { font-feature-settings: "palt"; text-wrap: balance; letter-spacing: .01em; }
h1 { font-size: 28px; line-height: 1.35; margin: 0 0 20px; }
h2 { font-size: 20px; line-height: 1.45; margin: 48px 0 12px; }
p, li, dd { text-wrap: pretty; }
code, .mono { font-family: var(--font-mono); font-size: .92em; letter-spacing: 0; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  box-shadow: var(--shadow-1); padding: 24px; }
.conclusion { padding: 0 24px; }
.conclusion .row { display: grid; grid-template-columns: 104px 1fr; gap: 16px; padding: 14px 0; }
.conclusion .row + .row { border-top: 1px solid var(--border); }
.conclusion .row.act { margin: 0 -24px; padding: 14px 24px; background: var(--accent-tint);
  box-shadow: inset 3px 0 0 var(--accent); border-radius: 0 0 11px 11px; }
.conclusion .row.act .label { color: var(--accent-text); }
.label { font-size: 13px; font-weight: 600; letter-spacing: .04em; color: var(--text-2); }
.pill { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; font-weight: 600; }
.num { font-variant-numeric: tabular-nums; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 4px; }
svg text { font-family: var(--font-sans); fill: var(--text); }
```
