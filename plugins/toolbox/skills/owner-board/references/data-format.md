# データとCLI

Python 3.11+ の標準ライブラリだけで動く。JSONの追加・回答反映は更新担当が行い、CLIは検証とHTML生成を担う。
永続DB、HTML編集UI、通知daemon、図の描画engineは追加しない。

## CLI

```bash
python3 <skill-dir>/scripts/owner_board.py validate --data <artifact-dir>/owner-board.json
python3 <skill-dir>/scripts/owner_board.py render --data <artifact-dir>/owner-board.json --output <artifact-dir>/owner-board.html
```

実際の場所に置き換え、shellに合わせて引用する。終了コードは成功0、検証/入出力失敗1。
`validate` はJSON、図、リンク先のローカルファイルを検証する。SVGはJSONと同じdirectory以下に置く。
`render` は全検証と描画が成功してから、出力directory内の一時ファイルを置換する。
失敗しても既存HTMLを上書きしない。出力は通常ファイルの `.html` とし、symlinkを指定しない。
出力先はJSONと同じdirectoryに限定する。別資料の戻りリンクは実際のHTML名に合わせて作成・確認する。
移動する場合は関連資料と図を含むdirectory全体を移す。入力自身を出力先に指定することは拒否する。
新規HTMLは所有者のみ読書きできる0600、既存HTMLは以前のpermissionを維持する。
JSONは変更しない。表示時刻はタイムゾーン付きのHTML生成時刻であり、回答受領時刻とは別。

未知のfield、重複したJSON key、重複ID、存在しない親番号、選択肢とセッション名の衝突を拒否する。
一時ファイルからの置換は部分的なHTMLの公開を防ぐものであり、複数セッションの同時編集を調停するlockではない。
前のJSONを参照しないため、過去の番号の再利用や削除を自動検出することはできない。全項目を保持する運用で防ぐ。回答済み項目の意味の変更も自動検出しないため、当時の内容を編集せず保持する。
提示済みの問い・対象操作・条件・選択肢の意味を変更する場合は、未回答の旧Qを取り下げて新しいQを採番する。
回答済みの旧Qは当時の内容・回答と `answered` を保ち、後継Qの背景に元のQ番号と変更理由を書く。

## 連絡板

| field | 内容 |
|---|---|
| `version` | 整数 `1` |
| `title` / `maintainer` | ページ名と、唯一の更新担当を表す文字列 |
| `namespace` | 統合板は空文字、担当板はASCII英数字とハイフンのsession ID |
| `session_names` | 任意。関係セッションの表示名。選択肢code/labelとの衝突を検出する |
| `terms.preferred_terms` | 任意。避ける用語から希望する用語への文字列map。文章作成時に参照し、rendererは自動置換しない |
| `context` | 任意。報告のみ・返信不要の短い説明などを置くブロック列 |
| `items` | 全項目。回答済み・取り下げも消さずに保持する |
| `related` | 任意。`label` と `href` を持つ関連資料リンクの列 |

個人名や秘密の値を設定の例に使わない。実運用の内容はrepo外で管理する。

## 項目

共通必須: `id`, `title`, `kind`, `state`, `urgency`。

- `id`: 統合板の `Q12`、担当板の `design-Q12`。担当板はnamespaceと接頭辞を一致させる。
  小問は `Q5-1`。親の `Q5` の記録も保持する。項目を小問へ分割した場合、親は取り下げ理由を記録して残せる。
- `kind`: `decision` / `task`。
- `state`: `open` / `preparing` / `answered` / `withdrawn`。
- `urgency`: `today` / `soon` / `none`。準備中の表示はurgencyにかかわらず「準備中・回答不要」。
- `due`: 任意の文字列。期限がある場合、日付・時刻・タイムゾーンを含める。相対表現だけで放置しない。
- `blocks`: 任意の判断材料。下のブロックを自由な順序で並べる。

`open` の必須fieldは `question`（太字の問い）、`purpose`、`background`、`owner_reason`、
`consequence`、`reply`（当該IDと `:` または `：` から始まる返信例）。いずれも空でない文字列。
準備中はまだ選択肢や手順が揃っていなくてよい。`question` や `blocks` で準備状況と提示条件を説明する。

### 判断

`options` と `recommended` が必要。
`options` の各要素は `code`, `label`, `reason`, `drawback` の文字列を持ち、2択以上。
codeは既定で `1` / `2`。英数字のみ、同じ質問内で一意、セッション名と一致させない。
`recommended` は推奨するcodeで、HTMLではその行を先頭へ移す。
不確かな理由は「未検証」「推定」等を文中に明記する。欠点なしなら、その判断の根拠や制限を書く。

### 作業

`inputs`（秘密を含まない入力の説明）、`steps`、`return_expected` が必要。
`steps` は `title` と `blocks` を持つ要素を実施順に並べ、HTMLで番号を付ける。
各手順内にも表・コード・複数の図を自由に置ける。コマンドは `code` ブロックとして記録する。
秘密の値は保存せず、端末で非表示入力する方法を文章と安全なコマンドで説明する。
値をログへ出すコマンド、引数に秘密を埋める例、チャットへの値の返信例を作らない。

### 回答と取り下げ

回答は秘密を除いた原文をtextへ、要約と処理結果はfollow_up.summaryへ記録する。
元の問い・選択肢・手順を保持したまま `state=answered` とし、次の `answer` を追加する。

```json
{
  "text": "1。少人数で先に確認する",
  "at": "2026-01-01T09:00:00+00:00",
  "follow_up": {"state": "pending", "summary": "確認対象の準備待ち"},
  "relays": [{"to": "設計担当", "state": "pending"}]
}
```

日時は例。実際の受領時刻を記録する。`follow_up.state` は `pending` / `done`。
`relays[].state` は `pending` / `sent`。送信成功を確認してからsentにし、関係担当がいなければ空の列。
反映待ち・中継待ちは折りたたみの外へ表示され、記録には回答とその後の対応をまとめ、内側の折りたたみから当時の問い・選択肢・手順も読める。
反映不要なら、その理由をsummaryに書いてdoneにする。回答の訂正は元の回答と訂正内容をtextに残し、対応を再評価する。
取り下げは `state=withdrawn` と `withdrawal`（理由）を追加する。番号は残す。

## 説明ブロック

固定の図種や枚数を要求しない。以下のブロックを `context`、項目の `blocks`、手順の `blocks` へ自由に組み合わせる。
文字列はプレーンテキストで、HTMLとして実行しない。JSON内にMarkdownや任意HTMLを入れても描画されない。

| type | field | 用途 |
|---|---|---|
| `paragraph` | `text` | 本文 |
| `heading` | `text` | カード内の補助見出し |
| `list` | `items`（文字列列）、任意の `ordered`（boolean） | 箇条書き、順序付き説明 |
| `table` | `caption`, `columns`（文字列列）, `rows`（同じ列数の文字列列の列） | 比較、対応表、検証結果 |
| `code` | `text`、任意の `label` | コマンド、コード。改行を保持し、長い行は表示上だけ折り返す |
| `svg` | `path`, `alt`、任意の `caption` | 対応する静的SVG図。生成後はHTMLに埋め込み、元ファイルへの表示依存を持たない |
| `link` | `href`, `label` | 詳しい解説や正本へ移動するリンク |

例えば、背景の文章 → シーケンス図 → 比較表 → フロー図 → 補足資料リンクという順序にもできる。
rendererは図の種類を解釈せず、静的SVGとして扱う。

```json
[
  {"type": "heading", "text": "回答から反映まで"},
  {"type": "svg", "path": "diagrams/answer-sequence.svg", "alt": "オーナーの回答を統合役が担当へ伝え、担当が反映結果を返す"},
  {"type": "table", "caption": "役割", "columns": ["主体", "担当"], "rows": [["統合役", "判断と共有"], ["担当", "作業への反映"]]},
  {"type": "code", "label": "確認用コマンド", "text": "python3 -m json.tool ./sample.json"}
]
```

### SVGとリンクの境界

SVGはviewBox、SVG namespace、図形・線・text/tspan・marker・gradient・内部参照などの静的要素を使う。
`alt` は図が伝える要点を説明し、captionで必要な条件を補う。同じSVGを複数回使っても内部IDを自動で分離する。
script、イベント属性、foreignObject、style要素、外部画像・外部参照、DTD/entity/processing instructionを拒否する。先頭のBOM/XML宣言、version、xml:space、xml:lang、受動的な描画属性は受理する。
exporterが付ける固定のW3C SVG 1.1 DOCTYPEだけは、外部DTDを取得せず削除する。内部subsetや他のDOCTYPEは拒否する。
exporterのclassは削除して板のCSSとの衝突を避ける。data-cell-id、pointer-events、contentStyleTypeも静的表示に不要なので削除する。metadataとルートのcontentは編集用データとして削除する。
class/style要素に依存する外観はそのまま再現しないため、静的な描画属性へ変換してから使う。
style属性はpaint/fontと静的な背景表示の限定されたpropertyだけを受け付ける。属性ベースで描画するSVGを優先する。
対応外のSVGは制約を無効化せず、text/tspanを使う静的SVGへ書き出す。

シーケンス図やフロー図を生成するツールは固定しない。利用できる図解スキル/ツールで作り、上の条件を満たすSVGを使う。
Mermaid等のソースは図として実行しない。使う場合は事前にSVGへ変換し、HTMLに外部の描画ライブラリを追加しない。
図の作り直しが高く付く場合は、その編集可能なソースもローカル成果物directoryへ残せる。

リンクはHTTPS/HTTP、相対ファイル、ページ内fragmentを許可し、javascript/data/file等のscheme、
埋め込み認証情報、protocol-relative URLを拒否する。HTMLとJSONは同directoryへ保存し、関連資料との相対リンクを保つ。
別directoryの正本への相対リンクも許可する。その場合は成果物directory全体の移動だけでは足りず、移動後のリンクを再確認する。
別HTMLは独立した資料として保存し、連絡板に戻る相対リンクを用意する。HTML単体の主要内容はオフラインで読める。

対応属性・要素はrendererの許可リストに限定する。任意の図種を表現できることと、任意のSVG構文を受理することは別である。
Mermaid・PlantUML・draw.ioの既定出力は、そのままでは対応しない場合がある。特にstyle要素、filter、foreignObjectは対応外。
エラーはJSON内のブロック位置とSVG内の要素・属性位置を示す。入力由来の名前や私的なパスは出さない。
図内テキストの検索・選択を保つため、画像data URIへの変換ではなくインラインSVGを使う。

種別に合わないfield（作業のoptions、判断のsteps等）は拒否する。準備中のreplyも拒否する。
準備中に記録した選択肢・手順・影響は草案として表示され、回答不要の表示を保つ。
