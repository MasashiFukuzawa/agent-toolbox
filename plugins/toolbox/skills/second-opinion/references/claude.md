# Claude CLI で起動する

ホストがCodexでもClaude Codeでも同じコマンドを使う。必要なのはシェルと`claude` CLIだけである。引数は版で変わるので、初めて使う環境と失敗時は`claude --help`で確かめる。

以下のコマンドはCLIに渡す中身であり、[実行記録](durable-run-record.md) を作るwrapperの内側で実行する。`REVIEW_MODEL`と`REVIEW_EFFORT`は、`model-selection`で確定した値を起動前に設定する。

## レビュー（read-only）

```bash
claude -p "$(cat <<'SECOND_OPINION_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke second-opinion or any review skill, codex exec, claude -p, or any nested reviewer.
Return findings directly as text.

<依頼内容>
SECOND_OPINION_PROMPT
)" \
  --session-id <session_uuid> \
  --model "$REVIEW_MODEL" \
  --effort "$REVIEW_EFFORT" \
  --add-dir /path/to/project \
  --permission-mode plan \
  --output-format stream-json \
  --verbose \
  --disallowedTools "Edit,Write,NotebookEdit" \
  < /dev/null > "<event_log>" 2> "<stderr_log>"
```

- `--permission-mode plan`と`--disallowedTools "Edit,Write,NotebookEdit"`は必ず両方入れる。前者はBashを含む実行全体を変更しないモードにし、後者は編集のツールを禁止する。実行の直前に、両方があることを確かめる。
- `--disallowedTools`は可変長の引数なので、依頼文は必ず最初の引数に置く。後ろに置くと依頼文が認識されない。
- `--add-dir`で対象のdirectoryへのアクセスを許可する。複数のdirectoryを見せるときは、共通の親を広く許可せず、必要なpathだけを並べ、依頼文にも対象のpathを書く。

  ```bash
  --add-dir /path/to/repo-a /path/to/repo-b /path/to/shared
  ```

- 起動前に新しいUUIDを採番して`--session-id`に渡す。`--no-session-persistence`は付けない。`--output-format stream-json --verbose`で最初のeventを`<event_log>`へすぐ残し、そのeventのsession IDが採番したUUIDと一致することを、sessionが成立した根拠にする。
- 末尾の`< /dev/null`は必須。依頼文以外の標準入力を待たせない。

## 動作確認（写しの中だけ書き込む）

wrapperは、作業directoryを写しのworktreeにして起動する。

```bash
claude -p "$(cat <<'SECOND_OPINION_PROMPT'
You are the verifier. Work only inside the current directory.
Do not invoke second-opinion or any review skill, codex exec, claude -p, or any nested reviewer.
Do not fix the code. Do not commit, push, or post anything. Return the results directly as text.

<依頼内容>
SECOND_OPINION_PROMPT
)" \
  --session-id <session_uuid> \
  --model "$REVIEW_MODEL" \
  --effort "$REVIEW_EFFORT" \
  --permission-mode acceptEdits \
  --output-format stream-json \
  --verbose \
  --allowedTools "Bash(<動かし方の接頭辞> *)" \
  < /dev/null > "<event_log>" 2> "<stderr_log>"
```

- `--add-dir`は付けない。作業directoryである写しだけが対象になる。
- `--permission-mode acceptEdits`は、作業directoryの中のファイル編集を確認なしで通す。
- `--allowedTools`には、依頼文の「動かし方」に書いたコマンドの接頭辞だけを並べる（例: `"Bash(uv run *)" "Bash(npm *)"`）。可変長の引数なので、依頼文は最初の引数に置く。非対話の実行では、許可していないコマンドは実行されない。
- **Claude CLIは、Bashの書き込み先を既定ではOSの水準で制限しない。** 写しの外へ書かせないことは、作業directory、許可するコマンドの絞り込み、依頼文の3つで担保する。OSの水準で止める必要がある対象では、Codexを検証役に選ぶか、Claude CLIのsandboxの設定をその時点の公式資料で確かめてから有効にする。
- 終了後に、写しの側の`git status`に加えて、本体のツリーに第三者の実行による変更が無いことを`git status --porcelain`で確かめる。待ち時間に自分や並行作業が加えた変更は除いて比べる。

## 依頼文の渡し方

- 依頼文は必ずsingle-quotedのheredocで渡す（`<<'SECOND_OPINION_PROMPT'`）。バッククォート・`$VAR`・`$(...)`を含む文を`claude -p "..."`へ直接書くと、シェルが展開して依頼文を壊す。依頼文の中に区切りと同じ行があるときだけ、別の一意な区切りの名前に変える。
- heredocの中に`$HOME`などの変数を書かない。展開されず、文字のまま相手へ渡る。対象のpathはheredocの外の引数で渡し、本文には展開済みの絶対pathを書く。

## 復旧と追加質問

復旧の判断の順序はSKILL.mdの「中断・回収失敗からの復旧」に従う。resumeは、元のモデル・effort・権限の引数を保って行う。

```bash
claude -p "$(cat <<'SECOND_OPINION_RECOVERY'
You are the reviewer. Do not invoke second-opinion or any review skill, codex exec, claude -p, or any nested reviewer.
Return findings directly as text.

直前の処理を継続してください。調べ終えた範囲をやり直さず、未完了の部分だけを完了させてください。
この回答は中断後の継続であり、元の最終本文の逐語的な再掲とは主張しないでください。
今回実際に検査した範囲と、sessionの履歴から引き継いだ範囲を分けて「検査しなかった範囲」を返してください。新しい観点は足さないでください。
SECOND_OPINION_RECOVERY
)" \
  --resume <session_uuid> \
  --model <original_model> \
  --effort <original_effort> \
  --add-dir /path/to/project \
  --permission-mode plan \
  --output-format stream-json \
  --verbose \
  --disallowedTools "Edit,Write,NotebookEdit" \
  < /dev/null > "<recovery_event_log>" 2> "<recovery_stderr_log>"
```

- 動作確認のresumeでは、権限の引数を動作確認の形（`--permission-mode acceptEdits`と`--allowedTools`、`--add-dir`なし）に置き換え、同じ写しを作業directoryにする。
- 正確なIDとして扱えるのは、起動時の記録、記録済みのホストのタスクのmetadata、記録済みの出力に含まれるIDだけである。`--continue`は作業directoryの直近のsessionを暗黙に選ぶので使わない。`--fork-session`も同じ処理の復旧には使わない。
- 指摘の深掘りや反論の確認は、同じ権限の引数と正確なsession IDで、質問の本文だけを渡す（例「指摘2を、根拠となるpath:lineと成立する条件を示して詳しく説明してください」）。
- 復旧や追加質問の出力先（`<recovery_event_log>`など）も実行記録へ追記し、既存の出力を上書きしない。

## 出力の取り出し

回収したstream-jsonは数百KBになることがある。全体を読まず、result eventから最終本文を取り出す。
