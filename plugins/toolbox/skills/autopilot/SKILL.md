---
name: autopilot
description: >-
  複数タスクを選択から実装、検証、リリースまで順番に自律処理する。バックログを無人で継続消化する明示依頼に使う。単発タスクには使わない。「自律で進めて」「バックログを全部消化して」を正のトリガーとし、人の判断待ちが必要な単発実装には通常の実装フローを使う。
---
# autopilot — 自律開発オーケストレータ

## Core Principle（絶対に変えてはいけない原則）

**このスキルは薄いオーケストレータである。** ループ制御・ゲート管理・エスカレーションのみを
自前実装し、重い処理は**拡張点（役割）**に委譲する。委譲先の内部実装には踏み込まない。

### 拡張点と解決順

各拡張点は「① repo config（`.agents/autopilot.json`）の明示指定 → ② プロジェクトの同役割スキル → ③ 既定」の順で解決する。
**名前の完全一致でなく役割で解決する**（plugin 配布下では `toolbox:codex-review` のように namespace 付きで見える）。

| 拡張点 | 役割 | 既定（③） |
|--------|------|-----------|
| **ship-gate** | 実装後の検証・出荷ゲート。`quality-gate: PASS` 署名の確認だけ行い内部に踏み込まない | done スキル（done plugin）+ repo の `.agents/done.yml`。done.yml が無い repo では PASS 署名を要求せず、config の verify コマンド or 会話で代替ゲートを確認 |
| **reviewer** | プランの第三者レビュー（逆エンジン） | claude 上→codex-review / codex 上→claude-review / cursor 上→codex-review。使えない場合は使える方 |
| **e2e** | UI/E2E 検証の安全方針 | e2e-capability-verification（browser tool の選択は browser-operations の優先順位に従う） |
| **reporter** | 進捗・引き継ぎレポート | progress-report |

### 破壊的操作の確認境界（拡張点と独立の不変ルール）

自律ループ中でも、以下は **config の `gates` 設定が明示的に許可した場合のみ**自動実行する。
**未設定時の既定は「人間ゲート」**（PR 作成までは自律・その先は停止してエスカレーション）:

- `gates.merge`（PR の merge）/ `gates.deploy`（本番・staging への deploy）
- 常に人間確認（config でも解除不可）: **worktree/ブランチの削除で未コミット変更が消えるもの・データベースやユーザーデータの削除・force push**

「止まらず進めて」等の会話指示は当該セッション内でのみ gates を緩め、config には書き戻さない。

**「無人で継続消化する」ことと「merge を既定で止める」ことは矛盾しない。** 無人化の対象は
タスクの選択・実装・検証・PR 作成という反復作業であって、出荷の判断ではない。ここを既定 `auto` にすると、
`gates` を書いていない repo — つまり運用方針をまだ決めていない repo — が最初の run から無人マージを始める。
**明示的に `auto` と書いた repo だけが自動マージされる**のが、配布される plugin の既定として正しい。
この既定を「スキルの目的と矛盾している」と読んで緩めない。

## マルチテナント安全性（最優先・絶対不変条件）

複数の組織・顧客・repository間で設定や成果物が混入すると、tenant境界を越える情報漏洩に直結する。

1. **設定は常に「今いる repo」の `.agents/autopilot.json` からのみ解決する。**
   前セッション・他repoの値を記憶/流用しない。configが無い・曖昧なら推測せず停止する。

2. **全書き込み操作の前に `repo` 同一性ガードを実行する（後述 Preflight 参照）。**
   不一致なら全書き込みを拒否して即停止する。

3. **`gh` 書き込みコマンドは必ず config 由来の `--repo`/`--owner` を明示する。**
   グローバル既定やカレントディレクトリ推測に依存しない。

4. **レポート・記録はカレントrepo内に閉じる。** 複数repoの結果を1か所に集約しない。

## Preflight（起動時に必ず実行）

```bash
<skill-dir>/scripts/autopilot_board.py preflight
```

このコマンドは次を検証し、いずれか満たさなければ**非ゼロで終了する。終了したら書き込みを一切行わない。**

- `.agents/autopilot.json` が存在し、`repo` を持つ
- **`gh repo view` で見た実際の repo が config の `repo` と一致する**（不一致は tenant 境界越え。最優先の不変条件）
- `gates.merge` が `auto` のとき、base ブランチの branch protection が実際に無人 merge を止められるか
  （required status checks がある / `enforce_admins` が有効 / force push が禁止）を確認する。
  **止められないなら human ゲートへ降格し、理由を `notes` に載せて実行は続ける。**
  ここで run ごと拒否すると、タスク側では直しようのない repo 設定のためにバックログ全体が止まる。
  降格後の挙動は「gates 未設定」と同じ（PR 作成まで自律・その先は人間）。

**出力（JSON）が以降で使う値の唯一の定義元である。** 各フィールドを次の変数へ取り、
以降のステップはこれらだけを参照する（config を再度読み直さない）。

```bash
PREFLIGHT=$(<skill-dir>/scripts/autopilot_board.py preflight) || exit 1
EXPECTED_REPO=$(echo "$PREFLIGHT" | jq -r '.repo')
BASE_BRANCH=$(echo "$PREFLIGHT" | jq -r '.baseBranch')
MERGE_GATE=$(echo "$PREFLIGHT" | jq -r '.mergeGate')   # "auto" または "human" に正規化済み
DEPLOY_GATE=$(echo "$PREFLIGHT" | jq -r '.deployGate')
```

加えて、後続で使う実行環境を判定する。

- `run_in_background` 可否: Claude Code 上なら可、`codex exec` 内なら不可（foreground のみ）
- browser tool 可否: browser-operations の優先順位（CLI → MCP）で利用可能な手段を確認。staging MCP の可否もここで確認する

## Per-task Loop

**1タスクを終端状態（Done または escalated-skip）にしてから次を取得する（直列・再開可能）。**
再起動時に In Progress のタスクが既にある場合は**再開扱い**（二重着手しない）。

---

### Step 0: タスク源の確認と次タスク選択

config の `taskSource.mode` に従う:

#### `github-projects` モード

```bash
NEXT=$(<skill-dir>/scripts/autopilot_board.py next-task) || exit 1
```

Project / field / option の id を実行時に解決し、**In Progress のタスクがあればそれを再開**、無ければ
config の `pickFrom` の順序（先頭が最優先）で次のタスクを選んで In Progress へ移す。
出力の `task` が `null` なら対象なしなので正常終了する。それ以外は**出力が以降で使う値の唯一の定義元**である。

```bash
TASK=$(echo "$NEXT" | jq -r '.task')
[[ "$TASK" == "null" ]] && { echo "INFO: 対象タスクなし。"; exit 0; }
ITEM_ID=$(echo "$TASK" | jq -r '.itemId')
PROJECT_ID=$(echo "$TASK" | jq -r '.projectId')
TASK_TITLE=$(echo "$TASK" | jq -r '.title')
ISSUE_URL=$(echo "$TASK" | jq -r '.issueUrl // empty')
ISSUE_NUMBER=$(echo "$TASK" | jq -r '.issueNumber // empty')
BRANCH=$(echo "$TASK" | jq -r '.branch')
RESUMED=$(echo "$TASK" | jq -r '.resumed')
```

**id を config にハードコードしない。** Project の構成は変わるので、毎回解決する。

**この run で escalated-skip したタスクは `--exclude <itemId>` で除外する（複数可）。**
escalated-skip した item は In Progress のまま残るため、除外しないと次の反復で再開対象として
毎回同じものを掴み、**1件の詰まりがボード全体を止める**。

#### `plan-doc` モード

config の `taskSource.planDoc.path` を読み、未チェック（`- [ ]`）の先頭項目を次タスクとする。
完了時にチェックマーク（`- [x]`）に書き換える。

`issueQuery` が設定されている場合は、その値を検索式として `gh issue list --repo "$EXPECTED_REPO" --search <issueQuery>` で取得する。

#### `none` モード

タスク源なし。現在の会話コンテキスト・ユーザー指示を直接使う。

---

### Step 1: feature ブランチ作成

ブランチ名は Step 0 の出力（`branch`）を使う。非ASCII タイトルは Issue 番号へフォールバック済み。
**plan-doc / none モードでは board を経由しないので、同じ規則を次で得る。**

```bash
BRANCH=$(<skill-dir>/scripts/autopilot_board.py branch-name \
  --title "$TASK_TITLE" --issue-number "$ISSUE_NUMBER" | jq -r '.branch')
```

```bash
# 着手前に作業ツリーが clean であることを必須にする。
# dirty のまま次タスクへ進むと、前タスクの未コミット変更はブランチをまたいで持ち越され、
# そのタスクの commit に巻き込まれて別タスクの PR として出荷される。
[[ -z "$(git status --porcelain)" ]] || {
  echo "ERROR: 作業ツリーが dirty です。前タスクの後始末が完了していません。"; exit 1
}

git fetch -q origin "$BASE_BRANCH"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout "$BRANCH"          # 再開時は既存ブランチをそのまま使う
else
  # 新規は必ず最新の base から分岐する。現在の HEAD から切ると、前タスクのローカル commit が
  # 次タスクの PR 差分へ混入する（squash merge 運用で顕在化する）。
  git checkout -b "$BRANCH" "origin/$BASE_BRANCH"
fi
```

**main/master への直コミットは絶対にしない。**

---

### Step 2: プランニング

実装前にプランを作成し出力する。

- **github-projects モード**: Issueのコメントとして出力（`gh issue comment "$ISSUE_URL" --repo "$EXPECTED_REPO" --body "..."`)。
- **plan-doc / none モード**: 会話に出力し確認を求める。

---

### Step 3: プランレビュー（逆エンジン）

逆エンジンの review スキルを使い、プランの妥当性を確認してもらう。
**通過するまで最大3回反復**。3回で収束しなければエスカレーション。

- claude 上 → codex-review スキル（`toolbox:codex-review`）を呼ぶ（Step 2 で作成したプランを会話コンテキストとして渡す）
- codex 上 → claude-review スキル（`toolbox:claude-review`）を呼ぶ（同上）

リポジトリ規約では provider 未指定の第三者レビューはユーザーへ確認するが、無人実行では確認プロンプトを
出せないため、host の逆エンジンを既定とする明示的な例外である。ユーザーまたは config が provider を
明示した場合はそれに従う。

---

### Step 4: 実装

現在のhostが読み込んだrepository instructions（`AGENTS.md`、`CLAUDE.md`等）の開発原則を厳守して実装する。
- 既存コード・ユーティリティを必ず調べて再利用する
- 設計・アプローチに迷ったら実装前に会話に提示し確認する
- 品質に妥協しない
- **受入条件・承認済みプランに無い機構を足さない。** fallback・再試行・防御的検証・設定項目・抽象は、
  いま観測されている要求に対してだけ書く。「将来必要になりそう」は書かない理由である

**実装が終わったら、Step 5 の前に commit する。** 順序が逆だと検証したツリーと出荷されるツリーが食い違う。
pre-commit hook にフォーマッタを置く構成（`biome check --write` や `stage_fixed` など）は珍しくなく、
その場合 commit の瞬間にファイル内容が変わる。**done を先に走らせると、署名した `verification-tree` と
実際に commit された内容がずれる。しかも作業ツリーが clean なら Stop hook は検査しないので、
このずれは誰にも検出されない。** 先に commit すれば hook の書き換えは検証より前に済み、
検証したツリー = push されるツリーが成立する。

---

### Step 5: 実装後ゲート（done Skill）

現在のhostで `done` Skillを明示的に実行し、**出力末尾の `quality-gate: PASS` 署名のみを成功判定の根拠**とする。
`done` の内部（tier 判定・検証ステップ）には一切踏み込まない。

`quality-gate: PASS` が出なければ `done` の指示に従い修正 → 再実行（最大3回）。
3回収束しなければ該当タスクをエスカレーション・スキップして次へ。

**PASS 後、`done` 自身が加えた修正が未コミットで残っていれば commit し、
`git rev-parse 'HEAD^{tree}'` が署名の `verification-tree` と一致することを確認してから Step 6 へ進む。**
一致しなければ pre-commit hook が内容を書き換えているので、その状態で `done` を再実行する。
未コミットのまま push すると `done` の修正はそもそも出荷されない。

UI 変更がある場合は `e2e-capability-verification` スキルの方針に従い動作確認を行う
（browser tool の選択も同スキルと `browser-operations` の優先順位に委譲する）。
browser-operations の優先順位で利用可能な browser tool が無い環境では理由をメモしてスキップ。

---

### Step 6: PR 作成 → board を In Review へ

```bash
# ブランチを push（未 push だと gh pr create が対話プロンプトで止まるため先に実行）
# pre-push hook がある repo では、ここで hook が走る。失敗は verify 失敗と同じ扱いで
# 修正 → 再試行（最大3回）。3回収束しなければエスカレーション・スキップ。
git push --set-upstream origin "$BRANCH"

# PR 作成（BASE_BRANCH は Preflight で解決済み）
PR_URL=$(gh pr create \
  --repo "$EXPECTED_REPO" \
  --title "$TASK_TITLE" \
  --body "<プランと変更点の要約>" \
  --base "$BASE_BRANCH")

# board の Status を In Review へ（github-projects モード）
<skill-dir>/scripts/autopilot_board.py set-status \
  --project-id "$PROJECT_ID" --item-id "$ITEM_ID" --status "In Review"
```

---

### Step 7: CI 監視

```bash
# ブロッキングで CI が緑になるまで待つ（PR 紐付きの checks を監視）
# --fail-fast: いずれかのチェックが失敗したら即終了（無駄な待機を排除）
# --exit-status / --interval は gh version により異なるため、失敗時は gh run list で状況確認
gh pr checks "$PR_URL" --repo "$EXPECTED_REPO" --watch --fail-fast
```

Claude Code 上では `run_in_background: true` で起動し、完了通知を待つことも可。
タイムアウト（既定 30 分）を超えたらエスカレーションし、スキップして次へ。
CI が赤で終わった場合は 3 回リトライしてから escalated-skip へ。

---

### Step 8: Merge（明示許可時のみ）

**`gates.merge` が `auto` でも、差分が品質ゲートの定義そのものを含む場合は自動 merge しない。**
対象は `.agents/**`（`done.yml` / `autopilot.json`）と CI 設定（`.github/workflows/**` 等）。
これらは以降のすべての実行を守っているルールなので、緩める変更が無人で通ると次回以降の全タスクに波及する。
該当する場合は人間の確認へ回す（ゲートを緩めても実装が正しくなるわけではない）。

`gates.merge` が `auto`（文字列）または `true`（真偽値）で、かつCIが緑の場合だけmergeする。未設定、`human`、その他の値（`"yes"`、`1`、`"Auto"` など）はすべて人間ゲートとして PR 作成後に停止する。
**曖昧なものは人間ゲートに倒す** — ここを緩く読むと、綴り間違い1つで無人マージが起きる。`gates.deploy` も同じfail-closed規則を適用する。
Step 7 で CI green を確認済みなので `--auto` は不要。merge戦略フラグは排他なので単一で指定する:

```bash
# MERGE_GATE は Preflight が正規化済み（"auto" | "human"）。ここで config を読み直さない
# — 読み直すと真偽値 true が "auto" と一致せず、Preflight と判断が食い違う。
[[ "$MERGE_GATE" == "auto" ]] || {
  echo "INFO: merge requires a human gate; stopping after PR creation."
  exit 0
}
gh pr merge "$PR_URL" --repo "$EXPECTED_REPO" --squash
```

---

### Step 9: デプロイ

`DEPLOY_GATE`（Preflight で正規化済み）が `auto` でなければ、ここで停止して人間へ返す。
`auto` のときだけ config の `deploy.steps` を**上から順に**実行する。`deploy.needed` が `false` なら省略。

各 step の `run` と `monitor` は **config に書かれたコマンドそのもの**である。
1つでも失敗したらその時点で停止し、以降の step を実行しない（部分適用のまま次タスクへ進まない）。

**config に生の `terraform apply` 等を書くことを禁止する。** deploy は `gh workflow run` のような
ラッパー経由にする。config への書き込み権限は、ここに書かれた任意コマンドの実行権限と等価である。

---

### Step 10: Staging 検証

config の `stagingVerify.method` に従う:

- `mcp`: config の `stagingVerify.mcpServer` に接続し、MCP ツールで staging 動作を確認する。
- `manual`: 自動検証不可。エスカレーション内容をメモして記録し、スキップ。
- `skip`: 検証なし（明示的スキップ）。

MCP が使えない環境・エンジンでは `method: mcp` でも理由をメモしてスキップ。

---

### Step 11: board を Done へ → 次タスクへ

```bash
<skill-dir>/scripts/autopilot_board.py set-status \
  --project-id "$PROJECT_ID" --item-id "$ITEM_ID" --status Done
```

plan-doc モードはチェックマーク（`- [x]`）に書き換える。次タスクへ。

---

## タスクを終える前の後始末（escalated-skip でも必須）

**次タスクへ移る前に、作業ツリーを必ず clean にする。** 失敗・スキップしたタスクの未コミット変更を
残したまま次へ進むと、ブランチを切り替えても変更は持ち越され、次タスクの commit がそれを巻き込む
（＝スキップしたはずのコードが別タスクの PR として出荷される）。

**未コミット変更を破棄してはならない。** 現在のブランチが当該タスクのブランチであることを確認したうえで、
WIP として commit して隔離する（push はしない）。

```bash
[[ "$(git symbolic-ref --quiet --short HEAD)" == "$BRANCH" ]] || {
  echo "ERROR: 想定外のブランチにいます。作業ツリーを触らず人間へエスカレーションします。"; exit 1
}
if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git commit -q -m "WIP: escalated-skip — $TASK_TITLE"
fi
```

失敗途中のコードは pre-commit hook を通らないことがある。**この WIP commit は出荷物ではないので、
hook で止まった場合は `--no-verify` を使ってよい。** それでも commit できなければ、作業ツリーを保持した
まま run 全体を停止して人間へ返す（次タスクへは進まない）。

作業は該当ブランチに保全され、作業ツリーは clean になり、次タスクが Step 1 の clean 検査を通れる。
ブランチ名を End-of-run レポートに残す。この WIP commit は「main への直コミットをしない」原則の対象外
ではなく、feature ブランチ上で完結し push も PR もされない。

---

## 差し込みタスク

途中でタスク追加が必要になった場合:
- **github-projects モード**: 利用可能な Issue 作成スキル、または
  `gh issue create --repo "$EXPECTED_REPO"` で作成後、Project に追加。
- 全体を俯瞰して着手順を整理しなおす。大きな変更なら逆エンジンレビューを通す。

---

## Stop Conditions（unattended 安全弁）

| レベル | 条件 | 動作 |
|--------|------|------|
| ゲート | 各ゲートで最大3回リトライ → 収束しない | エスカレーション記録 → タスクをスキップして次へ |
| タスク | タスク単位のエラー | 内容をメモ → スキップ → 次タスク |
| ループ | 残タスクゼロ / 連続2件失敗 / バジェット超過 | 統合レポートを出力して終了 |
| 緊急 | repo 同一性ガード失敗 / config 未発見 | **即停止（書き込みなし）** |

---

## Escalation

詰まったら逆エンジンの review スキルにヘルプ依頼する。
それでも解決しなければ、エスカレーション内容を Issue コメントまたは会話に記録してスキップする。

---

## End-of-run Report

ループ終了時に `progress-report` スキルを使い、以下を**1本のレポートに統合**して出力する:
- ✅ shipped: タスク名・PR URL・merge SHA
- ⏭️ skipped: タスク名・スキップ理由
- ⚠️ escalated: タスク名・詰まった箇所・次に取るべき手順

progress-report のテンプレート構造との対応: shipped/skipped/escalated の一覧は L2 全体マップの表として
載せ、escalated の要対応事項は L1 の「要対応・要判断」へ、各タスクの詳細は L3 詳細へ載せる。
複数のレポートを Issueコメントに散らさない。1本を朝に読める形で出力する。

### 蓄積した複雑度の点検（この run で2件以上 ship した場合のみ）

`done` の簡素化観点は**1タスクの差分**しか見ない。個々には妥当な小さい抽象でも、タスクをまたいで
積み上がると重複した機構が残る。これは差分単位のレビューでは原理的に捕まらないので、run の最後に一度だけ見る。

ship した各ブランチの累積差分（`git diff "origin/$BASE_BRANCH"...<branch>`）を通しで読み、次を挙げる:

- 同じ関心事に対して重複して増えた抽象・ユーティリティ
- タスクをまたいで残った `SPECULATIVE` な機構（ラベル定義は `ai-native-engineering` の「BASIS ラベル」節、処分の既定は `done` のレビュー観点に従う）
- 統合できる設定項目・分岐

**ここでは変更を加えない。** 広範囲のリファクタは受入条件を持たず、無人で走らせる対象ではない。
結果は「次に起票すべきタスク」の形でレポートに載せ、着手はユーザーの判断に委ねる。
指摘が無ければ「蓄積した複雑度の点検: 指摘なし」の1行でよい。

---

## Bootstrap（`.agents/autopilot.json` が存在しない場合）

repo の特徴を自動検出し、config の雛形を提案する（**実行はユーザー確認後**）:

1. `terraform` ディレクトリ or `Taskfile.yml` の存在 → infra repo と判定
2. `.github/workflows/` の内容 → デプロイワークフロー候補を列挙
3. `gh project list --owner <owner>` → リンク済み Project の候補を提示
4. 雛形を `.agents/autopilot.json` に出力し、中身を確認・編集するよう求める
5. unattended 運用前に必ずコミットするよう案内する

---

## 安全ルール（厳守）

- **`config.repo` と実際の repo が一致しない場合、一切の書き込みを行わない**
- **生の `terraform apply` をスキルが直接実行しない**（`gh workflow run` 等の config 記載コマンド経由）
- **`.agents/autopilot.json` のサンプル・説明文に実在の企業名・org名・IDを含めない**
- **`done` Skill の内部実装（tier/step）に依存しない。`quality-gate: PASS` 署名のみ見る**
- **main/master への直コミットをしない。必ず feature ブランチを切る**
- **前セッションの値・他repoの設定を流用しない。常に起動時に読み直す**
