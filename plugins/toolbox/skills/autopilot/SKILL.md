---
name: autopilot
description: >-
  複数タスクを選択から実装、検証、リリースまで順番に自律処理し、実装はワーカーへ委譲する。バックログを無人で継続消化する明示依頼に使う。単発タスクには使わない。「自律で進めて」「バックログを全部消化して」を正のトリガーとし、人の判断待ちが必要な単発実装には通常の実装フローを使う。
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
| **worker** | Step 4 の実装実行体。承認済みプランを受け取り実装する（commit も品質ゲートも実行しない） | `workers.engine`（未設定は `auto`）。`auto` は Claude Code 上で `claude-subagent`、それ以外で `codex-exec`、どちらも不可なら `none`（orchestrator 自身が実装） |
| **ship-gate** | 実装後の検証・出荷ゲート。`quality-gate: PASS` 署名の確認だけ行い内部に踏み込まない | done スキル（done plugin）+ repo の `.agents/done.yml`。done.yml が無い repo では PASS 署名を要求せず、config の verify コマンド or 会話で代替ゲートを確認 |
| **reviewer** | プランの第三者レビュー（逆エンジン） | claude 上→codex-review / codex 上→claude-review / cursor 上→codex-review。使えない場合は使える方 |
| **e2e** | UI/E2E 検証の安全方針 | e2e-capability-verification + Chrome DevTools / Playwright MCP |
| **reporter** | 進捗・引き継ぎレポート | progress-report |

### 実行モデル（orchestrator / worker）

**worker はコードを書くところまでを担い、それ以外はすべて orchestrator が担う。**

- **委譲は既定で有効。** `workers.engine` の既定は `auto`。タスクは従来どおり 1 件ずつ直列に処理する
- **worker のホストは orchestrator のホストと独立に選べる。** Claude Code から Codex worker を、Codex から Codex worker を起動できる
- **worker のモデルは 2 段。** 既定は低コスト側（`workers.model` + 低めの effort）だが、**やり直しコストが高い実装は `workers.escalatedModel`（フロンティアモデル）+ 高い effort へ昇格する**。昇格はプランを見た orchestrator の判定による
- **品質ゲート（Step 5 の done）は worker ではなく orchestrator が実行する。** 実装したモデルが自分の実装をレビューして自分で PASS 署名を出す構図を作らない。署名を後から検証しても「done が実際に走ったか」は確かめられないため、実行主体を信頼できる側に置くことが唯一の実効的な担保である
- **worker への禁止事項は原則として指示であって機構ではない。** sandbox が実際に効くのは `codex-exec` の `.git/` 書き込み禁止（＝ commit / branch 切替を阻む）と network 既定無効の 2 点だけで、MCP・hooks・`/tmp` への書き込みはその外側にある。orchestrator は起動前に baseline（HEAD・status・ブランチ）を取り、完了後に差分と外部書き込みの形跡を確認する

詳細（入出力契約・engine adapter・モデル昇格）は [worker-contract.md](references/worker-contract.md) に従う。

### 破壊的操作の確認境界（拡張点と独立の不変ルール）

自律ループ中でも、以下は **config の `gates` 設定が明示的に許可した場合のみ**自動実行する。
**未設定時の既定は「人間ゲート」**（PR 作成までは自律・その先は停止してエスカレーション）:

- `gates.merge`（PR の merge）/ `gates.deploy`（本番・staging への deploy）
- 常に人間確認（config でも解除不可）: **worktree/ブランチの削除で未コミット変更が消えるもの・データベースやユーザーデータの削除・force push**

「止まらず進めて」等の会話指示は当該セッション内でのみ gates を緩め、config には書き戻さない。

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
# 1. config 読み込み
CONFIG=$(cat .agents/autopilot.json 2>/dev/null) || {
  echo "ERROR: .agents/autopilot.json が見つかりません。"
  # unattended 運用（overnight 等）では config が無い限り書き込みを行わず即停止。
  # 対話セッションでのみ Bootstrap を提案する（「y/N」への回答が可能な場合）。
  echo "対話セッションの場合: bootstrap モードで config の雛形を生成しますか？（y/N）"
  # → y なら後述の Bootstrap を実行。n または unattended なら exit 1。
  exit 1
}

# 2. repo 同一性ガード（最重要: いかなる書き込み前に必ず実行）
EXPECTED_REPO=$(echo "$CONFIG" | jq -r '.repo')
ACTUAL_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null)
if [[ "$ACTUAL_REPO" != "$EXPECTED_REPO" ]]; then
  echo "ERROR: repo 不一致。書き込みを中断します。"
  echo "  config.repo = $EXPECTED_REPO"
  echo "  actual repo = $ACTUAL_REPO"
  echo "正しいディレクトリで起動しているか、.agents/autopilot.json を確認してください。"
  exit 1
fi

# 3. エンジン・MCP 可否の判定（後続で使う変数をセット）
# - run_in_background 可否: Claude Code 上なら可、codex exec 内なら不可（foreground のみ）
# - MCP 可否: Chrome DevTools / Playwright / staging MCP が利用可能か確認

# 4. マージ先ブランチ（Step 1 の分岐元にも使う）
BASE_BRANCH=$(echo "$CONFIG" | jq -r '.baseBranch // "main"')

# 5. worker の起動可否をここで確定する（board を書き換える前に）
#    engine が使えるか、必要な model/effort が config に揃っているか、CLI が存在するかを検証する。
#    Step 4 まで遅らせると、item を In Progress にした後で停止し、宙吊りのタスクが残る。
```

worker の解決規則は [worker-contract.md](references/worker-contract.md) に従う。**解決できなければ、board を含む
一切の書き込みを行う前に停止して報告する**（`workers.engine` を `none` にすれば orchestrator 自身が実装して続行できる）。

## Per-task Loop

**1タスクを終端状態（Done または escalated-skip）にしてから次を取得する（直列・再開可能）。**
再起動時に In Progress のタスクが既にある場合は**再開扱い**（二重着手しない）。

---

### Step 0: タスク源の確認と次タスク選択

config の `taskSource.mode` に従う:

#### `github-projects` モード

```bash
# field-id / option-id は実行時に解決（config にハードコードしない）
PROJECT_OWNER=$(echo "$CONFIG" | jq -r '.taskSource.githubProjects.owner')
PROJECT_NUMBER=$(echo "$CONFIG" | jq -r '.taskSource.githubProjects.projectNumber')

# Project node ID を取得（gh project item-edit の --project-id に必要）
PROJECT_ID=$(gh project view "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json | jq -r '.id')
# 解決失敗 → エスカレーションして停止
[[ -z "$PROJECT_ID" || "$PROJECT_ID" == "null" ]] && {
  echo "ERROR: Project ID の解決に失敗しました。owner/projectNumber を確認してください。"; exit 1
}

# Status フィールドの option-id を動的解決
FIELD_DATA=$(gh project field-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json)
STATUS_FIELD_ID=$(echo "$FIELD_DATA" | jq -r '.fields[] | select(.name == "Status") | .id')
# 解決失敗 → 即停止
[[ -z "$STATUS_FIELD_ID" || "$STATUS_FIELD_ID" == "null" ]] && {
  echo "ERROR: Status フィールドが見つかりません。field-list を確認してください。"; exit 1
}

# option-id も同様に動的解決
STATUS_IN_PROGRESS_ID=$(echo "$FIELD_DATA" | \
  jq -r '.fields[] | select(.name == "Status") | .options[] | select(.name == "In Progress") | .id')
[[ -z "$STATUS_IN_PROGRESS_ID" || "$STATUS_IN_PROGRESS_ID" == "null" ]] && {
  echo "ERROR: Status オプション 'In Progress' が見つかりません。"; exit 1
}

# pick 対象列（"Ready", "Inbox" 等）。配列の順序が列の優先度を表す（先頭が最優先）
PICK_FROM_JSON=$(echo "$CONFIG" | jq '.taskSource.githubProjects.pickFrom')

# pickFrom 順序を尊重して最高優先タスクを選択
# ※ _pick_order が小さいほど pickFrom の先頭列（高優先）。同一列内は priority でベストエフォート昇順。
# ※ priority フィールドの型は repo 依存（文字列 "P1: next" 等）。sort_by はベストエフォート。
ITEM=$(gh project item-list "$PROJECT_NUMBER" --owner "$PROJECT_OWNER" --format json | \
  jq -r --argjson pick "$PICK_FROM_JSON" \
  '[.items[] | select(.status as $s | $pick | index($s)) | . + {_pick_order: ($pick | index(.status))}]
   | sort_by([._pick_order, .priority])
   | .[0]')

ITEM_ID=$(echo "$ITEM" | jq -r '.id // empty')
# タスクが見つからない場合（pickFrom 列が空）は正常終了
[[ -z "$ITEM_ID" || "$ITEM_ID" == "null" ]] && {
  echo "INFO: 次のタスクが見つかりません（pickFrom 列に対象アイテムがありません）。"; exit 0
}
TASK_TITLE=$(echo "$ITEM" | jq -r '.title')
# Issue URL（Step 2 のコメント投稿で使用）
ISSUE_URL=$(echo "$ITEM" | jq -r '.content.url // ""')
ISSUE_NUMBER=$(echo "$ITEM" | jq -r '.content.number // ""')

# 選択したタスクを In Progress へ遷移
gh project item-edit \
  --project-id "$PROJECT_ID" \
  --id "$ITEM_ID" \
  --field-id "$STATUS_FIELD_ID" \
  --single-select-option-id "$STATUS_IN_PROGRESS_ID"
```

再起動時: `gh project item-list` で Status=In Progress のタスクがあれば、それを再開タスクとする（`ITEM_ID`/`TASK_TITLE`/`ISSUE_URL` を同様に取得して再利用）。

#### `plan-doc` モード

config の `taskSource.planDoc.path` を読み、未チェック（`- [ ]`）の先頭項目を次タスクとする。
完了時にチェックマーク（`- [x]`）に書き換える。

`issueQuery` が設定されている場合は `gh issue list --repo "$EXPECTED_REPO" --search "$QUERY"` で取得。

#### `none` モード

タスク源なし。現在の会話コンテキスト・ユーザー指示を直接使う。

---

### Step 1: feature ブランチ作成

```bash
# タスク名から branch 名を生成
# ASCII タイトルの場合: 小文字化 + スペース/スラッシュをハイフンに置換
# 日本語など非ASCII タイトルの場合: Issue番号をフォールバックとして使用
# （grep -P は macOS BSD grep で無効なため LC_ALL=C の POSIX クラスで判定）
if echo "$TASK_TITLE" | LC_ALL=C grep -qv '^[[:print:][:space:]]*$'; then
  BRANCH="autopilot/issue-${ISSUE_NUMBER:-$(date +%s)}"
else
  BRANCH="autopilot/$(echo "$TASK_TITLE" | tr '[:upper:]' '[:lower:]' | tr ' /' '-' | tr -cd 'a-z0-9-' | cut -c1-50)"
fi
# 着手前に作業ツリーが clean であることを必須にする（fail-closed）。
# dirty のまま次タスクへ進むと、前タスクの未コミット変更がブランチをまたいで持ち越され、
# Step 5 の `git add -A` が別タスクの変更を巻き込んで commit する。
[[ -z "$(git status --porcelain)" ]] || {
  echo "ERROR: 作業ツリーが dirty です。前タスクの後始末が完了していません。"; exit 1
}

# 再開時（Step 0 で In Progress のタスクを拾った場合）: 既存ブランチがあれば作り直さず checkout のみ。
git fetch -q origin "$BASE_BRANCH"
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git checkout "$BRANCH"
else
  # 新規は必ず最新の base から分岐する。現在の HEAD から切ると、前タスクのローカル commit が
  # 次タスクの PR 差分へ混入する（squash merge 運用で顕在化する）
  git checkout -b "$BRANCH" "origin/$BASE_BRANCH"
fi
```

**タスク間の依存に注意する。** `gates.merge` が `human`（既定）の場合、実行中は `origin/$BASE_BRANCH` が動かない。
プランが未 merge の先行タスクの成果に依存していることが分かったら、その base 上では実装できないため
**着手せず escalated-skip にして依存関係をレポートする**（依存を無視して実装すると、重複実装や矛盾する変更になる）。

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

---

### Step 4: 実装（worker へ委譲）

**Step 3 を通過したプランを worker へ渡して実装させる。** engine とモデルの選択・プロンプト・出力契約は
[worker-contract.md](references/worker-contract.md) に従う。

**起動前にモデル段を決める。** プランがやり直しコストの高い実装（0→1、コアドメイン、破壊的変更を伴う基盤実装、
ロールバック困難）であれば `workers.escalatedModel` を使い、**昇格した理由を一言記録してから起動する**。

worker へ必ず伝える要件:
- 現在のhostが読み込んだrepository instructions（`AGENTS.md`、`CLAUDE.md`等）の開発原則を厳守する
- 既存コード・ユーティリティを必ず調べて再利用する
- 品質に妥協しない
- **commit しない**（変更は作業ツリーに残す。commit は Step 5 の PASS 後に orchestrator が 1 回だけ行う）
- repo の外を書かない。push / PR / merge / deploy / board 更新は行わない。ブランチを切り替えない
- **done は実行しない**（品質ゲートは orchestrator が Step 5 で実行する）
- 破壊的操作の確認・要件矛盾・権限不足は `halt`、プランから外れる設計判断が必要なら `needs_orchestrator` で戻す

**起動前に baseline（ブランチ・HEAD・`git status`）を取る。** これが無いと、着手前から存在した変更を worker の成果と誤認し、
worker が既存の未コミット変更を壊しても検出できない。worker 完了後は、baseline との比較を含む
[worker-contract.md](references/worker-contract.md) の「受け取り時の確認」を実行する。満たさなければ指摘を添えて再実行する（最大3回）。

worker が `halt` / `needs_orchestrator` を返した場合は orchestrator が判断する（破壊的操作は「破壊的操作の確認境界」に従う）。
`workers.engine` が `none`、または worker engine を起動できないホストでは、orchestrator 自身が上記要件で実装する
（その場合、設計・アプローチに迷ったら実装前に会話へ提示し確認する）。

---

### Step 5: 実装後ゲート（done Skill）

**委譲した場合も、`done` Skill は orchestrator が実行する**（worker には実行させない。理由は「実行モデル」参照）。
**出力末尾の `quality-gate: PASS` 署名のみを成功判定の根拠**とし、`done` の内部（tier 判定・検証ステップ）には一切踏み込まない。

**PASS を得たら、orchestrator が作業ブランチへ commit する（出荷される唯一の commit）。**
worker に commit させず `done` の後にまとめるのは、`done` が検証だけでなく**修正も行う**ため
（検証失敗の修正・simplify・レビュー指摘の反映）。

**commit 前後に、署名の `verification-tree` と実際の tree が同一であることを照合する**（手順は
[worker-contract.md](references/worker-contract.md) の「commit と後始末」）。「一致するはず」で進めない
— PASS 後に別プロセスが触る場合も、pre-commit hook がファイルを書き換えて成功する場合も、黙ってずれる。
不一致なら push せず `done` を再実行する。`--no-verify` で hook を迂回してはならない。

`quality-gate: FAIL` の場合は、指摘を worker へ差し戻して修正 → 再実行（既定段で最大3回）。
3回収束しなければ、[worker-contract.md](references/worker-contract.md) の事後昇格に従い昇格段で1回だけ再実行する
（**1タスクあたり合計最大4回 = 既定段3回 + 昇格段1回**）。それでも収束しなければエスカレーション・スキップして次へ。

`.agents/done.yml` が無い repo では `done` を実行しない（done は設定作成の確認待ちで止まるため unattended では進まない）。
代わりに config の `verify` コマンドを順に実行し、全て成功した場合のみ出荷判定を満たす。
**`verify` も未設定なら、ゲート無しで先へ進まず escalated-skip とする**（fail-closed）。

UI 変更がある場合は `e2e-capability-verification` スキルの方針に従い動作確認を行う。
MCP（Chrome DevTools / Playwright）が使えない環境では理由をメモしてスキップ。

---

### Step 6: PR 作成 → board を In Review へ

```bash
# ブランチを push（未 push だと gh pr create が対話プロンプトで止まるため先に実行）
git push --set-upstream origin "$BRANCH"

# PR 作成（BASE_BRANCH は Preflight で解決済み）
PR_URL=$(gh pr create \
  --repo "$EXPECTED_REPO" \
  --title "$TASK_TITLE" \
  --body "$PR_BODY" \
  --base "$BASE_BRANCH")

# board の Status を In Review へ（github-projects モード）
STATUS_IN_REVIEW_ID=$(echo "$FIELD_DATA" | \
  jq -r '.fields[] | select(.name == "Status") | .options[] | select(.name == "In Review") | .id')
[[ -z "$STATUS_IN_REVIEW_ID" || "$STATUS_IN_REVIEW_ID" == "null" ]] && {
  echo "ERROR: Status オプション 'In Review' が見つかりません。"; exit 1
}
gh project item-edit \
  --project-id "$PROJECT_ID" \
  --id "$ITEM_ID" \
  --field-id "$STATUS_FIELD_ID" \
  --single-select-option-id "$STATUS_IN_REVIEW_ID"
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

`gates.merge` が文字列 `auto` と完全一致し、かつCIが緑の場合だけmergeする。未設定、未知値、`human` はすべて人間ゲートとしてPR作成後に停止する。`gates.deploy` も同じfail-closed規則を適用する。
Step 7 で CI green を確認済みなので `--auto` は不要。merge戦略フラグは排他なので単一で指定する:

```bash
MERGE_GATE=$(echo "$CONFIG" | jq -r '.gates.merge // "human"')
[[ "$MERGE_GATE" == "auto" ]] || {
  echo "INFO: merge requires a human gate; stopping after PR creation."
  exit 0
}
gh pr merge "$PR_URL" --repo "$EXPECTED_REPO" --squash
```

---

### Step 9: デプロイ

config の `deploy.steps` を順番に実行する。`needed: false` なら省略。

**注意: `deploy.steps[].run` は config から読んだコマンドをそのまま実行する。**
生の `terraform apply` を config に書くことを禁止する（`gh workflow run` 等のラッパー経由）。

```bash
DEPLOY_NEEDED=$(echo "$CONFIG" | jq -r '.deploy.needed // false')
if [[ "$DEPLOY_NEEDED" == "true" ]]; then
  DEPLOY_GATE=$(echo "$CONFIG" | jq -r '.gates.deploy // "human"')
  [[ "$DEPLOY_GATE" == "auto" ]] || {
    echo "INFO: deploy requires a human gate; stopping before deploy."
    exit 0
  }
  # 各 step を実行
  for step in $(echo "$CONFIG" | jq -r '.deploy.steps[] | @base64'); do
    CMD=$(echo "$step" | base64 --decode | jq -r '.run // ""')
    MONITOR=$(echo "$step" | base64 --decode | jq -r '.monitor // ""')
    [[ -n "$CMD" ]] && eval "$CMD"
    [[ -n "$MONITOR" ]] && eval "$MONITOR"
  done
fi
```

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
STATUS_DONE_ID=$(echo "$FIELD_DATA" | \
  jq -r '.fields[] | select(.name == "Status") | .options[] | select(.name == "Done") | .id')
[[ -z "$STATUS_DONE_ID" || "$STATUS_DONE_ID" == "null" ]] && {
  echo "ERROR: Status オプション 'Done' が見つかりません。"; exit 1
}
gh project item-edit \
  --project-id "$PROJECT_ID" \
  --id "$ITEM_ID" \
  --field-id "$STATUS_FIELD_ID" \
  --single-select-option-id "$STATUS_DONE_ID"
```

plan-doc モードはチェックマーク（`- [x]`）に書き換える。次タスクへ。

---

## タスクを終える前の後始末（escalated-skip の場合も必須）

**次タスクへ移る前に、作業ツリーを必ず clean にする。** 失敗・スキップしたタスクの未コミット変更を残したまま次へ進むと、
Step 1 でブランチを切り替えても変更は持ち越され、次タスクの `git add -A` がそれを巻き込んで commit する
（＝スキップしたはずのコードが別タスクの PR として出荷される）。

**未コミット変更を破棄してはならない。** 当該タスクのブランチへ WIP として commit（push はしない）してブランチ名を
レポートに残す。手順は [worker-contract.md](references/worker-contract.md) の「commit と後始末」。

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
| ゲート | 各ゲートで最大3回リトライ → 収束しない（Step 5 のみ、この後さらに昇格段で1回） | エスカレーション記録 → 後始末して次へ |
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
- 🤖 worker: タスクごとに使った engine とモデル段（昇格した場合はその理由）

複数のレポートを Issueコメントに散らさない。1本を朝に読める形で出力する。

---

## Bootstrap（`.agents/autopilot.json` が存在しない場合）

repo の特徴を自動検出し、config の雛形を提案する（**実行はユーザー確認後**）:

1. `terraform` ディレクトリ or `Taskfile.yml` の存在 → infra repo と判定
2. `.github/workflows/` の内容 → デプロイワークフロー候補を列挙
3. `gh project list --owner "$ORG"` → リンク済み Project の候補を提示
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
- **worker に push / PR / merge / deploy / board 更新をさせない。外部書き込みは orchestrator が行い、worker 完了後に形跡が無いか確認する**
- **`done` を worker に実行させない。品質ゲートは orchestrator が実行する**
- **出荷される commit は Step 5 の PASS 後に orchestrator が作る 1 つだけ。worker には commit させない**（escalated-skip 時の WIP commit は push も PR もしない隔離用で、この規則の明示的な例外）
- **worker の自己申告 status で出荷しない。出荷判定は Step 5 の ship-gate のみ**（done.yml がある repo では `quality-gate: PASS` 署名、無い repo では config の `verify` 全成功。どちらも無ければ出荷しない）
- **feature ブランチは常に最新の base から分岐する（前タスクのローカル commit を持ち越さない）**
