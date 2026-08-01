# autopilot worker 契約

Step 4（実装）を委譲する **worker** と、委譲元の **orchestrator**（autopilot 本体）の間の契約を定義する。
worker は**コードを書くところまで**を担い、それ以外はすべて orchestrator が担う。

## 責務の分割

| | orchestrator | worker |
|---|---|---|
| プラン作成・第三者レビュー（Step 2〜3） | ✅ | — |
| 実装・ローカルでの動作確認（Step 4） | — | ✅ |
| **done による品質ゲート（Step 5）** | ✅ | — |
| **commit（Step 5 の PASS 後に 1 回）** | ✅ | — |
| push / PR / merge / deploy / board 更新（Step 6〜11） | ✅ | — |

**commit は done が PASS した後に orchestrator が 1 回だけ行う。** worker は commit しない。
`done` は未コミットの作業ツリーを検証する前提で設計されており（一時 index に `git add -A` して verification tree を計算する）、
かつ `done` 自身が検証失敗の修正・simplify・レビュー指摘の反映でファイルを書き換える。
**検証と修正がすべて終わってから 1 回 commit することで、署名が保証した内容と push される内容が完全に一致する。**

**done を worker に実行させない。** 実装したモデルが自分の実装をレビューして自分で PASS 署名を出す構図になり、
done の advisor レビュー（done Step 4）と外部レビュー（Step 5）が独立性を失う。
また、署名を後から検証しても「署名がツリー状態と整合しているか」しか分からず「done が実際に走ったか」は確かめられないため、
**実行主体を信頼できる側に置くことが唯一の実効的な担保**である。

## 不変条件（worker 側・逸脱禁止）

1. **repo の作業ツリーの外を書かない。** repo 外・ホームディレクトリ・設定ディレクトリを変更しない
2. **外部書き込みをしない。** push / PR 作成 / merge / deploy / board 更新 / Issue コメント / チャット通知はすべて orchestrator の責務
3. **ブランチを切り替えない。** orchestrator が作成したブランチの上で作業する
4. **commit しない。** 変更は作業ツリーに残したまま終える（commit は Step 5 の PASS 後に orchestrator が行う）
5. **`done` を実行しない。** 品質ゲートは orchestrator の責務
6. **ネスト起動をしない。** 別の worker、`codex exec`、`claude -p`、review 系スキルを起動しない
7. **破壊的操作の確認・要件矛盾・権限不足は `halt` で返す。** 自分で判断して踏み込まない
8. **プランから外れる設計判断が必要になったら `needs_orchestrator` で返す。** 自分で決めない

**これらは指示であって、機構による保証ではない。** `codex-exec` の `workspace-write` sandbox が制約するのは主に
モデルが生成する shell コマンドであり、ユーザー設定由来の MCP・connector・notify・hooks はその外側で動く。
`/tmp` などへの書き込みも止まらない。`claude-subagent` に至ってはホストのツールをそのまま継承しうる。

sandbox が実際に効くのは次の 2 点で、これは**設計と合致している**。

- **`.git/` は `workspace-write` でも書けない。** そのため `git add` / `git commit` / `git switch` は概ね失敗し、不変条件 3・4 は機構としても支えられる
- **network access は既定で無効。** worker は依存を新規インストールできない（後述）

orchestrator は worker 完了後に、検出可能な範囲だけを確認する（下記「受け取り時の確認」）。
**deploy や board 更新のように検出手段が無い逸脱は、この確認では拾えない**ことを前提に扱う。

## orchestrator が渡す入力

| 項目 | 内容 |
|---|---|
| タスク | title、Issue URL / 番号、受入条件 |
| プラン | Step 2〜3 で作成しレビューを通過した実装方針 |
| ブランチ | orchestrator が作成済みのブランチ名 |
| 品質要件 | repository instructions（`AGENTS.md` / `CLAUDE.md` 等）の厳守、既存コードの調査と再利用 |
| 出力契約 | 下記 JSON ブロックを末尾に出すこと |

## 出力契約（必須）

worker は次の形の JSON を返す。**受け取り方は engine で異なる**（`codex-exec` は `--output-schema` / `-o`、
`claude-subagent` は下記の区切り付き末尾ブロック）。フィールドはどちらも同じ。

`claude-subagent` の場合は、自由作文の進捗サマリの**末尾**に、単独行の区切りと 1 行 JSON を出す。

```
... 人間可読の進捗・差分サマリ ...

<<<AUTOPILOT_WORKER_RESULT>>>
{"status":"succeeded","branch":"autopilot/issue-123","files_changed":["lib/foo.py","tests/test_foo.py"],"unresolved":[],"next_action_hint":null,"error_summary":null}
<<<END>>>
```

| フィールド | 型 | 説明 |
|---|---|---|
| `status` | `succeeded` \| `halt` \| `needs_orchestrator` | worker 自己申告 |
| `branch` | string | 作業したブランチ名 |
| `files_changed` | string[] | 変更したファイル（未コミットの状態で作業ツリーに残っている） |
| `unresolved` | string[] | 未解決の懸念 |
| `next_action_hint` | string \| null | orchestrator への次アクション提案 |
| `error_summary` | string \| null | エラー概要 |

規約:

- 区切り `<<<AUTOPILOT_WORKER_RESULT>>>` と `<<<END>>>` は**単独行**
- JSON は**1 行**、行末コメントを含めない
- parser は**最後の出現**を使う（本文中で区切り文字列に言及しても壊れない）
- JSON ブロックが無い出力は失敗として扱い、再実行する（黙って生テキストを採用しない）

## 起動前の baseline 取得（orchestrator 側・必須）

baseline を取らないと、**worker 着手前から存在した変更を worker の成果と誤認**し、
worker が既存の未コミット変更を上書き・削除しても検出できない。

```bash
REPO_ROOT=$(git -C "$CANDIDATE" rev-parse --show-toplevel)          # 必ず絶対パスに解決する
ACTUAL_BRANCH=$(git -C "$REPO_ROOT" symbolic-ref --quiet --short HEAD) || exit 1
[[ "$ACTUAL_BRANCH" == "$BRANCH" ]] || exit 1                        # detached HEAD / 別ブランチで起動しない
BEFORE_HEAD=$(git -C "$REPO_ROOT" rev-parse HEAD)
BEFORE_STATUS=$(git -C "$REPO_ROOT" status --porcelain)
```

## 受け取り時の確認（orchestrator 側）

`status` を鵜呑みにせず、次を確認してから Step 5 へ進む。

```bash
git -C "$REPO_ROOT" rev-parse HEAD                     # BEFORE_HEAD と一致（worker が commit していない）
git -C "$REPO_ROOT" status --porcelain                 # BEFORE_STATUS から増えている（実装された変更がある）
git ls-remote --heads origin "$BRANCH"                 # 空（worker が push していない）
gh pr list --repo "$EXPECTED_REPO" --head "$BRANCH"    # 空（worker が PR を作っていない）
```

`git log origin/<branch>` は使わない。Step 6 まで push しないため remote-tracking ref が存在せず、正常系で失敗する。

worker が commit してしまった場合（`claude-subagent` では起こりうる）は、それ自体を失敗扱いにせず
**その commit を残したまま Step 5 へ進む**（done は HEAD からの差分と未コミット分の両方を検証する）。
ただし契約違反として記録し、再実行時の指摘に含める。

変更が増えていない場合は指摘を添えて再実行する（**最大3回**。収束しなければ escalated-skip）。
品質そのものの判定は Step 5 の done が行う。

## モデル選択と昇格

**engine とモデル段は独立の軸である。** engine（どの実行系か）を選んだうえで、そのengine内で 2 段のモデルから選ぶ。

| 段 | config | 用途 |
|---|---|---|
| 既定 | `workers.model` | 定型実装、既知パターンの適用、プランどおりの変更 |
| 昇格 | `workers.escalatedModel` | **やり直しコストが高い実装** |

**空文字のときの扱いは engine で異なる。**

- **`claude-subagent`**: ホストがエイリアス（`sonnet` / `opus` 等）を解決するため、空文字なら既定段にバランス型、昇格段に最上位のエイリアスを使う。具体的なモデル ID を知る必要はない
- **`codex-exec`**: 具体的なモデル ID が必要で、ID は時期により変わる。**空文字なら推測せず、config への設定を促して停止する**（記憶に頼って廃止済み ID を渡すと exec が失敗するか、意図しない旧モデルで実装が進む）。`codex debug models` で利用可能な ID と各モデルの対応 effort を実行時に列挙できるので、**config に書かれた ID と effort の組み合わせは起動前にこれで検証する**。ただし一覧は account・provider・CLI version で変わり、`debug` は安定 API ではないため、空 config を埋める用途には使わない

いずれの場合も、**実際に使ったモデル名を記録し End-of-run レポートに出す**。

### 昇格条件

orchestrator が Step 4 の起動前にプランを見て判定する。次のいずれかに当たれば昇格する。

- **0→1 の実装**（前例が repo 内に無く、設計そのものを実装しながら決める部分が残る）
- **コアドメインの実装**（そのrepoの中心的な業務ロジック・不変条件を定義・変更する）
- **破壊的変更を伴う基盤実装**（既存の契約・スキーマ・公開インターフェースを壊す、移行手順が要る）
- **ロールバックが困難**（データ移行、外部への不可逆な作用を含む）

判断軸は**題材の難しさではなく、間違えたときの手戻りの大きさ**である。認証や並行処理に触れること自体は昇格理由にならない。
プランどおりに書けば済む定型実装は、対象領域に関わらず既定段で扱う。

### 昇格の規律

- **昇格したら理由を一言記録してから起動する**（Issue コメントまたは会話に、どの基準に当たったかを書く）。所要時間とコストが増えるため、無言で昇格しない
- **降格は自動で行わない。** 昇格条件に当たったタスクを、時間やコストを理由に既定段へ落とさない
- **ユーザーや config がモデルを明示した場合、自動判定で上書きしない**（上げるのも下げるのも禁止）
- **昇格しても品質ゲートは変わらない。** 強いモデルを使ったことを Step 5 を軽くする理由にしない
- **事後の昇格**: 既定段の worker が 3 回で収束しない場合、同じ段で 4 回目を回さず、**昇格段で 1 回だけ再実行**する。それでも収束しなければ escalated-skip（Stop Conditions の「最大3回」はこの 1 回を含めて数える）。理由を記録する
- **effort もモデル段に合わせて上げる。** 既定段は `medium`、昇格段は `high`。effort は推論の深さそのものに効く（モデルカタログ自身が `medium` を「速度と深さのバランス」、`high` を「複雑な問題向けに深さを増す」と定義している）。やり直しコストが高いからモデルを上げておきながら effort だけ据え置くのは整合しない。対応 effort はモデルごとに異なるため、指定前に `codex debug models` で確認する

## engine adapter

`workers.engine` で選ぶ。**orchestrator のホストとは独立**に指定できる。

### `claude-subagent`（Claude Code orchestrator 専用）

Agent tool でサブエージェントを起動する。

- `model`: 昇格判定の結果（既定段 or 昇格段）
- `run_in_background: true` で起動し、完了通知を受けて Step 5 へ進む
- prompt の冒頭に repo の絶対パスと作業ブランチ名を書く

### `codex-exec`（どちらのホストからも使える）

`WORKER_MODEL` / `WORKER_EFFORT` には昇格判定の結果を入れる。config 既定に委ねず必ず `-m` と `-c` で明示する。

**出力契約は末尾 JSON ブロックではなく、`--output-schema` と `-o` で受け取る。** 自由文の末尾を区切りで探す方式は、
進捗・メタ出力が stdout に混ざる可能性と、background runner が stdout/stderr を結合する可能性の両方に対して脆い。

```bash
codex exec \
  -s workspace-write \
  -m "$WORKER_MODEL" \
  -C "$REPO_ROOT" \
  -c model_reasoning_effort="$WORKER_EFFORT" \
  --ignore-user-config \
  --ephemeral \
  --disable multi_agent \
  --disable multi_agent_v2 \
  --output-schema "$SCHEMA_FILE" \
  -o "$RESULT_FILE" \
  "$(cat <<'AUTOPILOT_WORKER_PROMPT'
You are the implementation worker. Work only inside the directory given by -C.
Do not push, open PRs, merge, deploy, update the board, or comment on issues.
Do not switch branches. Do not commit; leave your changes in the working tree.
Do not run the done quality gate; the orchestrator runs it, then commits, after you finish.
Do not invoke codex exec, claude -p, or any nested worker or reviewer.

<プラン・受入条件・品質要件>
AUTOPILOT_WORKER_PROMPT
)" < /dev/null
```

`$SCHEMA_FILE` には「出力契約」の JSON Schema を書き出す。`$RESULT_FILE` に最終メッセージだけが入るので、
orchestrator はそれを直接 parse する（`<<<AUTOPILOT_WORKER_RESULT>>>` 区切りは `claude-subagent` 用の代替手段であり、
`codex-exec` では使わない）。exit status が非 0、schema 不一致、`$RESULT_FILE` が空のいずれかは失敗として扱う。

各フラグの理由:

| フラグ | 理由 |
|---|---|
| `--ignore-user-config` | ユーザーの `~/.codex/config.toml`（MCP server・notify・plugins 等）を継承しない。unattended 実行の再現性と隔離のため |
| `--ephemeral` | session file を Codex home へ永続化しない |
| `--disable multi_agent` / `multi_agent_v2` | built-in subagent を無効化する。ネスト起動禁止を**指示から機構へ**寄せる唯一の手段。ただし完全な隔離ではない |
| `--output-schema` / `-o` | 出力契約を機械可読にする（前述） |
| `< /dev/null` | stdin 待ちのハング防止。**必須** |

- 権限と effort は**レビュー用途と逆**である（`codex-review` は `read-only`、実装 worker は `workspace-write`）。混用しない
- `codex exec` は常に `approval: never` で動く（`-a` フラグは持たない）。承認プロンプトで止まる心配は無いが、**外側の wall-clock timeout は別途必要**
- **network は既定で無効**なので、worker は依存を新規インストールできない。テスト実行に依存インストールが要る repo では、**起動前に orchestrator 側で provision しておく**。どうしても必要なら `-c sandbox_workspace_write.network_access=true` を足すが、その場合ネスト起動に対する副次的な防御も失われる
- `-C` には `git rev-parse --show-toplevel` の絶対パスを渡す。subdirectory を渡すとその外は読めても書けないことがある
- Claude Code orchestrator 上では `run_in_background: true` で起動する。Codex orchestrator 上は foreground で実行する

### `none`

委譲せず orchestrator 自身が Step 4 を実装する（委譲導入前の挙動）。worker engine が使えないホストのフォールバックでもある。

**`none` では実装と品質ゲートの分離が成立しない**（同じ主体が実装し done を走らせる）。従来と同等の保証水準であり、
「実行主体を分ける」という担保はこの経路には適用されない。委譲可能な engine があるなら `none` を選ばない。
