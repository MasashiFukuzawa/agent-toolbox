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
| **e2e** | UI/E2E 検証の安全方針 | e2e-capability-verification + Chrome DevTools / Playwright MCP |
| **reporter** | 進捗・引き継ぎレポート | progress-report |

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
```

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
git checkout -b "$BRANCH"
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

---

### Step 4: 実装

現在のhostが読み込んだrepository instructions（`AGENTS.md`、`CLAUDE.md`等）の開発原則を厳守して実装する。
- 既存コード・ユーティリティを必ず調べて再利用する
- 設計・アプローチに迷ったら実装前に会話に提示し確認する
- 品質に妥協しない

---

### Step 5: 実装後ゲート（done Skill）

現在のhostで `done` Skillを明示的に実行し、**出力末尾の `quality-gate: PASS` 署名のみを成功判定の根拠**とする。
`done` の内部（tier 判定・検証ステップ）には一切踏み込まない。

`quality-gate: PASS` が出なければ `done` の指示に従い修正 → 再実行（最大3回）。
3回収束しなければ該当タスクをエスカレーション・スキップして次へ。

UI 変更がある場合は `e2e-capability-verification` スキルの方針に従い動作確認を行う。
MCP（Chrome DevTools / Playwright）が使えない環境では理由をメモしてスキップ。

---

### Step 6: PR 作成 → board を In Review へ

```bash
# ブランチを push（未 push だと gh pr create が対話プロンプトで止まるため先に実行）
git push --set-upstream origin "$BRANCH"

# マージ先ブランチ（config.baseBranch が未設定なら "main"）
BASE_BRANCH=$(echo "$CONFIG" | jq -r '.baseBranch // "main"')

# PR 作成
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
