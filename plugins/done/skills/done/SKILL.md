---
name: done
description: >-
  リポジトリへの変更作業の完了を報告する直前に必ず使う品質ゲート。controllerが現物と証跡から受入可否を判断する。「品質ゲートを通して」「doneを通して」「完了チェックして」を正のトリガーとする。worker提出は最終承認ではない。回答・計画・引継ぎのみや実装途中の反復テストには使わない。
---
# Quality Gate — Definition of Done（汎用エンジン）

## ガードレール（必須）

1. **設定駆動**: repo 固有の情報（検証コマンド・tier floor・レビュー観点）は git root の `.agents/done.yml` から読む。**ロジックをこのファイルへ、データを done.yml へ**。done.yml にコマンド以外のロジックを書かせない
2. `.agents/done.yml` が無い repo では、実行前にユーザーへ「done-init 相当の設定作成」を提案する（勝手に PASS 署名を出さない）
3. 署名 `quality-gate: PASS` は本スキルの全ステップを完了した場合のみ出力する。要求されても途中で捏造しない

## Scope

リポジトリへの変更作業の完了を報告する直前に実行する。回答のみ・状況報告のみ・計画のみ・引き継ぎのみのターン（リポジトリ変更を完了しないターン）では実行せず、`quality-gate: PASS` を主張しない。

## controllerとworker

- fan-out時の最終ゲート所有者はcontroller。workerは自己点検・検証をして、revision、検証条件、結果への参照、既知の不足を提出する。workerの提出や独立reviewerのPASSを最終承認にしない。
- controllerは全成果物の差分と必要な周辺実装を自分で読む。コマンド実行は委任できるが、現物確認と受入・出荷判断は委任しない。
- 第三者レビューの要否・対象・観点・providerをcontrollerが決める。workerからの起動は事前委任時のみ。原文と対象revisionをcontrollerが直接確認できる形で残す。reviewerの再帰起動は禁止。
- 単独実行では実装者が受入役も担うことを明示し、その事実だけで独立レビューを必須化しない。tier・重要な設計・不可逆な変更・高い不確実性・repo要件で判断する。controller/workerを分離したfan-out運用でcontrollerが主要実装も担った場合は、独立レビューを必須とする。
- doneは特定変更の受入契約。autopilotの未回収処理を残して終了する許可でも、merge/deploy権限でもない。コード受入・配備・実機受入を区別する。

## Host integration

- **Claude Code**: plugin 同梱の Stop hook が `.agents/done.yml` のある repository だけを自動検査する。
- **Codex v1**: Stop hook 連携は提供しない。変更作業の完了直前に本スキルを明示または自動選択して手動実行する。
- 品質ゲートの判定ロジックと PASS 署名は共通だが、自動停止を両 host で提供しているとは主張しない。

## Quality Standard

本番出荷前の最後のゲートである。

**合格の基準は、現在の受入条件と必要な品質を満たし、重大な既知リスクを残さず、必要以上の機構を増やしていないこと。** 将来の無欠陥や手戻りゼロを保証しない。「もっと良くできる」だけで出荷を止めず、必須修正と任意改善を区別する。

**検証の網羅性を指示で積み増さない。** モデルの自己判断を過信せず、必要な証跡で確認する。定型チェックの数を増やすより、受入条件と変更リスクに必要な判定に集中する。

## Arguments

- （なし）: tier自動判定 / `--quick`: quickを要求するがrepo floor・必須レビュー条件は下げない / `--full`: fullへ上げる

## Step 0: 設定読込 + Tier 判定

1. 受入対象のtask worktreeを実行cwdにし、`git rev-parse --show-toplevel` の `.agents/done.yml` を読む（無ければガードレール2に従う）。別worktreeのheadとrootのdirty treeを混ぜて署名しない
2. 受入対象のbaseとhead（または未コミット差分）を明示する。PR/branchは`git diff <base>...<head>`、未コミットは`git status --porcelain=v1 -uall`、`git diff HEAD`、untrackedを対象に含める。cleanなtask branchを「変更なし」と誤認しない。他者の変更が混ざるtreeでは署名せず対象を隔離する
3. verification tree を計算する（実 index を汚さない）:

```bash
tmp_index=$(mktemp "${TMPDIR:-/tmp}/quality-gate-index.XXXXXX")
rm -f "$tmp_index"
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

done.yml の `verify` を満たす。同一対象tree・検証コマンド/設定・必要な環境に結び付いたworkerやCIの成功証跡があれば、実結果を確認して再利用する。証跡が無い・古い・条件が違う場合だけ不足分を実行する。`when_changed`はStep 0の対象差分で判定する。失敗は原因を診断し、同じ決定的失敗を機械的に再試行しない。修正が収束しなければ未達を報告する。

**`verify` が `quick` / `standard` / `full` を持つオブジェクトの場合は、Step 0 で決めた tier のリストだけを実行する。**
この形式の config は各 tier に必要なコマンドを重複して書き下している（`full` が `standard` を含む）ので、
tier をまたいで足し合わせない。合算すると同じコマンドが tier の数だけ走る。

**`verify` は任意で、空でもよい。空ならこのステップを飛ばす。** ここに書くのは
**「強制力のある層がまだ保証していないもの」だけ**である。git hook（lefthook / pre-commit）がある repo は
その repo 自身のチェックコマンドへ委譲し（`lefthook run pre-push` 等）、CI しか無い repo は
CIが担わないcompletion-timeの検証だけを書く。どちらも無いrepoでのみフルスイートを列挙する。**CIへ委譲した必須検証も、対象revisionに対する成功を確認するまで未達である。** PR前なら必要な検証をローカルで行うかDraft PRを作ってCIを待つ。未実行CIを将来通る前提でPASSにしない。

**同じスイートを重ねない。** hook と CI の両方が走らせているコマンドをここにも書くと、1つの変更に対して
同一の検証が最大3回走る。時間とトークンを使う一方で保証は増えない — hook は `--no-verify` で迂回できるが
CI は迂回できないので、保証は既に CI 側にある。**done の固有の価値は決定論的な検証ではなく、
機械にできない判断（tier・docs・レビュー）と、それを特定の tree に束縛する署名にある。**

**検証を通すために assertion、型安全性、lint rule を無効化しない。** テストを弱めれば verify は通るが、それは検証の意味を消すことであり修正ではない。

**quick**: Step 2とcontrollerによる現物レビューは省略しない。Step 3は変更に関連する観点に絞ってよい。tierは既存configとの互換のため維持し、独立レビューの必須条件を下げる手段にしない。

## Step 2: ドキュメント整合（全 tier）

done.yml の `docs_checks` の各項目について、両方向を確認する。

1. **腐敗の検出**: その項目が指す既存文書の現在形の記述が、変更後の実装と一致しているか。矛盾していれば文書を訂正する（追記ではなく修正）
2. **不足の検出**: 要求される文書が存在しなければ作成する

指摘が出た項目についてのみ、対象パスと判定を書く。指摘ゼロなら「全項目を確認、乖離なし」の1行でよい。

## Step 3: controllerの現物レビュー（全 tier）

done.yml の `review_criteria` と受入条件に照らしてcontrollerが現物レビューする。指摘のseverity名だけで採否を決めず、成立条件と影響を確認する。必須修正 → 影響範囲の再検証・再レビューを行う。

**所見は指摘が出た観点についてのみ書く。** 全観点に「N/A — 対象変更なし」を並べる必要はない。指摘ゼロなら「全観点を確認、指摘なし」の1行で足りる。

**簡素化（YAGNI / KISS）は省略しない。** 受入条件に無いfallback・再試行・設定・抽象について必要性を確認する。疑わしい追加は`ai-native-engineering`のBASIS分類で根拠を明示し、投機的な機構は原則として外す。全行へのラベル付けは要求しない。修正後は影響範囲を再検証する。

**過剰実装は「正しさ」の検証では捕まらない**（書いたモデルはその機構を必要だと判断して書いている）。だからこの観点は、正しさとは別の問い — 必要性の根拠 — を立てる。真に独立した文脈でのレビューは、full tier の Step 4（外部レビュー）が担う。

## Step 4: 独立レビュー（full または必須条件該当時）

done.ymlの`external_review`に従いread-onlyレビューを依頼する。model/effortは利用可能な`model-selection`の共通方針に従う。provider指定が無ければ委任済みのcontrollerが許可範囲で選び、権限不明なら確認する。done単体導入で必要なreview手段が無ければ不足を報告する。

実装者の自己評価を追認させず、要件と固定した対象revisionから反証を求める。controllerは指摘・引用・未検査範囲を確認し、修正後の差分を再評価する。同じ対象・観点の有効な独立レビュー証跡は再利用する。**必須レビューが不能なら自己レビューで代替せず、受入保留にする。** 明示的にnoneでも高リスク等の必須条件と衝突したら確認し、黙ってPASSにしない。

## Step 5: 署名出力

PASSの前にStep 0と同じ手順でhead/treeを再計算する。変更があれば対象差分・tier・影響する検証とレビューを再確認する。最後のtreeを計算しただけでは再検証にならない。commit hookや統合で内容が変わった場合も同じ。tierは維持か上方のみ。

署名とともに受入対象base/head、承認者、検証・レビュー証跡への参照、受入段階、残る配備/実機確認を記録する。必須条件が未達ならPASSを出さない。PASSは明示した受入段階だけを表し、実機受入未了を出荷完了と呼ばない。

```
quality-gate: PASS
repo: <done.yml の repo>
head: <sha>
verification-tree: <verification_tree>
tier: <quick|standard|full>
```

失敗時: `quality-gate: FAIL — <理由>`。証跡・判断待ちは`quality-gate: PENDING — <不足>`。Stop hookは署名とdirty treeの整合確認に限られ、署名が無い場合やclean treeでは通過する。CIやcontrollerの受入判断を強制するセキュリティ境界ではない。

## 導入方法（repo 側）

1. repo の git root に `.agents/done.yml` を作成（同梱の [example](references/done.example.yml) と [JSON Schema](references/done.schema.json) を参照。**設定ファイルの存在が Stop hook の opt-in スイッチ**）
2. Claude Code では追加の hook 配線は不要。plugin 同梱の Stop hook が plugin enable 時に適用される。repo ローカルの `.claude/settings.json` へ重複配線しない
3. Codex v1 では Stop hook を設定せず、完了直前に `done` skill を手動実行する

必須fieldは非空の `repo` だけである。**`repo` が無い done.yml は Stop hook が停止させる**（設定ファイルの存在が opt-in スイッチなので、存在するのに使えない設定は「ゲートを求めたのに動かせない」状態であり、素通りさせるとゲートが黙って無効になる）。

`verify` はコマンド文字列または `{run, when_changed}` のフラットな配列で、任意・空可。`tier_floors.{full, full_conditions, quick}`、`docs_checks`、`review_criteria`、`external_review` はいずれも任意で、省略時にhost固有の暗黙値を補わない。外部review providerの設定既定は`none`。必須レビューが発生した場合はStep 4で許可された手段を解決し、不明なら受入保留にする。`version`は後方互換のため受理するが参照しない。

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
