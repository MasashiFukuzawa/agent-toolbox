# Codex CLI で起動する

ホストがClaude CodeでもCodexでも同じコマンドを使う。必要なのはシェルと`codex` CLIだけである。引数は版で変わるので、初めて使う環境と失敗時は`codex exec --help`で確かめる。Codexは`approval: never`で動くので、承認の問い合わせは起きない。

以下のコマンドはCLIに渡す中身であり、[実行記録](durable-run-record.md) を作るwrapperの内側で実行する。`REVIEW_MODEL`と`REVIEW_EFFORT`は、`model-selection`で確定した値を起動前に設定する。

## レビュー（read-only）

```bash
codex exec \
  --json \
  -o "<final_output>" \
  -s read-only \
  -m "$REVIEW_MODEL" \
  -C /path/to/project \
  -c model_reasoning_effort="$REVIEW_EFFORT" \
  "$(cat <<'SECOND_OPINION_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke second-opinion or any review skill, codex exec, claude -p, or any nested reviewer.
Return findings directly as text.

<依頼内容>
SECOND_OPINION_PROMPT
)" < /dev/null > "<event_log>" 2> "<stderr_log>"
```

- `-s read-only`は必須。ファイルの変更をsandboxで禁止する。
- `-m`と`-c model_reasoning_effort`は必ず明示する。省くと設定ファイルの既定で動き、選んだ値が効かない。
- `-C`で作業rootを指定する。対象がGitのrepoでなければ`--skip-git-repo-check`を足す。
- `--json`のevent streamをrepoの外の`<event_log>`へ残し、最初の`thread.started.thread_id`をsession IDとして読む。`-o`で最終本文を`<final_output>`へ保存する。`--ephemeral`は付けない。
- 末尾の`< /dev/null`は必須。標準入力の待ちを防ぐ。`Reading additional input from stdin...`と表示されても、redirect済みなら先へ進む。

### 差分のレビュー

差分でも上の汎用の`codex exec`を使い、対象と範囲を依頼文で言い切って、`git diff`などで取得させる。

`codex exec review`（`--uncommitted`・`--base`・`--commit`）は依頼文と同時に指定できず、観点も返す形式も渡せない。ユーザーが明示的に求めたときだけ使い、観点の指定が効かないことを一言伝える。

```bash
codex exec review --json -o "<final_output>" -m "$REVIEW_MODEL" \
  -c model_reasoning_effort="$REVIEW_EFFORT" --uncommitted \
  < /dev/null > "<event_log>" 2> "<stderr_log>"
```

`codex exec review`は`-s`を持たないので付けない。作業directoryがGitのrepoである必要がある。「検査しなかった範囲」を求められないので、完了はprocessの正常終了と`<final_output>`の存在で判断する。

### 複数のrepoをまたぐレビュー

`-C`を対象のrepo群の共通の親へ向け、`--skip-git-repo-check`を付ける。依頼文には、共通の親からの相対pathで対象を並べ、対象外のrepoを探索させない。

## 動作確認（写しの中だけ書き込む）

```bash
codex exec \
  --json \
  -o "<final_output>" \
  -s workspace-write \
  -m "$REVIEW_MODEL" \
  -C "<snapshot_worktree>" \
  -c model_reasoning_effort="$REVIEW_EFFORT" \
  "$(cat <<'SECOND_OPINION_PROMPT'
You are the verifier. Work only inside the working root.
Do not invoke second-opinion or any review skill, codex exec, claude -p, or any nested reviewer.
Do not fix the code. Do not commit, push, or post anything. Return the results directly as text.

<依頼内容>
SECOND_OPINION_PROMPT
)" < /dev/null > "<event_log>" 2> "<stderr_log>"
```

- `-s workspace-write`は、書き込みを作業root（写し）とsandboxが許す一時領域に限る。`--add-dir`は書き込める場所を増やすので付けない。`danger-full-access`と`--dangerously-bypass-approvals-and-sandbox`は使わない。
- このsandboxでは、ネットワークが既定で使えないことがある。依存の導入にネットワークが要るときは、許可する設定をその時点の`codex exec --help`と公式資料で確かめる。確かめられなければ、導入済みの環境で動かせる範囲だけを確かめさせ、残りを「確かめられず」として返させる。
- 終了後に、写しの側の`git status`に加えて、本体のツリーの`git status --porcelain`が起動前と同じであることを確かめる。

## 依頼文の渡し方

- 依頼文は必ずsingle-quotedのheredocで渡す（`<<'SECOND_OPINION_PROMPT'`）。バッククォート・`$VAR`・`$(...)`を含む文を二重引用符で直接書くと、シェルが展開して依頼文を壊す。依頼文の中に区切りと同じ行があるときだけ、別の一意な区切りの名前に変える。
- heredocの中に`$HOME`などの変数を書かない。対象のpathはheredocの外の`-C`で渡し、本文には展開済みの絶対pathを書く。

## 復旧と追加質問

復旧の判断の順序はSKILL.mdの「中断・回収失敗からの復旧」に従う。

```bash
codex exec resume SESSION_ID \
  --json \
  -o "<recovery_output>" \
  -m <original_model> \
  -c model_reasoning_effort="<original_effort>" \
  -c sandbox_mode="read-only" \
  "$(cat <<'SECOND_OPINION_RECOVERY'
You are the reviewer. Do not invoke second-opinion or any review skill, codex exec, claude -p, or any nested reviewer.
Return findings directly as text.

直前の処理を継続してください。調べ終えた範囲をやり直さず、未完了の部分だけを完了させてください。
この回答は中断後の継続であり、元の最終本文の逐語的な再掲とは主張しないでください。
今回実際に検査した範囲と、sessionの履歴から引き継いだ範囲を分けて「検査しなかった範囲」を返してください。新しい観点は足さないでください。
SECOND_OPINION_RECOVERY
)" < /dev/null > "<recovery_event_log>" 2> "<recovery_stderr_log>"
```

- resumeは元のsessionの作業rootを引き継ぐ。`-s`と`-C`は持たないので足さず、権限は`-c sandbox_mode`で明示し直す。レビューは`"read-only"`、動作確認は`"workspace-write"`にする。Gitのrepoでないrootから起動したsessionでは`--skip-git-repo-check`を付け直す。
- 正確なIDとして扱えるのは、記録済みのホストのタスクのmetadataと、記録済みのevent logの`thread.started`だけである。`--last`は別のsessionを選びうるので使わない。
- `codex exec review`で起動した処理は、正常終了と`<final_output>`の存在を完了の根拠にする。
- 指摘の深掘りや反論の確認は、同じ`codex exec resume SESSION_ID`に質問の本文だけを渡す（例「指摘2を、根拠となるpath:lineと成立する条件を示して詳しく説明してください」）。
- 復旧や追加質問の出力先（`<recovery_output>`など）も実行記録へ追記し、既存の出力を上書きしない。

## 出力の取り出し

- 完了したら`<final_output>`を読む。最終本文だけが入っている。event logは、session IDの取得と、中断時の途中の状態の確認にだけ使う。
- `--json`を付けずに起動した`codex exec review`のtext出力は数百KBになることがある。全体を読まず、末尾と見出しの検索で必要な箇所を特定し、冒頭のメタ情報は除く。
- `ERROR rmcp::transport::worker: ... Auth(AuthorizationRequired)`は、対話での認証が要るMCPを起動できなかった表示である。本文が出ていれば失敗として扱わない。
