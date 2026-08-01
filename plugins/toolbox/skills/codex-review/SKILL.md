---
name: codex-review
description: >-
  Codex CLI の独立インスタンスでコードや差分を read-only レビューする。Codex・OpenAI を明示した第三者レビューに使う。一般的なレビューや Claude 指定には使わない。「Codexに見てもらって」を正のトリガーとし、provider未指定の第三者レビューでは勝手に選ばず、ユーザーへ確認する。
---
# Codex Review スキル

このスキルは Claude Code / Codex / Cursor のどのホスト（エージェント）からも呼ばれる前提で書かれている。ホスト固有の手順は「実行時間と中断の防止」のホスト分岐に従う。

**用途境界:** 本スキルは第三者レビュー専用で、`read-only` + 既定 `high`（`xhigh` 以上は使わない）。実装ワーカーとして Codex を委譲する場合は別のオーケストレーター手順を使い、`workspace-write` + 通常 `medium` とする。同じCLIでも権限とeffortが逆なので混用しない。

## レビューの目的

本スキルの価値は**モデルの強さではなく独立性**にある。現セッションの文脈・前提・思い込みを共有しない別プロセスが、**実装者・設計者の視野に無い観点を持ち込む**ことが目的である。この前提が、以降のモデル選択と依頼文の書き方を規定する。

**適用対象は「やり直しコストが高い成果物」に絞る。** 設計メモ・提案書・ADR・アーキテクチャ判断・リリース前のコード・セキュリティ境界のように、後から誤りが判明したときの手戻りが大きいものが対象。独立プロセスの起動は時間もトークンも消費するため、日常の小さな差分すべてに機械的に掛けない。

**次のものは本スキルの対象ではない。**

- 型チェック・lint・テストで機械的に検出できる欠陥（`verification-loop` / `done` の担当）
- 「動くかどうか」の確認（実行して確かめる方が速く確実）
- 呼び出し元がすでに結論を持っており、同意だけを求めている確認

**対象外だと判断したときは、ユーザーがそれを自覚しているかに関わらず、見立てと代替案（型チェック・lint・テストの実行、その場での目視確認など）を述べた上で、実行可否の判断をユーザーに返す。** 黙って実行するのも、黙って断るのもしない。ユーザーが承知の上で実行を求めた場合はそのまま実行する。

**依頼のスタンスは「改善提案の収集」ではなく「懐疑的検証」に置く。** 「良くしてほしい」と投げると一般論が返る。**「この成果物には問題がある前提で、反証を試みてほしい」**と設定し、各論点に判定と根拠をセットで返させる（具体的な依頼文の書き方は「推奨prompt contract」を参照）。

## ガードレール（必須・逸脱禁止）

1. **read-only 厳守**: 必ず `-s read-only` で起動する。レビュー用 Codex が作業ツリーへ変更を加えることは許されない（実行後に `git status` で汚染がないか確認し、汚染があれば即報告する）
2. **ネスト起動禁止**: レビュー用 Codex に別の `codex exec` / `claude -p` / review 系 skill を起動させない（依頼文に再帰防止文を必ず含める。後述）
3. **書き込み系操作の禁止**: commit / push / PR 作成 / GitHub コメント / Issue 作成・更新をレビュー用 Codex に行わせない。結果はテキストで返させ、扱いは呼び出し元が判断する
4. **明示指定の尊重**: ユーザーが effort / model を明示した場合、自動判定で上書きしない（上げるのも下げるのも禁止）。**明示指定とはモデルIDまたは effort レベル名（`low`/`medium`/`high` 等）を挙げたものを指す。** 「しっかり」「念のため」「軽く」のようなレベル名を伴わない強調表現は明示指定として扱わず、自動判定の入力（依頼内容の複雑度の手がかり）として扱う

Codex CLI を read-only サンドボックスで実行し、コードベースを分析する。
`approval: never` で動作するため、ユーザーの承認プロンプトは発生しない。

## モデルと effort（2026-07 時点）

**このセクションが本スキル内のモデル ID・effort・既定値の唯一の定義元。** 以降のコマンド例に埋まっているモデル名・effort はここの既定値の写しであり、モデル状況が変わったら本セクション・コマンド例・frontmatter description をあわせて更新する。

### モデル（GPT-5.6 系・3ティア構成）

| モデル | 位置づけ |
|--------|---------|
| `gpt-5.6-terra` | **既定**。品質/コストのバランス型。実装済みコードのレビューに十分 |
| `gpt-5.6-sol`   | 昇格先。設計そのものが対象・不確実性が高い場合に限って選ぶ |
| `gpt-5.6-luna`  | 高速・低コスト。クイックチェック向け |

`~/.codex/config.toml` の既定に依存せず、必ず `-m` でモデルを明示固定する（自己文書化のため）。

**既定は `gpt-5.6-terra` + `high`。** 本スキルの目的は独立した観点の持ち込みであって、モデルの推論力で欠陥を掘り出すことではない（「レビューの目的」参照）。**詳細設計が済んでいて実装内容に一定の信頼がある対象**——設計どおりに実装されたコード、既知パターンの適用、レビュー目的が「実装者に無い観点の提案」であるもの——は既定のままで扱う。上位モデルは所要時間が伸び、多くのレビューではその追加時間に見合う質の差が出ない。

**次のいずれかに当てはまるときのみ `gpt-5.6-sol` へ昇格する。** 依頼を受けた時点で判断できる条件に限る。

- **プランニング段階**のレビュー（設計方針・アーキテクチャ選定・ADR・提案書など、実装前の判断そのものが対象）
- 詳細設計は済んでいるが**不確実性が高い**（前例の無い方式、外部仕様への依存が大きい、想定外の失敗モードが読めない）
- **拠り所となる詳細設計が無い**まま複雑な実装が積み上がっている（レビューが実装の検証ではなく、設計の再構築から始まる）

**判断軸は対象の題材ではなく、難所が設計で片付いているかどうか。** 認証・並行処理・データ整合性といった領域に触れること自体は昇格理由にならない。詳細設計どおりに実装された認証コードのレビューは既定の `gpt-5.6-terra` で扱う。

**昇格するときは、その理由を一言添えてから起動する**（所要時間が伸びるため）。複数の条件に該当する場合は該当したものを全て挙げる。上記に当てはまらない限り既定を維持し、「念のため強いモデルで」という理由で昇格しない。

**事後の昇格（重要）。** 深さが足りるかどうかは起動時には判定できないため、**判断は結果を見た呼び出し元に渡す**。`terra` の結果が一般論に留まる・`path:line` の裏付けが薄い・懸念していた論点に触れていない場合は、その結果をそのまま採用しない。**effort を上げるのではなく、対象スコープを絞り、観点を具体化した上で `gpt-5.6-sol` で再実行する。** 再実行したことと、`terra` の結果との差分を呼び出し元へ報告する。

**既定モデルでの結果を報告するときは、判断材料と選択肢を添える（必須）。** 報告の最後に、(1) scope statement のうち未検査のまま残った範囲に重要なものがあるか、(2) 「このまま採用する」か「スコープを絞って `gpt-5.6-sol` で再実行する」かの選択、を明示して呼び出し元に問う。黙って結果だけ返すと、浅い1回で打ち切られたのか十分だったのかが呼び出し元から区別できない。

**昇格のための再実行では `codex exec resume` を使わない（新規 session で起動する）。** resume は元 session の結論・探索経路・見落としをそのまま引き継ぐため、「1回目が見落とした観点」を拾う目的には最も効かない。resume が適切なのは、**同じ結論の深掘り・根拠の確認・反論の提示**であって、別の視点を得るための再レビューではない（用途は後述の「同じレビューへの追加質問」を参照）。

**ユーザーがモデルを明示した場合はガードレール4が優先する。** 上記の自動判定で上書きしない。

### Effort レベル

**effort が明示されない場合は、依頼内容の複雑度から自動判定する。既定は `high`。** 通常のコードレビューもアーキテクチャ分析もこの既定 `high` で行う。クイックチェックなど明らかに軽微な依頼に限り `medium` / `low` に下げてよい。effort が明示された場合は必ずそれに従う。

**`xhigh` 以上（`xhigh` / `max` / `ultra`）は使わない。** effort を上げるほど精度が上がるわけではなく、過剰な探索と推論でレビュー結論の質が落ちる場合がある。自動判定でも既定でも選ばない。深さが足りないと感じたときは effort を上げるのではなく、**対象スコープを絞る・観点を具体化する・複数回に分ける**方向で対処する。

下表は各レベルの「深さの目安」であって、タスク種別から機械的にレベルを引くための対応表ではない。**未指定時は上のルール（既定 `high`）が優先**し、下表は「既定からどこまで降格してよいか」の判断材料として使う。

| レベル | オプション | 目安（既定 `high` 基準） |
|--------|-----------|------|
| `low`    | `-c model_reasoning_effort="low"`    | ごく軽微・クイックな確認のみ（最速） |
| `medium` | `-c model_reasoning_effort="medium"` | 小さな差分・限定スコープの軽いレビュー |
| `high`   | `-c model_reasoning_effort="high"`   | 通常のコードレビュー〜複雑な設計判断・アーキテクチャ分析・難解なバグ（**既定・自動判定の上限**） |
| `xhigh` / `max` / `ultra` | （使わない） | **選択しない。** 精度向上に結び付かず、時間とコストだけが増える。`ultra` はサブエージェント並列で使用量が急増する警告もある |

**自動判定の上限は `high`。** ユーザーが `xhigh` 以上を明示的に要求した場合のみ、ガードレール4に従って尊重する（その際は精度が上がらない可能性を一度添える）。指定してエラーになったら `high` へフォールバックしてその旨を報告する。

## 実行前の確認

会話の文脈からわかる場合は確認を省略して構わない。不明な場合のみ確認する。

| 項目 | デフォルト |
|------|-----------|
| 依頼内容 | 必須。何をレビュー・調査してほしいか。 |
| 対象ディレクトリ | カレントディレクトリ (`pwd`) |
| モデル | `gpt-5.6-terra`。設計そのものが対象・高不確実性・拠り所の設計が無い場合のみ `gpt-5.6-sol` へ昇格。明示指定があればそれを優先 |
| Effort レベル | 自動判定（既定 `high`、軽微な依頼のみ `medium`/`low`。`xhigh` 以上は使わない） |

`<依頼内容>` には、ユーザーの依頼をその意図を保ったまま、レビュー対象スコープ（全体／特定ファイル・ディレクトリ／差分の範囲）と観点を含む簡潔な指示へ整形して埋める。差分レビューでは対象（未コミット／ブランチ差分／コミット）を明示し、未指定なら作業ツリーの差分（ステージ済み・未ステージ・untracked を含む）を既定とする。docsレビューでは`git diff --name-only`でREADME等を含む実対象を列挙してpromptへ入れる。

重要: 汎用 `codex exec` でレビューを依頼する場合、起動先 Codex がさらに `codex-review` / `claude-review` skill や `codex exec` / `claude -p` を起動して再帰することがある。`<依頼内容>` の先頭または末尾に必ず次の趣旨を明示する。

```text
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.
```

`codex exec review --uncommitted` / `--base` / `--commit` はカスタム指示を渡せないため、この再帰防止文は付けられない。その場合でも、呼び出し元が `codex exec review` を直接実行しているので nested reviewer のリスクは低い。

## 実行コマンド

### 汎用分析・レビュー

プロンプト本文は必ず **single-quoted heredoc** で渡す。Markdown のバッククォート、`$VAR`、`$(...)`、型注釈、引用符を含むレビュー依頼を `codex exec ... "..."` に直接入れると、shell がコマンド置換や変数展開として解釈してプロンプトを壊す。

```bash
codex exec \
  -s read-only \
  -m gpt-5.6-terra \
  -C /path/to/project \
  -c model_reasoning_effort="<level>" \
  "$(cat <<'CODEX_REVIEW_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.

<依頼内容>
CODEX_REVIEW_PROMPT
)" < /dev/null
```

- `-s read-only`: ファイル変更・危険なコマンドをサンドボックスで禁止
- `-m gpt-5.6-terra`: 品質優先の既定modelを明示固定（config既定に依存しない）
- `-C <project_dir>`: 分析対象の作業ルートを指定
- `-c model_reasoning_effort`: 推論深度の指定（既定 `high`、自動判定。`xhigh` 以上は使わない）
- `< /dev/null`: **必須**。明示promptに加えて端末stdinを待つハングを防ぐ。`Reading additional input from stdin...` が表示されても、redirect済みなら正常に先へ進む

**重要**: プロンプト本文（heredoc 内）に `$HOME` などの変数を書かない。single-quoted heredoc では展開されず、リテラル文字列 `$HOME` のままレビュー先へ渡る。対象パスは heredoc の外にある `-C` で渡し、本文では「`-C` で指定した作業ルート」と参照するか、展開済みの絶対パスを書く。
**重要**: heredoc delimiter は必ず引用する（例: `<<'CODEX_REVIEW_PROMPT'`）。引用しない `<<EOF` は shell 展開を許すため使わない。プロンプト内に delimiter と同じ行が含まれる場合だけ、別の一意な delimiter 名に変える。
**重要**: Claude Code 上ではこのコマンドを **`run_in_background: true` で起動する**（理由と手順は後述の「実行時間と中断の防止」を参照）。既定 `high` でも対象が大きければ処理は数分〜数十分かかりうるが、背景実行なら Bash の10分上限で kill されず、呼び出し元もブロックしない。

### diff / commit / ブランチの差分レビュー

**差分レビューでも既定は上の汎用 `codex exec` を使う。** 依頼文に対象（未コミット／ブランチ差分／特定コミット）を明記し、起動先 Codex に `git diff` 等の読み取り系コマンドで取得させる。

理由: `codex exec review` は `[PROMPT]` と相互排他でカスタム指示を渡せないため、**懐疑的スタンス・網羅性要求・scope statement 要求・BASIS ラベルといった prompt contract を一切注入できない**。本スキルの目的（実装者の視野に無い観点を、判定と根拠付きで得る）が差分レビューにだけ効かなくなる。

対象の範囲は依頼文で言い切る。「未コミット差分」は解釈が割れるため、**ステージ済み・未ステージ・untracked のどれを含むかまで書く**（既定は3つとも含める）。**ブランチ差分（`git diff main` 等）でも同じく、作業ツリーの未コミット分を含めるかを明記する**（既定は含める＝そのブランチの現在の内容全体を見る）。

```text
対象は作業ツリーの未コミット差分です。ステージ済み・未ステージ・untracked の新規ファイルをすべて含みます
（git status と git diff / git diff --staged で取得してください）。
この差分には問題がある前提で反証を試みてください。
```

`codex exec review` は**ユーザーが明示的に要求した場合のみ**使う。その場合は prompt contract が効かないことを一言伝える。

```bash
# 未コミットの変更をレビュー
codex exec review -m gpt-5.6-terra -c model_reasoning_effort="high" --uncommitted < /dev/null

# 特定のブランチとの差分をレビュー
codex exec review -m gpt-5.6-terra -c model_reasoning_effort="high" --base main < /dev/null

# 特定コミットをレビュー
codex exec review -m gpt-5.6-terra -c model_reasoning_effort="high" --commit COMMIT_SHA < /dev/null
```

上の各コマンドにも末尾へ `< /dev/null` を付ける。汎用 `exec` と `exec review` のどちらもmodelとeffortを必ず明示し、config既定へ委ねない。

**重要**: `codex exec review` は `-c model_reasoning_effort` を省くと `~/.codex/config.toml` の既定（通常 `medium`）で動き、**既定 `high` が効かない**。自動判定した effort（未指定なら既定 `high`）を確実に反映するため、`-c model_reasoning_effort="<level>"` を必ず明示すること。diff レビューも長時間化しうるため、Claude Code 上では同様に `run_in_background: true` で起動する。

**重要**: `[PROMPT]` と `--uncommitted`/`--base`/`--commit` は相互排他。`--help` では同時指定可能に見えるが、実際に実行すると `error: the argument '[PROMPT]' cannot be used with '--uncommitted'` で失敗する（v0.144.1 でも継続）。diff レビューにカスタム指示を組み合わせることはできない。カスタム指示が必要な場合は汎用の `codex exec` コマンドを使うこと。

### 実行例

```bash
# カレントプロジェクトのセキュリティレビュー（既定 high）
codex exec \
  -s read-only \
  -m gpt-5.6-terra \
  -C $HOME/my-project \
  -c model_reasoning_effort="high" \
  "$(cat <<'CODEX_REVIEW_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.

認証周りのセキュリティ上の問題点を洗い出してください
CODEX_REVIEW_PROMPT
)" < /dev/null

# 未コミット変更のレビュー（カスタム指示なし、既定 high）
codex exec review -m gpt-5.6-terra -c model_reasoning_effort="high" --uncommitted < /dev/null
```

### 複数repo横断レビュー

`-C` を対象repo群の共通親へ向け、`--skip-git-repo-check` を付ける。promptには共通親からの相対pathで対象を明示列挙し、対象外repoを探索させない。

```bash
codex exec -s read-only -m gpt-5.6-terra \
  -c model_reasoning_effort="high" \
  -C /path/to/common-parent --skip-git-repo-check \
  "$(cat <<'CODEX_REVIEW_PROMPT'
You are the reviewer. Inspect only these targets:
- repo-a/path/to/file
- repo-b/path/to/file
Do not invoke nested reviewers. Use read-only commands and return findings directly.
CODEX_REVIEW_PROMPT
)" < /dev/null
```

### 同じレビューへの追加質問

出力headerの `session id:` を保存する。findingの深掘りや反論確認は新規レビューを起動せず、同じsessionをresumeする。`--ephemeral` を付けた実行はresumeできない。

```bash
codex exec resume SESSION_ID \
  -m gpt-5.6-terra \
  -c model_reasoning_effort="high" \
  "$(cat <<'CODEX_REVIEW_FOLLOWUP'
Finding 2を、根拠となるpath:lineと成立条件を示して詳しく説明してください。
CODEX_REVIEW_FOLLOWUP
)" < /dev/null
```

resumeは元sessionのsandboxと作業文脈を引き継ぐ。現行CLIではresume自体に`-s`/`-C`を足さない。
`session id:` を取得できない場合は推測したIDや`--last`で別sessionへ接続せず、resume不能と報告する。

## 実行時間と中断の防止

レビューは対象が大規模なほど時間がかかる。既定の `gpt-5.6-terra` + `high` は多くの場合**数分程度**で完了するが、`gpt-5.6-sol` へ昇格した場合や対象が大規模な場合は**数十分**に達しうる。いずれも正常で、出力が無い間も停止やハングではなく推論を継続している。**長時間化を理由に kill・キャンセル・再実行をしてはならない。** 呼び出し元（人間・上位エージェントを問わず）に中断不要だと伝え、気長に完了を待つ。

**まず実行ホストで分岐する**: Claude Code 上なら背景実行（手順1〜4）。`run_in_background` を持たないホスト（Codex/Cursor 等。自分が Codex として動作している場合を含む）は手順1〜4ではなく**手順5の foreground フォールバック**を使う。

1. **`run_in_background: true` で起動する（Claude Code での本筋）**
   Claude Code 上では Bash ツールの `run_in_background` を使う。foreground と違い10分上限で kill されず、呼び出し元をブロックしない。完了時に Claude Code がエージェントを自動再呼び出しし、出力も取得できる。
2. **起動直後に呼び出し元へ予告する**（背景起動でターンが即 yield するので、この一言を必ず出す）
   > 「codex-review をバックグラウンドで開始しました。レビューには数分〜数十分かかる場合があります。応答が無くても処理は継続中（ハングではありません）なので、中断せず気長にお待ちください。完了時に結果を報告します。」
3. **完了通知で再呼び出しされたら報告する**
   背景出力は数百KBになることがあるため、ファイル全体を`Read`せず`tail`で末尾から確認する。論点位置は`rg -n "VERDICT|must-fix" <output>`で特定する。最終回答は最後の`codex`行の後にあり、`tokens used`後に同じ本文が再掲される場合があるため、重複を二重報告しない。
4. **待機中は背景タスクを kill・キャンセル・再起動しない。** `high`で10分超・10万token級、または数十分無出力でも正常になり得る。`Reading additional input from stdin...` はredirect済みなら待機を意味しない。`ERROR rmcp::transport::worker: ... Auth(AuthorizationRequired)` はheadlessで対話認証MCPを起動できないノイズであり、レビュー本文が出ていれば失敗扱いしない。
5. **背景実行を持たないホスト（Codex/Cursor 等）でのフォールバック**
   foreground で実行し、ホストの実行タイムアウトを可能な限り長く確保する（Claude Code の Bash 相当なら上限 `600000`ms=10分）。foreground はブロックするため発話窓は「実行直前」のみ。**起動直前に**次の foreground 用の予告を出す（手順2の文言は「バックグラウンドで開始」を含み foreground では不正確になるため、そのまま流用しない）。
   > 「これからレビューを実行します。完了まで数分〜数十分かかる場合があります。応答が無くても処理は継続中（ハングではありません）なので、中断せず気長にお待ちください。」

   結果は標準出力（戻り値）として直接返るため、背景用の出力ファイル `Read` / `BashOutput` は使わず、その stdout を下記「結果の整理と報告」に従って報告する。ホストのタイムアウト上限が数十分の実行に足りず kill された場合も盲目的に再実行せず、対象を絞る（特定ファイル/ディレクトリ）か、effort を一段下げる（high→medium）。
6. **補足（実行モードに依らない）**: 背景実行は10分の foreground 上限に縛られないが「無制限」ではない。巨大リポジトリのレビューが背景でも長すぎる場合は、同様に対象の絞り込みや effort 降格（high→medium）で対処する。
7. **時間超過への対処でも、ガードレール4（明示指定の尊重）が優先する。** ユーザーが effort / model を明示している場合、時間超過を理由に自動で降格してはならない。まず対象スコープの絞り込みで対処し、それでも収まらなければ降格の可否をユーザーへ確認する。明示指定が無い場合のみ、自動判定の範囲として降格してよい。

## 結果の整理と報告

Codex の出力には先頭にメタ情報ヘッダー（バージョン・モデル・サンドボックス種別など）が含まれる。
ヘッダーは除外し、本文の分析結果のみをユーザーに伝える。レビュー指摘は結論ではなく仮説であり、採用前に必ず該当path:lineと実装を自分で確認する。必要であれば以下の観点で整理する:

1. **要約**: 主な発見事項（3点以内）
2. **詳細**: 具体的な指摘（優先度順）
3. **推奨対応**: 改善提案と実装方針
4. **補足**: 追加調査が必要な項目

### 推奨prompt contract

- **懐疑的スタンスを冒頭で設定する。** 「改善点を教えて」ではなく「この成果物には問題がある前提で反証を試みてほしい」と書く。前者は一般論を、後者は判定と根拠を返させる
- **既知の欠陥ではなく、こちらが見落としている観点を求めていると明示する。** 「型チェック・lint・テストで検出できるものは対象外。設計判断・前提・失敗モードなど、実装者の視野に入っていない可能性がある観点を優先する」
- 論点を番号付きで列挙し、各論点に `VERDICT: AGREE / AGREE-WITH-CAVEAT / DISAGREE / RISK`、根拠、代替案を要求する
- 「見落とされている論点」を重要度順に要求する
- **見ていない範囲を返させる。** 「今回検査しなかったファイル・観点・前提」を scope statement として必ず出させる。無言の未検査を「問題なし」と誤読しないため。事後昇格の判断材料としても必須（「モデルと effort」の handoff 参照）
- 遠慮不要と明記し、懸念している弱点を具体的に列挙する
- 各findingに`path:line`を必須化する
- docsレビューでは契約定義・manifest・package設定など対象実装を列挙し、文書の現在形の主張と実装を突合させる。docs整合だけなら`medium`を選べる

**必要性の根拠と単純案を明示的に要求する（重要）。** 細部の指摘は精度が高く抜け漏れも少ない一方で、改善提案が overengineering へ寄ることがある。次の2点を依頼文へ必ず入れる。

- **各提案に必要性の根拠をラベルさせる。** `BASIS: OBSERVED`（コードやテストで観測された事実・再現する不具合）/ `CURRENT-THREAT`（現在の脅威モデル・受入条件・規制で要求される）/ `REAL-DEMAND`（実在する利用者・ユースケース）/ `SPECULATIVE`（将来こうなるかもしれないという仮説）のいずれかを付けさせる。`SPECULATIVE` は提案の削除ではなく分離が目的で、受け取り側の判断材料にする。
- **より単純な代替案を併記させる。** 「同じ問題を解決できる、より少ない機構・抽象・依存で済む案を必ず1つ挙げ、その案を採らない理由を示す」。単純案が示せない提案は、必要性の再確認対象にする。

### 受け取り側の検証規律

1. 指摘を機械的に採用・棄却せず、該当箇所と成立条件を確認する。
2. **引用の実在を確認する。** 提示された `path:line` とコード断片が実際にその内容で存在するかを、採用前に必ず自分で突き合わせる。行番号のずれ、古い内容の引用、存在しないシンボルは珍しくない。実在しない引用に依存した指摘は、結論が正しく見えても採用しない。
3. **scope statement を読み、未検査範囲を明示的に扱う。** 未検査の観点が重要なら、別途レビューするか自分で確認する。返答に無いことを「問題が無いこと」の根拠にしない。
4. **`BASIS: SPECULATIVE` の提案は既定で採用しない。** 「security上望ましい」「将来必要になりそう」「一般にベストプラクティス」だけを根拠にした提案は、具体的な資産・攻撃経路・実需・観測された負荷を特定できるまで保留する。判定基準は `ai-native-engineering` skill の「投機的な抽象化を見分ける」「需要を待つ領域」「原則として先に決める判断」に従い、契約・境界の先決めと機構の先作りを分けて扱う。
3. **単純案が併記されている場合、まず単純案を検討する。** 提案側の複雑な案を既定にしない。
4. セキュリティ境界は`fail-closed`等のラベルで合格にせず、何と何を比較し、どこで強制しているかを実装まで辿る。
5. 修正後は元の検査に加え、secret/confusable等の関連scanを再実行する。レビュー修正そのものが新しい欠陥を作り得る。
6. 最後に`git status`を再確認し、レビュー用processによる汚染がないことを確認する。

## 注意事項

- `-s read-only` により書き込み系コマンドはサンドボックスで禁止される
- 汎用 `codex exec` のプロンプトを二重引用符で直書きしない。Markdown やコード片を含む場合は必ず single-quoted heredoc で渡す
- `codex exec review` は既定でサンドボックス（read-only 相当）で動作する。`-s`/`--sandbox` フラグは持たないため付けない（汎用 `codex exec` のみ `-s read-only` を明示）
- 適用対象は「やり直しコストが高い成果物」に絞る。型・lint・テストで検出できる欠陥や、実行すれば分かる動作確認には使わない
- モデル・effort の既定と昇格条件は「モデルと effort」セクションの定義に従う（config 既定に依存せず必ず明示する）
- モデルは既定 `gpt-5.6-terra`。設計そのものが対象・高不確実性・拠り所の設計が無い場合だけ `gpt-5.6-sol` へ昇格し、理由を一言添える。題材（認証・並行処理など）は昇格理由にならない
- 既定モデルでの結果報告には、未検査範囲と「採用する／スコープを絞って `gpt-5.6-sol` で再実行する」の選択を必ず添える
- 昇格のための再実行は新規 session で行い、`codex exec resume` で引き継がない（独立性が失われるため）。resume は同じ結論の深掘り専用
- 差分レビューも既定は汎用 `codex exec`。`codex exec review` は prompt contract を注入できないため、ユーザー明示時のみ使う
- `xhigh` / `max` / `ultra` は使わない。精度が上がらないため、深さ不足はスコープの絞り込みや観点の具体化で解決する
- 対象ディレクトリが Git リポジトリでない場合は `--skip-git-repo-check` を追加する
- `codex exec review` は CWD が Git リポジトリである必要がある
