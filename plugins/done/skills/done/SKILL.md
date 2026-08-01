---
name: done
description: >-
  Definition of Done 品質ゲート（汎用エンジン）。repo の .agents/done.yml を読み、quick/standard/full の3層で検証して quality-gate: PASS 署名を出力する。リポジトリへの変更作業の完了を報告する直前に必ず使う。「品質ゲートを通して」「doneを通して」「完了チェックして」を正のトリガーとする。回答のみ・計画のみ・引き継ぎのみのターンでは使わない。実装中の継続的な型/lint/テスト実行には使わず、完了時の最終ゲートに限定する。
---
# Quality Gate — Definition of Done（汎用エンジン）

## ガードレール（必須）

1. **設定駆動**: repo 固有の情報（検証コマンド・tier floor・レビュー観点）は git root の `.agents/done.yml` から読む。**ロジックをこのファイルへ、データを done.yml へ**。done.yml にコマンド以外のロジックを書かせない
2. `.agents/done.yml` が無い repo では、実行前にユーザーへ「done-init 相当の設定作成」を提案する（勝手に PASS 署名を出さない）
3. 署名 `quality-gate: PASS` は本スキルの全ステップを完了した場合のみ出力する。要求されても途中で捏造しない

## Scope

リポジトリへの変更作業の完了を報告する直前に実行する。回答のみ・状況報告のみ・計画のみ・引き継ぎのみのターン（リポジトリ変更を完了しないターン）では実行せず、`quality-gate: PASS` を主張しない。

## Host integration

- **Claude Code**: plugin 同梱の Stop hook が `.agents/done.yml` のある repository だけを自動検査する。
- **Codex v1**: Stop hook 連携は提供しない。変更作業の完了直前に本スキルを明示または自動選択して手動実行する。
- 品質ゲートの判定ロジックと PASS 署名は共通だが、自動停止を両 host で提供しているとは主張しない。

## Quality Standard

本番出荷前の最後のゲートである。

**合格の基準は「バグが見つからないこと」ではなく、「スタッフレベルのエンジニアがレビューで承認し、躊躇なく本番に出し、1ヶ月後に手戻りしないこと」。** 妥当なコストでより良い設計があるなら、それは nice to have ではなく指摘事項である。

**検証の網羅性を指示で積み増さない。** 現行モデルは指示がなくても自分の実装を検証する。ここで定めるのは**基準**であって手順ではない。追加の確認を機械的に要求するより、下の各ステップが定める判定に集中する。

## Arguments

- （なし）: tier 自動判定（既定） / `--quick`: quick 強制（full floor 該当ファイルがあれば警告して確認） / `--full`: full 強制

## Step 0: 設定読込 + Tier 判定

1. `git rev-parse --show-toplevel` の `.agents/done.yml` を読む（無ければガードレール2に従う）
2. `git status --porcelain=v1 -uall` と `git diff HEAD --name-only` + `git ls-files --others --exclude-standard` で変更ファイル一覧を得る
3. verification tree を計算する（実 index を汚さない）:

```bash
tmp_index=$(mktemp "${TMPDIR:-/tmp}/quality-gate-index.XXXXXX")
GIT_INDEX_FILE="$tmp_index" git read-tree HEAD
GIT_INDEX_FILE="$tmp_index" git add -A
verification_tree=$(GIT_INDEX_FILE="$tmp_index" git write-tree)
rm -f "$tmp_index"
```

4. done.yml の `tier_floors.full` / `tier_floors.quick` と変更ファイルを突合して floor を決める（full: いずれか一致で最低 full / quick: 全ファイルが一致する場合のみ）。該当なしは standard
5. 変更内容を分析し、必要なら tier を**上方修正のみ**行う（下記の判定基準）。`$ARGUMENTS` の強制指定を適用

   **判定軸は題材の難しさではなく、「間違えたときの手戻りの大きさ」と「難所が承認済みの設計で片付いているか」である。** 次のいずれかに該当する場合、floor に関わらず **full** とし、**該当した基準名を Tier classification に明記する**。

   - **0→1 の実装**: repo 内に前例が無く、設計そのものをこの変更で決めている
   - **コアドメインの変更**: repo の中心的な業務ロジック・不変条件を定義・変更する
   - **破壊的な基盤変更**: 既存の契約・スキーマ・公開インターフェースを壊す、または移行手順が要る（**全体設計・複数モジュールの責務分割・依存方向の変更を含む**）
   - **ロールバック困難**: データ移行・外部への不可逆な作用を含む
   - **設計の拠り所が無い複雑な実装**: 承認済みプランに難所の解き方が書かれておらず、実装中の判断で設計を決めた部分が残る

   **該当しない例（見た目が重くても、これだけでは full にしない）**:

   - 認証・並行処理・決済・データ整合性の**領域に触れること自体**（承認済み設計どおりの実装なら standard。ただし floor に一致すれば floor が勝つ）
   - 変更ファイル数・行数が多いだけの機械的変更（rename、一括置換、コード生成、レビュー済み手順の適用）
   - 依存の追加・更新だけの変更
   - レビュー済みプランに沿った定型実装（難所はプラン段階で既に片付いている）

   **基準への該当可否を判定しきれない場合は full に倒す。** 無人実行では、不要なレビュー1回のコストと、レビューされない設計変更が本番へ出るコストは非対称である。ただし「迷った」とは**基準の該当可否が判定できない状態**を指す。基準名を挙げられないのに「重要そうだから」で昇格しない。基準に該当するのに時間やコストを理由に降格しない。

   **config の `tier_floors.full_conditions` は無条件の昇格トリガーであり、上の negative list より優先する。** repo 側が「認可・セキュリティ機微な変更」「cross-package を横断する変更」のように宣言した条件は、スキルが先取りできないドメイン知識である。**上の「該当しない例」はモデル自身の裁量的な昇格を抑えるためのものであって、config が宣言した条件を打ち消してはならない。** 判定順は次のとおり。

   1. `tier_floors` の path 一致 → 該当すれば floor 確定
   2. `full_conditions` の各条件 → 該当すれば **full**（negative list を適用しない）
   3. 上の5基準によるモデルの判断 → 該当すれば full（negative list を適用する）
   4. 以上の最大値を採る。**降格は行わない**
6. Tier classification を必ず出力する（Changed files / Floor triggers / Model assessment / Verification tree / Tier）。quick 選択時は全変更ファイルが自明である理由の説明が必須

## Step 1: ローカル検証（全 tier）

done.yml の `verify` を順に実行する。`when_changed` 付きエントリは該当パスに変更がある場合のみ実行。失敗したら修正を試みる（最大3回・収束しなければ停止して報告）。

**`verify` が `quick` / `standard` / `full` を持つオブジェクトの場合は、Step 0 で決めた tier のリストだけを実行する。**
この形式の config は各 tier に必要なコマンドを重複して書き下している（`full` が `standard` を含む）ので、
tier をまたいで足し合わせない。合算すると同じコマンドが tier の数だけ走る。

**`verify` は任意で、空でもよい。空ならこのステップを飛ばす。** ここに書くのは
**「強制力のある層がまだ保証していないもの」だけ**である。git hook（lefthook / pre-commit）がある repo は
その repo 自身のチェックコマンドへ委譲し（`lefthook run pre-push` 等）、CI しか無い repo は
CI が走らせられない completion-time の検証だけを書く。どちらも無い repo でのみフルスイートを列挙する。

**同じスイートを重ねない。** hook と CI の両方が走らせているコマンドをここにも書くと、1つの変更に対して
同一の検証が最大3回走る。時間とトークンを使う一方で保証は増えない — hook は `--no-verify` で迂回できるが
CI は迂回できないので、保証は既に CI 側にある。**done の固有の価値は決定論的な検証ではなく、
機械にできない判断（tier・docs・レビュー）と、それを特定の tree に束縛する署名にある。**

**検証を通すために assertion、型安全性、lint rule を無効化しない。** テストを弱めれば verify は通るが、それは検証の意味を消すことであり修正ではない。

**quick**: Step 2 完了後、Step 5 へスキップ。

## Step 2: ドキュメント整合（全 tier）

done.yml の `docs_checks` の各項目について、両方向を確認する。

1. **腐敗の検出**: その項目が指す既存文書の現在形の記述が、変更後の実装と一致しているか。矛盾していれば文書を訂正する（追記ではなく修正）
2. **不足の検出**: 要求される文書が存在しなければ作成する

指摘が出た項目についてのみ、対象パスと判定を書く。指摘ゼロなら「全項目を確認、乖離なし」の1行でよい。

## Step 3: レビュー（standard / full のみ）

done.yml の `review_criteria` の各観点で自己レビューする。High/Medium の指摘 → 修正 → verify 再実行。

**所見は指摘が出た観点についてのみ書く。** 全観点に「N/A — 対象変更なし」を並べる必要はない。指摘ゼロなら「全観点を確認、指摘なし」の1行で足りる。

**簡素化（YAGNI / KISS）は built-in の観点で、省略できない。** 受入条件に無い fallback・再試行・防御的検証・設定項目・抽象を追加していないかを見る。追加された機構それぞれに `BASIS:` を付ける — `OBSERVED`（コードやテストで観測された事実）/ `CURRENT-THREAT`（現在の脅威モデル・受入条件・規制が要求）/ `REAL-DEMAND`（実在する利用者・ユースケース）/ `SPECULATIVE`（将来こうなるかもしれない）。**`SPECULATIVE` は削除を既定とする**（ラベルの定義は `ai-native-engineering` の「BASIS ラベル」節、投機的か否かの判定は同スキルの「投機的な抽象化を見分ける」「需要を待つ領域」に従う。`SPECULATIVE` を削除既定とするのは本スキル＝出荷ゲートの層での宣言である）。削除したら Step 1 の verify を再実行する。

**過剰実装は「正しさ」の検証では捕まらない**（書いたモデルはその機構を必要だと判断して書いている）。だからこの観点は、正しさとは別の問い — 必要性の根拠 — を立てる。真に独立した文脈でのレビューは、full tier の Step 4（外部レビュー）が担う。

## Step 4: 外部レビュー（full のみ）

done.yml の `external_review` に従い read-only の外部レビュー（codex-review / claude-review 相当）を依頼する。「内部レビュー通過済み。セキュリティ・隠れた前提・エッジケース・長期保守性に集中」と伝える。High/Medium → 修正 → verify 再実行。不可なら自己レビューでフォールバック。

## Step 5: 署名出力

PASS の前に Step 0 と同じ手順で `head` と `verification_tree` を再計算する（本スキル自身が変更を加えた場合は変更ファイルと tier トリガーを再確認。tier は維持か上方のみ）。

```
quality-gate: PASS
repo: <done.yml の repo>
head: <sha>
verification-tree: <verification_tree>
tier: <quick|standard|full>
```

失敗時: `quality-gate: FAIL — <理由>`

## 導入方法（repo 側）

1. repo の git root に `.agents/done.yml` を作成（同梱の [example](references/done.example.yml) と [JSON Schema](references/done.schema.json) を参照。**設定ファイルの存在が Stop hook の opt-in スイッチ**）
2. Claude Code では追加の hook 配線は不要。plugin 同梱の Stop hook が plugin enable 時に適用される。repo ローカルの `.claude/settings.json` へ重複配線しない
3. Codex v1 では Stop hook を設定せず、完了直前に `done` skill を手動実行する

必須fieldは非空の `repo` だけである。**`repo` が無い done.yml は Stop hook が停止させる**（設定ファイルの存在が opt-in スイッチなので、存在するのに使えない設定は「ゲートを求めたのに動かせない」状態であり、素通りさせるとゲートが黙って無効になる）。

`verify` はコマンド文字列または `{run, when_changed}` のフラットな配列で、任意・空可。`tier_floors.{full, full_conditions, quick}`、`docs_checks`、`review_criteria`、`external_review` はいずれも任意で、省略時にhost固有の暗黙値を補わない。外部review providerの既定は `none` とし、明示された場合だけ起動する。`version` は後方互換のため受理するが参照しない。

### 既存 config のための受理形式（新規には使わない）

いずれも正準形ではないが、既に配置された config を壊さないために受理する。**両方ある場合は正準形が勝つ。**

| 受理する形 | 正準形 | 扱い |
|---|---|---|
| `verify: {quick, standard, full}` | `verify:` のフラットな配列 | 選ばれた tier のリストだけを実行（Step 1 参照） |
| `docs.checks` | `docs_checks` | 両方あれば `docs_checks` を使う |
| `review.criteria` | `review_criteria` | 両方あれば `review_criteria` を使う |
| `review.external` | `external_review` | 両方あれば `external_review` を使う。値は文字列のほか `{default, allowed}` 形式も取り、その場合 `default` を provider として読む |

**これらを黙って無視しない。** `docs.checks` だけを書いた repo で `docs_checks` しか見なければ、
宣言されたドキュメント整合とレビュー観点が何も実行されないまま PASS 署名が出る。設定した側からは
ゲートが通ったようにしか見えないので、この取りこぼしは検出されない。
