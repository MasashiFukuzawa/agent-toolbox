---
name: codex-review
description: >-
  Codex CLI の独立インスタンスでコードや差分を read-only レビューする。Codex・OpenAI を明示した第三者レビューに使う。一般的なレビューや Claude 指定には使わない。「Codexに見てもらって」を正のトリガーとし、provider未指定の第三者レビューでは勝手に選ばず、ユーザーへ確認する。
---
# Codex Review スキル

このスキルは Claude Code / Codex / Cursor のどのホスト（エージェント）からも呼ばれる前提で書かれている。ホスト固有の手順は「実行時間と中断の防止」のホスト分岐に従う。

## ガードレール（必須・逸脱禁止）

1. **read-only 厳守**: 必ず `-s read-only` で起動する。レビュー用 Codex が作業ツリーへ変更を加えることは許されない（実行後に `git status` で汚染がないか確認し、汚染があれば即報告する）
2. **ネスト起動禁止**: レビュー用 Codex に別の `codex exec` / `claude -p` / review 系 skill を起動させない（依頼文に再帰防止文を必ず含める。後述）
3. **書き込み系操作の禁止**: commit / push / PR 作成 / GitHub コメント / Issue 作成・更新をレビュー用 Codex に行わせない。結果はテキストで返させ、扱いは呼び出し元が判断する
4. **明示指定の尊重**: ユーザーが effort / model を明示した場合、自動判定で上書きしない（上げるのも下げるのも禁止）

Codex CLI を read-only サンドボックスで実行し、コードベースを分析する。
`approval: never` で動作するため、ユーザーの承認プロンプトは発生しない。

## モデルと effort（2026-07 時点）

**このセクションが本スキル内のモデル ID・effort・既定値の唯一の定義元。** 以降のコマンド例に埋まっているモデル名・effort はここの既定値の写しであり、モデル状況が変わったら本セクション・コマンド例・frontmatter description をあわせて更新する。

### モデル（GPT-5.6 系・3ティア構成）

| モデル | 位置づけ |
|--------|---------|
| `gpt-5.5`       | **既定**。一般利用可能な高性能model。深いレビュー・設計分析・難解なバグ調査 |
| `gpt-5.6-sol`   | 利用可能性を確認済み、またはユーザーが明示指定した場合のみ使うpreview候補 |
| `gpt-5.6-terra` | 品質/コストのバランス型。軽め〜中程度のレビューで指定可 |
| `gpt-5.6-luna`  | 高速・低コスト。クイックチェック向け |

`~/.codex/config.toml` の既定に依存せず、必ず `-m` でモデルを明示固定する（自己文書化のため）。別モデルの明示指定があればそれを優先。

### Effort レベル

**effort が明示されない場合は、依頼内容の複雑度から自動判定する。既定は `xhigh`。** 通常のコードレビューもアーキテクチャ分析もこの既定 `xhigh` で行う。クイックチェックなど明らかに軽微な依頼に限り `medium` / `high` に下げてよい。effort が明示された場合は必ずそれに従う。

下表は各レベルの「深さの目安」であって、タスク種別から機械的にレベルを引くための対応表ではない。**未指定時は上のルール（既定 `xhigh`）が優先**し、下表は「既定からどこまで降格してよいか」の判断材料として使う。

| レベル | オプション | 目安（既定 `xhigh` からの降格目安） |
|--------|-----------|------|
| `low`    | `-c model_reasoning_effort="low"`    | ごく軽微・クイックな確認のみ（最速） |
| `medium` | `-c model_reasoning_effort="medium"` | 小さな差分・限定スコープの軽いレビュー |
| `high`   | `-c model_reasoning_effort="high"`   | 既定より軽くしたいが一定の深さは要るとき |
| `xhigh`  | `-c model_reasoning_effort="xhigh"`  | 通常のコードレビュー〜複雑な設計判断・アーキテクチャ分析・難解なバグ（**既定・自動判定の上限**） |
| `max` / `ultra` | 同上の形式で指定 | **ユーザー明示時のみ**。Codex CLI 0.143+ でモデル依存に追加された。`ultra` はサブエージェント並列で使用量が急増する警告あり。モデル別の対応状況は公式未確認のため、指定してエラーになったら `xhigh` へフォールバックしてその旨を報告する |

## 実行前の確認

会話の文脈からわかる場合は確認を省略して構わない。不明な場合のみ確認する。

| 項目 | デフォルト |
|------|-----------|
| 依頼内容 | 必須。何をレビュー・調査してほしいか。 |
| 対象ディレクトリ | カレントディレクトリ (`pwd`) |
| モデル | `gpt-5.5` |
| Effort レベル | 自動判定（既定 `xhigh`、軽微な依頼のみ `medium`/`high`） |

`<依頼内容>` には、ユーザーの依頼をその意図を保ったまま、レビュー対象スコープ（全体／特定ファイル・ディレクトリ／差分の範囲）と観点を含む簡潔な指示へ整形して埋める。差分レビューでは対象（未コミット／ブランチ差分／コミット）を明示し、未指定なら作業ツリーの差分（`--uncommitted` 相当）を既定とする。

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
  -m gpt-5.5 \
  -C <project_dir> \
  -c model_reasoning_effort="<level>" \
  "$(cat <<'CODEX_REVIEW_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.

<依頼内容>
CODEX_REVIEW_PROMPT
)"
```

- `-s read-only`: ファイル変更・危険なコマンドをサンドボックスで禁止
- `-m gpt-5.5`: 一般利用可能な既定modelを明示固定（config既定に依存しない）
- `-C <project_dir>`: 分析対象の作業ルートを指定
- `-c model_reasoning_effort`: 推論深度の指定（既定 `xhigh`、自動判定）

**重要**: heredoc delimiter は必ず引用する（例: `<<'CODEX_REVIEW_PROMPT'`）。引用しない `<<EOF` は shell 展開を許すため使わない。プロンプト内に delimiter と同じ行が含まれる場合だけ、別の一意な delimiter 名に変える。
**重要**: Claude Code 上ではこのコマンドを **`run_in_background: true` で起動する**（理由と手順は後述の「実行時間と中断の防止」を参照）。xhigh が既定のため処理は数分〜数十分かかりうるが、背景実行なら Bash の10分上限で kill されず、呼び出し元もブロックしない。

### diff / commit / ブランチの差分レビュー

差分を対象にした専門的なレビューには `codex exec review` サブコマンドが最適:

```bash
# 未コミットの変更をレビュー
codex exec review -m gpt-5.5 -c model_reasoning_effort="xhigh" --uncommitted

# 特定のブランチとの差分をレビュー
codex exec review -m gpt-5.5 -c model_reasoning_effort="xhigh" --base main

# 特定コミットをレビュー
codex exec review -m gpt-5.5 -c model_reasoning_effort="xhigh" --commit <sha>
```

**重要**: `codex exec review` は `-c model_reasoning_effort` を省くと `~/.codex/config.toml` の既定（通常 `medium`）で動き、**既定 `xhigh` が効かない**。自動判定した effort（未指定なら既定 `xhigh`）を確実に反映するため、`-c model_reasoning_effort="<level>"` を必ず明示すること。diff レビューも長時間化しうるため、Claude Code 上では同様に `run_in_background: true` で起動する。

**重要**: `[PROMPT]` と `--uncommitted`/`--base`/`--commit` は相互排他。`--help` では同時指定可能に見えるが、実際に実行すると `error: the argument '[PROMPT]' cannot be used with '--uncommitted'` で失敗する（v0.144.1 でも継続）。diff レビューにカスタム指示を組み合わせることはできない。カスタム指示が必要な場合は汎用の `codex exec` コマンドを使うこと。

### 実行例

```bash
# カレントプロジェクトのセキュリティレビュー（既定 xhigh）
codex exec \
  -s read-only \
  -m gpt-5.5 \
  -C $HOME/my-project \
  -c model_reasoning_effort="xhigh" \
  "$(cat <<'CODEX_REVIEW_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.

認証周りのセキュリティ上の問題点を洗い出してください
CODEX_REVIEW_PROMPT
)"

# 未コミット変更のレビュー（カスタム指示なし、既定 xhigh）
codex exec review -m gpt-5.5 -c model_reasoning_effort="xhigh" --uncommitted
```

## 実行時間と中断の防止

ハイエンドモデル + 高 effort（既定の `gpt-5.5` + `xhigh`）では、対象が大規模なほどレビューに**数分〜数十分**かかることがある。これは正常で、出力が無い間も停止やハングではなく推論を継続している。**長時間化を理由に kill・キャンセル・再実行をしてはならない。** 呼び出し元（人間・上位エージェントを問わず）に中断不要だと伝え、気長に完了を待つ。

**まず実行ホストで分岐する**: Claude Code 上なら背景実行（手順1〜4）。`run_in_background` を持たないホスト（Codex/Cursor 等。自分が Codex として動作している場合を含む）は手順1〜4ではなく**手順5の foreground フォールバック**を使う。

1. **`run_in_background: true` で起動する（Claude Code での本筋）**
   Claude Code 上では Bash ツールの `run_in_background` を使う。foreground と違い10分上限で kill されず、呼び出し元をブロックしない。完了時に Claude Code がエージェントを自動再呼び出しし、出力も取得できる。
2. **起動直後に呼び出し元へ予告する**（背景起動でターンが即 yield するので、この一言を必ず出す）
   > 「codex-review をバックグラウンドで開始しました。レビューには数十分かかる場合があります。応答が無くても処理は継続中（ハングではありません）なので、中断せず気長にお待ちください。完了時に結果を報告します。」
3. **完了通知で再呼び出しされたら報告する**
   背景起動時に Bash ツールが返す出力ファイルのパスを `Read` するか `BashOutput` で出力を取得し、下記「結果の整理と報告」の観点でまとめて呼び出し元に返す。
4. **待機中は背景タスクを kill・キャンセル・再起動しない。** 数十分無出力でも推論継続中の正常状態として完了を待つ。
5. **背景実行を持たないホスト（Codex/Cursor 等）でのフォールバック**
   foreground で実行し、ホストの実行タイムアウトを可能な限り長く確保する（Claude Code の Bash 相当なら上限 `600000`ms=10分）。foreground はブロックするため発話窓は「実行直前」のみ。**起動直前に**次の foreground 用の予告を出す（手順2の文言は「バックグラウンドで開始」を含み foreground では不正確になるため、そのまま流用しない）。
   > 「これからレビューを実行します。完了まで数十分かかる場合があります。応答が無くても処理は継続中（ハングではありません）なので、中断せず気長にお待ちください。」

   結果は標準出力（戻り値）として直接返るため、背景用の出力ファイル `Read` / `BashOutput` は使わず、その stdout を下記「結果の整理と報告」に従って報告する。ホストのタイムアウト上限が数十分の実行に足りず kill された場合も盲目的に再実行せず、effort を一段下げる（xhigh→high）か対象を絞る（特定ファイル/ディレクトリ）。
6. **補足（実行モードに依らない）**: 背景実行は10分の foreground 上限に縛られないが「無制限」ではない。巨大リポジトリの xhigh が背景でも長すぎる場合は、同様に effort 降格（xhigh→high）や対象の絞り込みで対処する。

## 結果の整理と報告

Codex の出力には先頭にメタ情報ヘッダー（バージョン・モデル・サンドボックス種別など）が含まれる。
ヘッダーは除外し、本文の分析結果のみをユーザーに伝える。必要であれば以下の観点で整理する:

1. **要約**: 主な発見事項（3点以内）
2. **詳細**: 具体的な指摘（優先度順）
3. **推奨対応**: 改善提案と実装方針
4. **補足**: 追加調査が必要な項目

## 注意事項

- `-s read-only` により書き込み系コマンドはサンドボックスで禁止される
- 汎用 `codex exec` のプロンプトを二重引用符で直書きしない。Markdown やコード片を含む場合は必ず single-quoted heredoc で渡す
- `codex exec review` は既定でサンドボックス（read-only 相当）で動作する。`-s`/`--sandbox` フラグは持たないため付けない（汎用 `codex exec` のみ `-s read-only` を明示）
- モデル・effort の既定と選択肢は「モデルと effort」セクションの定義に従う（config 既定に依存せず必ず明示する）
- 対象ディレクトリが Git リポジトリでない場合は `--skip-git-repo-check` を追加する
- `codex exec review` は CWD が Git リポジトリである必要がある
