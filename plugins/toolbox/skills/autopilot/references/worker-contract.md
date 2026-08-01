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
6. **破壊的操作の確認・要件矛盾・権限不足は `halt` で返す。** 自分で判断して踏み込まない
7. **プランから外れる設計判断が必要になったら `needs_orchestrator` で返す。** 自分で決めない

不変条件 2 は**指示であって機構ではない**。`codex-exec` は sandbox で概ね担保されるが、`claude-subagent` はホストのツールを継承しうる。
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

自由作文の進捗サマリの**末尾**に、単独行の区切りと 1 行 JSON を出す。

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

## 受け取り時の確認（orchestrator 側）

`status` を鵜呑みにせず、次を確認してから Step 5 へ進む。

```bash
git status --porcelain                                # 非空（実装された変更が作業ツリーにある）
git rev-list --count "origin/$BASE_BRANCH..HEAD"      # 0（worker が commit していない）
git ls-remote --heads origin "$BRANCH"                # 空（worker が push していない）
gh pr list --repo "$EXPECTED_REPO" --head "$BRANCH"   # 空（worker が PR を作っていない）
```

`git log origin/<branch>` は使わない。Step 6 まで push しないため remote-tracking ref が存在せず、正常系で失敗する。

worker が commit してしまった場合は、それ自体を失敗扱いにせず、**その commit を残したまま Step 5 へ進む**
（done は HEAD からの差分と未コミット分の両方を検証する）。ただし契約違反として記録し、再実行時の指摘に含める。

`git status` が空（変更が無い）場合は指摘を添えて再実行する（**最大3回**。収束しなければ escalated-skip）。
品質そのものの判定は Step 5 の done が行う。

## モデル選択と昇格

**engine とモデル段は独立の軸である。** engine（どの実行系か）を選んだうえで、そのengine内で 2 段のモデルから選ぶ。

| 段 | config | 用途 |
|---|---|---|
| 既定 | `workers.model` | 定型実装、既知パターンの適用、プランどおりの変更 |
| 昇格 | `workers.escalatedModel` | **やり直しコストが高い実装** |

**空文字のときの扱いは engine で異なる。**

- **`claude-subagent`**: ホストがエイリアス（`sonnet` / `opus` 等）を解決するため、空文字なら既定段にバランス型、昇格段に最上位のエイリアスを使う。具体的なモデル ID を知る必要はない
- **`codex-exec`**: 具体的なモデル ID が必要で、ID は時期により変わる。**空文字なら推測せず、config への設定を促して停止する**（記憶に頼って廃止済み ID を渡すと exec が失敗するか、意図しない旧モデルで実装が進む）

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
- **昇格段でも `codex-exec` の effort は `medium` のまま**にする。実装の質は effort ではなくプランの具体性と反復で決まり、effort を上げると探索が伸びて所要時間だけが増える。上げるのはモデル段であって effort ではない

## engine adapter

`workers.engine` で選ぶ。**orchestrator のホストとは独立**に指定できる。

### `claude-subagent`（Claude Code orchestrator 専用）

Agent tool でサブエージェントを起動する。

- `model`: 昇格判定の結果（既定段 or 昇格段）
- `run_in_background: true` で起動し、完了通知を受けて Step 5 へ進む
- prompt の冒頭に repo の絶対パスと作業ブランチ名を書く

### `codex-exec`（どちらのホストからも使える）

`WORKER_MODEL` には昇格判定の結果を入れる。config 既定に委ねず必ず `-m` で明示する。

```bash
codex exec \
  -s workspace-write \
  -m "$WORKER_MODEL" \
  -C "$REPO_ROOT" \
  -c model_reasoning_effort="medium" \
  "$(cat <<'AUTOPILOT_WORKER_PROMPT'
You are the implementation worker. Work only inside the directory given by -C.
Do not push, open PRs, merge, deploy, update the board, or comment on issues.
Do not switch branches. Do not commit; leave your changes in the working tree.
Do not run the done quality gate; the orchestrator runs it, then commits, after you finish.
Do not invoke codex exec, claude -p, or any nested worker or reviewer.
End your output with the <<<AUTOPILOT_WORKER_RESULT>>> JSON block.

<プラン・受入条件・品質要件>
AUTOPILOT_WORKER_PROMPT
)" < /dev/null
```

- 権限と effort は**レビュー用途と逆**である（`codex-review` は `read-only` + `high`、実装 worker は `workspace-write` + `medium`）。混用しない
- `< /dev/null` は必須（stdin 待ちのハング防止）
- Claude Code orchestrator 上では `run_in_background: true` で起動する。Codex orchestrator 上は foreground で実行する

### `none`

委譲せず orchestrator 自身が Step 4 を実装する（委譲導入前の挙動）。worker engine が使えないホストのフォールバックでもある。

**`none` では実装と品質ゲートの分離が成立しない**（同じ主体が実装し done を走らせる）。従来と同等の保証水準であり、
「実行主体を分ける」という担保はこの経路には適用されない。委譲可能な engine があるなら `none` を選ばない。
