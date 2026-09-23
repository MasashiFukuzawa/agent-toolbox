---
name: codex-review
description: >-
  Codex CLI の独立インスタンスでコードや差分を read-only レビューする。Codex・OpenAI・luna・sol・astra を明示した第三者レビューに使う。一般的なレビューや Claude 指定には使わない。「Codexに見てもらって」「lunaに見てもらって」「solに相談して」「astraに相談して」を正のトリガーとし、provider未指定の第三者レビューでは勝手に選ばず、ユーザーへ確認する。
---
# Codex Review スキル

このスキルは Claude Code / Codex / Cursor のどのホスト（エージェント）からも呼ばれる前提で書かれている。ホスト固有の起動と合流は「非同期実行と合流」の型分岐に従う。

**用途境界:** 本スキルは第三者レビュー専用で、`read-only` + モデルごとの既定 effort（`xhigh` 以上は使わない）。実装ワーカーとして Codex を委譲する場合は別のオーケストレーター手順を使い、`workspace-write` + 通常 `medium` とする。同じCLIでも権限とeffortが逆なので混用しない。

<!-- MIRROR:review-common BEGIN -->
## レビューの目的

本スキルの価値は**モデルの強さではなく独立性**にある。現セッションの文脈・前提・思い込みを共有しない別プロセスが、**実装者・設計者の視野に無い観点を持ち込む**ことが目的である。この前提が、以降のモデル選択と依頼文の書き方を規定する。

**適用対象は「やり直しコストが高い成果物」に絞る。** 設計メモ・提案書・ADR・アーキテクチャ判断・リリース前のコード・セキュリティ境界のように、後から誤りが判明したときの手戻りが大きいものが対象。独立プロセスの起動は時間もトークンも消費するため、日常の小さな差分すべてに機械的に掛けない。

**次のものは本スキルの対象ではない。**

- 型チェック・lint・テストで機械的に検出できる欠陥（verify コマンドと `done` の担当）
- 「動くかどうか」の確認（実行して確かめる方が速く確実）
- 呼び出し元がすでに結論を持っており、同意だけを求めている確認

**対象外だと判断したときは、ユーザーがそれを自覚しているかに関わらず、見立てと代替案（型チェック・lint・テストの実行、その場での目視確認など）を述べた上で、実行可否の判断をユーザーに返す。** 黙って実行するのも、黙って断るのもしない。ユーザーが承知の上で実行を求めた場合はそのまま実行する。

**依頼のスタンスは「改善提案の収集」ではなく「懐疑的検証」に置く。** 「良くしてほしい」と投げると一般論が返る。**「この成果物には問題がある前提で、反証を試みてほしい」**と設定し、各論点に判定と根拠をセットで返させる（具体的な依頼文の書き方は「推奨prompt contract」を参照）。
<!-- MIRROR:review-common END -->

## ガードレール（必須・逸脱禁止）

1. **read-only 厳守**: 必ず `-s read-only` で起動する。レビュー用 Codex が作業ツリーへ変更を加えることは許されない（実行後に `git status` で汚染がないか確認し、汚染があれば即報告する）
2. **ネスト起動禁止**: レビュー用 Codex に別の `codex exec` / `claude -p` / review 系 skill を起動させない（依頼文に再帰防止文を必ず含める。後述）
3. **書き込み系操作の禁止**: commit / push / PR 作成 / GitHub コメント / Issue 作成・更新をレビュー用 Codex に行わせない。結果はテキストで返させ、扱いは呼び出し元が判断する
4. **明示指定の尊重**: ユーザーが effort / model を明示した場合、自動判定で上書きしない（上げるのも下げるのも禁止）。**明示指定とは、モデルのティア名（`sol` / `astra` / `luna`。モデルIDや版付き名も含む）または effort レベル名（`low`/`medium`/`high` 等）を挙げたものを指す。** モデル名の解決は「モデル」の規則に従う。 「しっかり」「念のため」「軽く」のようなレベル名を伴わない強調表現は明示指定として扱わず、自動判定の入力（依頼内容の複雑度の手がかり）として扱う
5. **長時間未完了時のフォールバック**: 開始時に想定所要時間を伝える（既定の `gpt-6-luna` + `high` なら数分程度、`gpt-6-sol` / `gpt-6-astra` を選んだ場合や大規模対象では数十分）。実時刻の計測で40分たっても完了していなければ、状況を報告して「継続 or 中断して `claude-review` へ切替」をユーザーに提示する（勝手に放置も勝手に中断もしない。中断時は結果の部分回収を試みる）。**判定基準は「無出力」ではなく「未完了」である** — 推論中に本文が出ないのは常態であり、それ自体を失敗の根拠にしない

Codex CLI を read-only サンドボックスで実行し、コードベースを分析する。
`approval: never` で動作するため、ユーザーの承認プロンプトは発生しない。

## モデルと effort（2026-09 時点）

**このセクションが本スキル内のモデル ID・effort・既定値の唯一の定義元。** 以降のコマンド例に埋まっているモデル名・effort はここの既定値の写しであり、モデル状況が変わったら本セクション・コマンド例・`evals/evals.json` の `expected_output` をあわせて更新する。

### モデル（GPT-6 系・3ティア構成）

| モデル | 位置づけ |
|--------|---------|
| `gpt-6-luna`  | **既定**。高速・低コスト。実装済みコードのレビューに使う |
| `gpt-6-sol`   | 昇格先。コーディングと日常作業の主力モデル。設計そのものが対象・不確実性が高い場合に限って選ぶ |
| `gpt-6-astra` | **ユーザー明示時のみ**。最上位モデル。最も難しい作業向けで、通常レビューでは自動選択しない |

`~/.codex/config.toml` の既定に依存せず、必ず `-m` でモデルを明示固定する（自己文書化のため）。

**モデルの版は常にこの表の最新版を使う。** ユーザー指定から読み取るのはティア名（`sol` / `astra` / `luna`）だけで、版は無視する。`sol`・`gpt-5.6-sol` は `gpt-6-sol`、`luna`・`gpt-5.6-luna` は `gpt-6-luna`、`astra` は `gpt-6-astra` へ解決する。最新版に無いティア（`terra`）は既定の `gpt-6-luna` へ解決する。指定された版・ティアと異なるモデルを使う場合は、置き換えたことを起動前に一言伝える。

**既定は `gpt-6-luna` + `high`。** 本スキルの目的は独立した観点の持ち込みであって、モデルの推論力で欠陥を掘り出すことではない（「レビューの目的」参照）。**詳細設計が済んでいて実装内容に一定の信頼がある対象**——設計どおりに実装されたコード、既知パターンの適用、レビュー目的が「実装者に無い観点の提案」であるもの——は既定のままで扱う。上位モデルは所要時間が伸び、多くのレビューではその追加時間に見合う質の差が出ない。

**次のいずれかに当てはまるときのみ `gpt-6-sol` へ昇格する。** 依頼を受けた時点で判断できる条件に限る。

- **プランニング段階**のレビュー（設計方針・アーキテクチャ選定・ADR・提案書など、実装前の判断そのものが対象）
- 詳細設計は済んでいるが**不確実性が高い**（前例の無い方式、外部仕様への依存が大きい、想定外の失敗モードが読めない）
- **拠り所となる詳細設計が無い**まま複雑な実装が積み上がっている（レビューが実装の検証ではなく、設計の再構築から始まる）

**判断軸は対象の題材ではなく、難所が設計で片付いているかどうか。** 認証・並行処理・データ整合性といった領域に触れること自体は昇格理由にならない。詳細設計どおりに実装された認証コードのレビューは既定の `gpt-6-luna` で扱う。

**昇格するときは、その理由を一言添えてから起動する**（所要時間が伸びるため）。複数の条件に該当する場合は該当したものを全て挙げる。上記に当てはまらない限り既定を維持し、「念のため強いモデルで」という理由で昇格しない。

**事後の昇格（重要）。** 深さが足りるかどうかは起動時には判定できないため、**判断は結果を見た呼び出し元に渡す**。既定モデルの結果が一般論に留まる・`path:line` の裏付けが薄い・懸念していた論点に触れていない場合は、その結果をそのまま採用しない。**luna の effort を上げるのではなく、対象スコープを絞り、観点を具体化した上で `gpt-6-sol` + `medium` で再実行する。** sol の結果も浅い場合は、同じ手順で sol の effort を一段上げる（「Effort レベル」参照）。再実行したことと、既定モデルの結果との差分を呼び出し元へ報告する。

**既定モデルでの結果を報告するときは、判断材料と選択肢を添える（必須）。** 報告の最後に、(1) scope statement のうち未検査のまま残った範囲に重要なものがあるか、(2) 「このまま採用する」か「スコープを絞って `gpt-6-sol` + `medium` で再実行する」かの選択、を明示して呼び出し元に問う。黙って結果だけ返すと、浅い1回で打ち切られたのか十分だったのかが呼び出し元から区別できない。

**昇格のための独立再レビューでは `codex exec resume` を使わない（新規 session で起動する）。** resume は元 session の結論・探索経路・見落としをそのまま引き継ぐため、「1回目が見落とした観点」を拾う目的には最も効かない。resume が適切なのは、**割り込みから同じレビューを完了させるrecovery、同じ結論の深掘り、根拠の確認、反論の提示**である。

**`gpt-6-astra` はユーザーが「astra で」「astraに相談して」のように astra を明示した場合のみ使用する。** 自動選択は絶対にしない。

**ユーザーがモデルを明示した場合はガードレール4が優先する。** 上記の自動判定で上書きしない。

### Effort レベル

**effort が明示されない場合は、モデルごとの既定値を使う。** effort が明示された場合は必ずそれに従う。

| モデル | 既定 | 調整 |
|--------|------|------|
| `gpt-6-luna`  | `high` | 明らかに軽微なクイックチェックだけ `medium` に下げてよい。`low` は極端に精度が落ちるため使わない。`xhigh` には上げず、深さが足りなければ `gpt-6-sol` `medium` へ切り替える |
| `gpt-6-sol`   | `medium` | `low` は `gpt-6-luna` `high` を下回るため使わない。`medium` の結果が浅かった再実行では `high`。`high` は相当難度・重要度の高い対象に限り、理由を一言添えて使う |
| `gpt-6-astra` | `low` | 同じモデルの `low` の結果が浅かった再実行では `medium`。`high` は誤りの手戻りが極めて大きく、かつ `medium` でも足りない相当難度・重要度の高い対象に限る |

**深さが足りないときは、同じモデルの effort を上げる前に上位モデルへ切り替える。** 自動で進める段階は `gpt-6-luna` `high` → `gpt-6-sol` `medium` →（限定的に）`gpt-6-sol` `high` とする。どの段でも、対象スコープの絞り込みと観点の具体化を併用する。

| レベル | オプション |
|--------|-----------|
| `low`    | `-c model_reasoning_effort="low"`    |
| `medium` | `-c model_reasoning_effort="medium"` |
| `high`   | `-c model_reasoning_effort="high"`   |

**`xhigh` 以上（`xhigh` / `max` / `ultra`）は使わない。** effort を上げるほど精度が上がるわけではなく、過剰な探索と推論でレビュー結論の質が落ちる場合がある。自動判定でも既定でも選ばない。`ultra` はサブエージェント並列で使用量が急増する警告もある。ユーザーが `xhigh` 以上を明示的に要求した場合のみ、ガードレール4に従って尊重する（その際は精度が上がらない可能性を一度添える）。指定してエラーになったら `high` へフォールバックしてその旨を報告する。

## 実行前の確認

会話の文脈からわかる場合は確認を省略して構わない。不明な場合のみ確認する。

| 項目 | デフォルト |
|------|-----------|
| 依頼内容 | 必須。何をレビュー・調査してほしいか。 |
| 対象ディレクトリ | カレントディレクトリ (`pwd`) |
| モデル | `gpt-6-luna`。設計そのものが対象・高不確実性・拠り所の設計が無い場合のみ `gpt-6-sol` へ昇格。`gpt-6-astra` は明示時のみ。明示指定があればそれを優先 |
| Effort レベル | モデルごとの既定（luna は `high`、sol は `medium`、astra は `low`）。`xhigh` 以上は使わない |

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

プロンプト本文は必ず **single-quoted heredoc** で渡す。Markdown のバッククォート、`$VAR`、`$(...)`、型注釈、引用符を含むレビュー依頼を `codex exec ... "..."` に直接入れると、shell がコマンド置換や変数展開として解釈してプロンプトを壊す。以下はCLI payloadであり、単独で直実行しない。必ず「durable recovery record」のwrapperがrun directory作成、record更新、process identity記録、終了status記録を行う内側で実行する。

```bash
codex exec \
  --json \
  -o "<final_output>" \
  -s read-only \
  -m gpt-6-luna \
  -C /path/to/project \
  -c model_reasoning_effort="<level>" \
  "$(cat <<'CODEX_REVIEW_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.

<依頼内容>
CODEX_REVIEW_PROMPT
)" < /dev/null > "<event_log>" 2> "<stderr_log>"
```

- `-s read-only`: ファイル変更・危険なコマンドをサンドボックスで禁止
- `-m gpt-6-luna`: 既定modelを明示固定（config既定に依存しない）
- `-C <project_dir>`: 分析対象の作業ルートを指定
- `-c model_reasoning_effort`: 推論深度の指定（モデルごとの既定。`xhigh` 以上は使わない）
- `< /dev/null`: **必須**。明示promptに加えて端末stdinを待つハングを防ぐ。`Reading additional input from stdin...` が表示されても、redirect済みなら正常に先へ進む
- `--json > <event_log>`: リポジトリ外の既知pathへevent streamを永続化し、最初の`thread.started`からsession IDを回収可能にする
- `-o <final_output>`: リポジトリ外の既知pathへ最終本文を保存し、完了済みreviewではresumeせず回収できるようにする

**重要**: プロンプト本文（heredoc 内）に `$HOME` などの変数を書かない。single-quoted heredoc では展開されず、リテラル文字列 `$HOME` のままレビュー先へ渡る。対象パスは heredoc の外にある `-C` で渡し、本文では「`-C` で指定した作業ルート」と参照するか、展開済みの絶対パスを書く。
**重要**: heredoc delimiter は必ず引用する（例: `<<'CODEX_REVIEW_PROMPT'`）。引用しない `<<EOF` は shell 展開を許すため使わない。プロンプト内に delimiter と同じ行が含まれる場合だけ、別の一意な delimiter 名に変える。
**重要**: このコマンドは**呼び出し元を解放する形で起動する**（起動と合流の型は後述の「非同期実行と合流」を参照）。既定の effort でも対象が大きければ処理は数分〜数十分かかりうるが、背景実行なら Bash の10分上限で kill されず、呼び出し元もブロックしない。
**重要**: `--ephemeral`は付けない。`event_log`の最初の`thread.started.thread_id`をsession IDとして、最初に取得可能になった時点で読む。通知型では通常完了前に本文を覗かないが、割り込み復旧では記録済みevent logのmetadataを読んでよい。下記「durable recovery record」に従い、session専用run directory・event log・final output・stderr log・lifecycle recordをCLI起動前に作る。すべてのpathを引用し、既存fileを再利用しない。

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
codex exec review --json -o "<final_output>" -m gpt-6-luna -c model_reasoning_effort="high" --uncommitted < /dev/null > "<event_log>" 2> "<stderr_log>"

# 特定のブランチとの差分をレビュー
codex exec review --json -o "<final_output>" -m gpt-6-luna -c model_reasoning_effort="high" --base main < /dev/null > "<event_log>" 2> "<stderr_log>"

# 特定コミットをレビュー
codex exec review --json -o "<final_output>" -m gpt-6-luna -c model_reasoning_effort="high" --commit COMMIT_SHA < /dev/null > "<event_log>" 2> "<stderr_log>"
```

上の各コマンドにもstdin redirect・event log・final outputを付ける。`exec review`はscope statementを要求できないため、完了判定はprocessの正常終了とfinal outputの存在で行う。汎用`exec`と`exec review`のどちらもmodelとeffortを必ず明示し、config既定へ委ねない。

**重要**: `codex exec review` は `-c model_reasoning_effort` を省くと `~/.codex/config.toml` の既定（通常 `medium`）で動き、**モデルごとの既定 effort が効かない**。選んだ effort（未指定ならモデルごとの既定）を確実に反映するため、`-c model_reasoning_effort="<level>"` を必ず明示すること。diff レビューも長時間化しうるため、Claude Code 上では同様に `run_in_background: true` で起動する。

**重要**: `[PROMPT]` と `--uncommitted`/`--base`/`--commit` は相互排他。`--help` では同時指定可能に見えるが、実際に実行すると `error: the argument '[PROMPT]' cannot be used with '--uncommitted'` で失敗する（v0.144.1 でも継続）。diff レビューにカスタム指示を組み合わせることはできない。カスタム指示が必要な場合は汎用の `codex exec` コマンドを使うこと。

### 実行例

```bash
# カレントプロジェクトのセキュリティレビュー（既定 high）
codex exec \
  --json \
  -o "<final_output>" \
  -s read-only \
  -m gpt-6-luna \
  -C $HOME/my-project \
  -c model_reasoning_effort="high" \
  "$(cat <<'CODEX_REVIEW_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.

認証周りのセキュリティ上の問題点を洗い出してください
CODEX_REVIEW_PROMPT
)" < /dev/null > "<event_log>" 2> "<stderr_log>"

# 未コミット変更のレビュー（カスタム指示なし、既定 high）
codex exec review --json -o "<final_output>" -m gpt-6-luna -c model_reasoning_effort="high" --uncommitted < /dev/null > "<event_log>" 2> "<stderr_log>"
```

### 複数repo横断レビュー

`-C` を対象repo群の共通親へ向け、`--skip-git-repo-check` を付ける。promptには共通親からの相対pathで対象を明示列挙し、対象外repoを探索させない。

```bash
codex exec --json -o "<final_output>" -s read-only -m gpt-6-luna \
  -c model_reasoning_effort="high" \
  -C /path/to/common-parent --skip-git-repo-check \
  "$(cat <<'CODEX_REVIEW_PROMPT'
You are the reviewer. Inspect only these targets:
- repo-a/path/to/file
- repo-b/path/to/file
Do not invoke nested reviewers. Use read-only commands and return findings directly.
CODEX_REVIEW_PROMPT
)" < /dev/null > "<event_log>" 2> "<stderr_log>"
```

### 同じレビューへの復旧・追加質問

findingの深掘りや反論確認は新規レビューを起動せず、記録した同じsessionをresumeする。中断・回収失敗からの復旧も同じコマンドを使うが、先に元processが終了していることを確認する。

```bash
codex exec resume SESSION_ID \
  --json \
  -o "<followup_output>" \
  -m gpt-6-luna \
  -c model_reasoning_effort="high" \
  -c sandbox_mode="read-only" \
  "$(cat <<'CODEX_REVIEW_FOLLOWUP'
Finding 2を、根拠となるpath:lineと成立条件を示して詳しく説明してください。
CODEX_REVIEW_FOLLOWUP
)" < /dev/null > "<followup_event_log>" 2> "<followup_stderr_log>"
```

状態遷移・ID特定・失敗時の扱いは後述の「中断・回収失敗からの復旧」を正とする。現行CLIではresume自体に`-s`/`-C`が無いため足さず、`sandbox_mode`をconfig overrideで明示する。
`<followup_output>`・`<followup_event_log>`・`<followup_stderr_log>`もrecovery recordへ追記し、既存出力を上書きしない。

<!-- MIRROR:review-async BEGIN -->
## durable recovery record

wrapperの最小schemaと更新手順は[`references/durable-run-record.md`](references/durable-run-record.md)を正とする。

ホストハンドルだけをrecovery recordにしてはならない。起動ごとに新しいrun UUIDを作り、ホストの永続state root配下の`reviews/<run_uuid>/`を専用run directoryにする。場所は一時directoryやrepo内ではなく、再開後も残る既知のrootとし、起動前にrun UUIDと絶対pathをユーザーへ通知する。別runのdirectoryやfileは再利用しない。

run directoryには少なくとも`record.json`、event/stdout、stderr、final outputを置く。`record.json`はrun UUID・provider session ID・cwd・対象root/path・model・effort・各出力path・host handle・process identity（PIDだけでなく起動時刻等の照合値）・`prepared|running|exited`・exit statusを含む。CLIを包むwrapperが、起動直前に`running`、終了直後に`exited`とstatusを書き、同じdirectory内の一時fileを`rename`して原子的に更新する。stderrも専用fileへ保存する。

割り込み後は、通知済みrun UUIDからdirectoryを決定的に開く。`latest`、mtime、候補一覧では選ばない。`running`のままなら記録したprocess identityを照合し、生存中なら待機する。不在またはidentity不一致なら元processは終了済みとして扱い、eventとstderrからsession成立・失敗理由を確認する。これによりhost handleを失っても、session成立済みなら正確なIDでresumeでき、未成立なら診断後に新規起動できる。run UUIDもlocatorも失った場合だけ復旧不能としてstep 3へ進む。

## 非同期実行と合流

レビューは対象が大規模なほど時間がかかり、数分〜数十分に達しうる。出力が無い間も停止やハングではなく推論を継続している。**長時間化を理由に kill・キャンセル・再実行をしてはならない。**

**起動は必ず呼び出し元を解放する形で行い、合流はホストの合流機構に任せる。** 起動直後に、所要時間の見込みと「応答が無くても処理は継続中でありハングではない」ことを呼び出し元へ伝える。

| 型 | ホスト | 起動 | 合流 |
|----|--------|------|------|
| **通知型** | `run_in_background` を持つホスト | `run_in_background: true` で起動する | 完了時にホストがエージェントを自動再呼び出しする |
| **ハンドル型** | コマンド実行ツールが yield 時間とセッションハンドルを持つホスト | 短い yield 時間で起動し、ハンドルを保持して制御を取り戻す | **自分からハンドルを読みに行く** |
| **同期型** | どちらの機構も無いホスト | foreground で実行する | 戻り値をそのまま受け取る |

- **通知型**: 完了前に出力を見に行かない。通知の遅延は「いま実行中のツール呼び出しが終わるまで」で決まり、覗いても縮まらない。近リアルタイムに合流したいなら待ち時間の作業を短く刻む
- **ハンドル型**: 手元の作業が一段落した時点で、1回のツール呼び出し内でブロッキング読み取りを行って合流する。**放置すると永久に合流しない。** 実測の経過が40分を超えたらガードレール5に従う。ハンドルと出力先は控えておき、推測したハンドルやパスを読まない
- **同期型**: 待ち時間そのものが存在しないため「レビュー中の並行作業」は適用外。発話窓は実行直前のみで、そこで予告を出す。ホストの実行タイムアウトに収まらない場合も盲目的に再実行せず、対象を絞るか effort を一段下げる

**経過時間は必ず実時刻の差で測る。起点は起動成功（ハンドル・タスク ID・プロセスを確認できた時点）に置き、その時刻を記録する。** 反復回数 × 待ち時間の机上積算をしない — ホストによっては shell の `sleep` が無効化されており、待機ゼロで空回りしたループを「待った時間」と数えて、経過数分を数十分と誤認する。禁止するのは `sleep` と再読込を組み合わせた自作ポーリングであり、ホストが提供するブロッキング wait / read はそのまま使ってよい。**完了通知は実際の終了より先に届くことがある** — 通知型では通知を受けるまで出力を見ず、通知後に実終了を確認してから結果を回収する。確認は CLI が明示的に提供する完了マーカー（終了時に出すフッター行）またはプロセスの終了で行い、どちらも確認できないホストではホストが返す最終結果・終了ステータスを完了根拠とする（未定義のマーカーを推測して待ち続けない）。

**シェルレベルの detach（`nohup` / `setsid`）は使わない。** macOS には `setsid(1)` が無く、`nohup` ではプロセスグループ単位の kill を防げない。ホストの機構が無ければ同期型として扱う。

時間超過への対処でも、ガードレール4（明示指定の尊重）が優先する。ユーザーが effort / model を明示している場合、時間超過を理由に自動で降格しない。まず対象スコープの絞り込みで対処し、それでも収まらなければ降格の可否をユーザーへ確認する。

合流したら、進行中の作業よりレビュー結果の検証と報告を優先する。

## レビュー中の並行作業

**待ち時間に対象リポジトリを触る予定があるなら、スナップショット起動にする。** レビュー対象を不変オブジェクトとして固定してから起動すれば、呼び出し元はその後リポジトリを自由に扱える（手順は `references/review-snapshot.md`）。実ツリーと index には一切触れず、untracked を含む現在の状態を固定できる。依頼文では対象を「`HEAD~1..HEAD` の差分」と伝え、`.gitignore` されたファイルは含まれないことを添える。**この場合、ガードレール1の汚染チェックはスナップショット worktree 内で行う** — メインツリーは並行作業で当然変化するため、そちらを見ると恒常的に偽陽性になる。

スナップショットを取らずに起動した場合は、レビュー完了まで次の3つを変えない。

1. **レビュー対象ツリーと index** — 編集・commit・stash・branch 切替・依存更新をしない
2. **依頼が参照する ref** — `git fetch` / `git pull` をしない（ブランチ差分は読み取り時点で ref を解決するため、差分の基準が途中で動く）
3. **共有の `.git/config` と hooks** — 全 worktree で共有される。別 worktree での依存インストール（`husky install` 等）はレビュー対象の git 挙動を書き換える。worktree の追加は `git -c core.hooksPath=/dev/null worktree add` で、レビュー起動より前に済ませる

**待ち時間に何を進めるかは制限しない。** 別 worktree での後続タスク実装を含めてよい。ただしそのブランチを merge するのは、レビュー結果を処理したあとにする。サブエージェントへ委譲するときは、上の制約と再帰起動の禁止をそのまま伝える（委譲先の完了時に別のレビューが自動起動する仕組みがあれば、それも止める）。
<!-- MIRROR:review-async END -->

## 中断・回収失敗からの復旧

会話の割り込みや合流失敗を、レビュー自体の失敗と同一視しない。**session成立後の割り込みでは**次の順で復旧し、新規レビューを先に起動してはならない。CLIがpromptを受理する前に終了し、process・出力・session metadataのいずれからもsession成立を確認できない場合は起動失敗であり、原因を直して新規起動する。

1. 通知済みrun UUIDから`record.json`を開き、lifecycle stateと記録済みprocess identityを先に確認する。`running`でidentityが一致するprocessが生存中なら、記録したホストハンドル（または同期型ホストの結果）で待機・回収し、同じsessionへ同時にresumeしない。process不在またはidentity不一致なら終了済みとしてevent・stderr・exit statusを確認する。run recordを開けず状態を確定できなければ、process名・mtime・候補sessionから推測せず、resumeもforkも新規起動もせずユーザーへ報告する
2. 終了済みなら、記録した出力先またはホストの最終結果から既存出力を先に回収する。汎用`codex exec`では元promptが要求した終端要素（少なくともレビュー結論とscope statement）が欠ける場合を未完了とする。`codex exec review`では正常終了とfinal outputの存在を完了根拠にする。回収不能または未完了の場合だけ、記録した正確な`SESSION_ID`を`codex exec resume`して同じレビューを完了させる
3. session IDを安全に特定できなければ、推測したIDや`--last`で別sessionへ接続せず、復旧不能と、新規レビューでは時間・トークンを再消費し元の探索文脈も継承できないことをユーザーへ報告して判断を返す

```bash
codex exec resume SESSION_ID \
  --json \
  -o "<recovery_output>" \
  -m <original_model> \
  -c model_reasoning_effort="<original_effort>" \
  -c sandbox_mode="read-only" \
  "$(cat <<'CODEX_REVIEW_RECOVERY'
You are the reviewer. Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.

直前のレビューを継続してください。調査済みの範囲をゼロからやり直さず、未完了部分だけを完了させてください。
この回答は中断後の継続生成であり、元の最終本文の逐語的な再掲とは主張しないでください。
今回実際に検査した範囲と、session履歴から引き継いだ範囲を区別したscope statementを必ず返してください。新しいレビュー観点は追加せず、リポジトリは変更しないでください。
CODEX_REVIEW_RECOVERY
)" < /dev/null > "<recovery_event_log>" 2> "<recovery_stderr_log>"
```

復旧を起動したら、`<recovery_output>`・`<recovery_event_log>`・`<recovery_stderr_log>`も同じrecovery recordへ追記し、以後の回収では元の出力先と混同しない。

recoveryはrecovery recordの`-C`作業rootから実行し、元のmodel・effort・対象pathを維持する。snapshot起動なら同じsnapshot worktreeを使い、新しい観点やスコープを加えない。同じhost timeoutが再発する条件ではhost-nativeな非同期実行へ直すかscopeを縮小し、縮小範囲をscope statementへ記録する。明示model/effortは変更しない。正確なIDとして扱えるのは、記録済みホストtaskのmetadata、記録済みevent logの`thread.started`のように元processと一意に対応する値だけである。cwdのlatest、更新時刻、候補一覧からの推測は使わない。resumeは元sessionの作業rootを引き継ぐため、現行CLIでは`-s`/`-C`を足さず、`-c sandbox_mode="read-only"`でread-onlyを再明示する。非git rootから起動したsessionでは`--skip-git-repo-check`を再指定する。resumeがsession不存在で失敗した場合は繰り返さず、復旧不能としてstep 3の報告へ進む。

## 結果の整理と報告

既定の`--json -o <final_output>`起動では、完了時に`final_output`を読み、event logはsession IDの取得と中断時の部分状態確認にだけ使う。`--json`を付けない`codex exec review`では従来のtext出力からメタ情報ヘッダーを除外する。レビュー指摘は結論ではなく仮説であり、採用前に必ず該当path:lineと実装を自分で確認する。必要であれば以下の観点で整理する:

`final_output`は最終本文だけなのでそのまま読む。text出力を回収する場合は数百KBになることがあるため、ファイル全体を読まず`tail`と`rg -n "VERDICT|must-fix"`で必要箇所を特定する。`ERROR rmcp::transport::worker: ... Auth(AuthorizationRequired)` はheadlessで対話認証MCPを起動できないノイズであり、レビュー本文が出ていれば失敗扱いしない。

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

- **各提案に必要性の根拠をラベルさせる。** `BASIS: OBSERVED`（コードやテストで観測された事実・再現する不具合）/ `CURRENT-THREAT`（現在の脅威モデル・受入条件・規制で要求される）/ `REAL-DEMAND`（実在する利用者・ユースケース）/ `SPECULATIVE`（将来こうなるかもしれないという仮説）のいずれかを付けさせる。`SPECULATIVE` は提案の削除ではなく分離が目的で、受け取り側の判断材料にする。ラベル定義の正本は `ai-native-engineering` の「BASIS ラベル」節。
- **より単純な代替案を併記させる。** 「同じ問題を解決できる、より少ない機構・抽象・依存で済む案を必ず1つ挙げ、その案を採らない理由を示す」。単純案が示せない提案は、必要性の再確認対象にする。

<!-- MIRROR:review-common BEGIN -->
### 受け取り側の検証規律

1. 指摘を機械的に採用・棄却せず、該当箇所と成立条件を確認する。
2. **引用の実在を確認する。** 提示された `path:line` とコード断片が実際にその内容で存在するかを、採用前に必ず自分で突き合わせる。行番号のずれ、古い内容の引用、存在しないシンボルは珍しくない。実在しない引用に依存した指摘は、結論が正しく見えても採用しない。
3. **scope statement を読み、未検査範囲を明示的に扱う。** 未検査の観点が重要なら、別途レビューするか自分で確認する。返答に無いことを「問題が無いこと」の根拠にしない。
4. **`BASIS: SPECULATIVE` の提案は既定で採用しない。** 「security上望ましい」「将来必要になりそう」「一般にベストプラクティス」だけを根拠にした提案は、具体的な資産・攻撃経路・実需・観測された負荷を特定できるまで保留する。判定基準は `ai-native-engineering` skill の「投機的な抽象化を見分ける」「需要を待つ領域」「原則として先に決める判断」に従い、契約・境界の先決めと機構の先作りを分けて扱う。
5. **単純案が併記されている場合、まず単純案を検討する。** 提案側の複雑な案を既定にしない。
6. セキュリティ境界は`fail-closed`等のラベルで合格にせず、何と何を比較し、どこで強制しているかを実装まで辿る。
7. 修正後は元の検査に加え、secret/confusable等の関連scanを再実行する。レビュー修正そのものが新しい欠陥を作り得る。
8. 最後に`git status`を再確認し、レビュー用processによる汚染がないことを確認する（スナップショット起動時はスナップショット worktree 側を確認する）。
<!-- MIRROR:review-common END -->

## 注意事項

- `-s read-only` により書き込み系コマンドはサンドボックスで禁止される
- 汎用 `codex exec` のプロンプトを二重引用符で直書きしない。Markdown やコード片を含む場合は必ず single-quoted heredoc で渡す
- `codex exec review` は既定でサンドボックス（read-only 相当）で動作する。`-s`/`--sandbox` フラグは持たないため付けない（汎用 `codex exec` のみ `-s read-only` を明示）
- 適用対象は「やり直しコストが高い成果物」に絞る。型・lint・テストで検出できる欠陥や、実行すれば分かる動作確認には使わない
- モデル・effort の既定と昇格条件は「モデルと effort」セクションの定義に従う（config 既定に依存せず必ず明示する）
- モデルは既定 `gpt-6-luna`。設計そのものが対象・高不確実性・拠り所の設計が無い場合だけ `gpt-6-sol` へ昇格し、理由を一言添える。題材（認証・並行処理など）は昇格理由にならない
- 既定モデルでの結果報告には、未検査範囲と「採用する／スコープを絞って `gpt-6-sol` + `medium` で再実行する」の選択を必ず添える
- `gpt-6-astra` は最上位モデルのため、astra をユーザーが明示した場合のみ使用し、自動選択は絶対にしない
- effort の既定は luna が `high`、sol が `medium`、astra が `low`。深さ不足は luna の effort ではなくモデルを上げて補い、`high` は相当難度・重要度の高い対象に限る
- 昇格のための独立再レビューは新規sessionで行う。割り込み・回収失敗のrecoveryと追加質問は、正確なsession IDを指定して`codex exec resume`する
- 差分レビューも既定は汎用 `codex exec`。`codex exec review` は prompt contract を注入できないため、ユーザー明示時のみ使う
- `xhigh` / `max` / `ultra` は使わない。精度が上がらないため、深さ不足はスコープの絞り込みや観点の具体化で解決する
- 対象ディレクトリが Git リポジトリでない場合は `--skip-git-repo-check` を追加する
- `codex exec review` は CWD が Git リポジトリである必要がある
