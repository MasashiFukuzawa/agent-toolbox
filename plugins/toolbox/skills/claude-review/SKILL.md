---
name: claude-review
description: >-
  Claude CLI の独立インスタンスでコードや設計を read-only レビューする。Claude・Anthropic を明示した第三者レビューに使う。一般的なレビューや Codex 指定には使わない。「Claudeに見てもらって」を正のトリガーとし、provider未指定の第三者レビューでは勝手に選ばず、ユーザーへ確認する。
---
# Claude Review スキル

このスキルは Claude Code / Codex / Cursor のどのホスト（エージェント）からも呼ばれる前提で書かれている。ホスト固有の手順は「実行時間と中断の防止」のホスト分岐に従う。

## ガードレール（必須・逸脱禁止）

1. **read-only 厳守**: レビュー用 Claude に書き込みを行わせない（実行後に `git status` で作業ツリー汚染がないか確認し、汚染があれば即報告する）
2. **ネスト起動禁止**: レビュー用 Claude に別の `claude -p` / `codex exec` / review 系 skill を起動させない（依頼文に再帰防止文を必ず含める）
3. **書き込み系操作の禁止**: commit / push / PR 作成 / GitHub コメント / Issue 作成・更新を行わせない。結果はテキストで返させる
4. **明示指定の尊重**: ユーザーが effort / model を明示した場合、自動判定で上書きしない（上げるのも下げるのも禁止）
5. **長時間無出力時のフォールバック**: 開始時に想定所要時間（数分〜数十分）を伝える。バックグラウンド実行にして進捗を定期確認し、40分以上無出力なら状況を報告して「継続 or 中断して codex-review へ切替」をユーザーに提示する（勝手に放置も勝手に中断もしない。中断時は結果の部分回収を試みる）。xhigh は公式に「30分超の long-running タスク向け」と定義されており、数十分の無出力は正常範囲

別プロセスの Claude CLI を起動し、コードベースを read-only で分析する。
現セッションのコンテキストやバイアスに縛られない、独立したセカンドオピニオンを得られる。

## モデルと effort（2026-07 時点）

**このセクションが本スキル内のモデル ID・effort・既定値の唯一の定義元。** 以降のコマンド例に埋まっているモデル名・effort はここの既定値の写しであり、モデル状況が変わったら本セクション・コマンド例・frontmatter description をあわせて更新する。

### 使用可能なモデル

| モデル | ID | 備考 |
|--------|-----|------|
| Opus 4.8 | `claude-opus-4-8` | **既定**。品質・深さ優先 |
| Sonnet 5 | `claude-sonnet-5` | 高速・低コスト。near-Opus 能力で xhigh 対応。軽めのレビューで指定可 |
| Fable 5 | `claude-fable-5` | **ユーザー明示時のみ**。トークン消費が著しく多いため自動選択しない |

**重要**: `claude-fable-5` はトークン消費が著しく多いため、ユーザーが「Fable で」「fable-5 を使って」と明示的に指定した場合のみ使用する。それ以外では常に `claude-opus-4-8` をデフォルトとする。別モデルの明示指定があればそれを優先。

### Effort レベル

**effort が明示されない場合は、依頼内容の複雑度から自動判定する。既定は `xhigh`。** 通常のコードレビューもアーキテクチャ分析もこの既定 `xhigh` で行う。クイックチェックなど明らかに軽微な依頼に限り `medium` / `high` に下げてよい。effort が明示された場合は必ずそれに従う。

下表は各レベルの「深さの目安」であって、タスク種別から機械的にレベルを引くための対応表ではない。**未指定時は上のルール（既定 `xhigh`）が優先**し、下表は「既定からどこまで増減してよいか」の判断材料として使う。

| レベル | オプション | 目安（既定 `xhigh` 基準の増減目安） |
|--------|-----------|------|
| `low`    | `--effort low`    | ごく軽微・クイックな確認のみ（最速） |
| `medium` | `--effort medium` | 小さな差分・限定スコープの軽いレビュー |
| `high`   | `--effort high`   | 既定より軽くしたいが一定の深さは要るとき |
| `xhigh`  | `--effort xhigh`  | 通常のコードレビュー〜複雑な設計判断・アーキテクチャ分析・難解なバグ（**既定・自動判定の上限**）。公式に「30分超の long-running タスク向け」と定義される深さ |
| `max`    | `--effort max`    | 最高精度（時間・コストが増える。ユーザー明示時のみ） |

**自動判定の上限は `xhigh`。`max` はユーザーが明示的に要求した場合のみ使用する**（過剰な時間・コストの暴発防止）。

## 実行前の確認

会話の文脈からわかる場合は確認を省略して構わない。不明な場合のみ確認する。

| 項目 | デフォルト |
|------|-----------|
| 依頼内容 | 必須。何をレビュー・調査してほしいか。 |
| 対象ディレクトリ | カレントディレクトリ (`pwd`) |
| モデル | `claude-opus-4-8`（Opus 4.8）。別モデル指定があればそれを優先 |
| Effort レベル | 自動判定（既定 `xhigh`、軽微な依頼のみ `medium`/`high`） |

`<依頼内容>` には、ユーザーの依頼をその意図を保ったまま、レビュー対象スコープ（全体／特定ファイル・ディレクトリ／差分の範囲）と観点を含む簡潔な指示へ整形して埋める。差分レビューでは対象（未コミット／ブランチ差分／コミット）を依頼文に明示し、未指定なら作業ツリーの差分を既定とする（起動先 Claude が `git diff` 等の読み取り系ツールで取得する）。

重要: 起動先 Claude がさらに `codex-review` / `claude-review` skill や `codex exec` / `claude -p` を起動して再帰することがある。`<依頼内容>` の先頭または末尾に必ず次の趣旨を明示する。

```text
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.
```

## 実行コマンド

プロンプト本文は必ず **single-quoted heredoc** で渡す。Markdown のバッククォート、`$VAR`、`$(...)`、型注釈、引用符を含むレビュー依頼を `claude -p "..."` に直接入れると、shell がコマンド置換や変数展開として解釈してプロンプトを壊す。

```bash
claude -p "$(cat <<'CLAUDE_REVIEW_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.

<依頼内容>
CLAUDE_REVIEW_PROMPT
)" \
  --model claude-opus-4-8 \
  --effort <level> \
  --add-dir <project_dir> \
  --disallowedTools "Edit,Write,NotebookEdit"
```

**重要**: heredoc delimiter は必ず引用する（例: `<<'CLAUDE_REVIEW_PROMPT'`）。引用しない `<<EOF` は shell 展開を許すため使わない。プロンプト内に delimiter と同じ行が含まれる場合だけ、別の一意な delimiter 名に変える。
**重要**: `--disallowedTools` は可変長フラグのため、プロンプトは必ずフラグ群より前（最初の引数）に置くこと。後ろに置くとプロンプトが認識されずエラーになる。
**重要**: Claude Code 上ではこのコマンドを **`run_in_background: true` で起動する**（理由と手順は後述の「実行時間と中断の防止」を参照）。xhigh が既定のため処理は数分〜数十分かかりうるが、背景実行なら Bash の10分上限で kill されず、呼び出し元もブロックしない。`claude -p` は非対話の print モードで標準出力に結果を出すため、背景起動でも出力ファイルから完全に回収できる。

- `--model claude-opus-4-8`: 使用モデルを明示固定（既定・選択肢は「モデルと effort」セクション参照）
- `--effort <level>`: 既定 `xhigh`（自動判定）
- `--add-dir <project_dir>`: 対象ディレクトリへのアクセスを明示的に許可する
- `--disallowedTools`: Edit/Write/NotebookEdit を禁止して読み取り専用を保証する
- ファイルの読み取り・Bash・git などの読み取り系ツールは引き続き使用可能

### 実行例

```bash
# カレントディレクトリを分析する場合（既定 xhigh）
claude -p "$(cat <<'CLAUDE_REVIEW_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.

認証周りのセキュリティ上の問題点を洗い出してください
CLAUDE_REVIEW_PROMPT
)" \
  --model claude-opus-4-8 \
  --effort xhigh \
  --add-dir $HOME/my-project \
  --disallowedTools "Edit,Write,NotebookEdit"
```

```bash
# 軽めのクイック確認（自動判定で Sonnet 5 + medium に下げた例）
claude -p "$(cat <<'CLAUDE_REVIEW_PROMPT'
You are the reviewer. Inspect the repository directly.
Do not invoke codex-review, claude-review, codex exec, claude -p, or any nested reviewer.
Use only read-only repository inspection commands and return findings directly.

この差分に明らかなバグがないか軽く見て
CLAUDE_REVIEW_PROMPT
)" \
  --model claude-sonnet-5 \
  --effort medium \
  --add-dir $HOME/other-project \
  --disallowedTools "Edit,Write,NotebookEdit"
```

## 実行時間と中断の防止

ハイエンドモデル + 高 effort（既定の Opus 4.8 + `xhigh`）では、対象が大規模なほどレビューに**数分〜数十分**かかることがある（xhigh は公式に「30分超の long-running タスク向け」と定義されている）。これは正常で、出力が無い間も停止やハングではなく推論を継続している。**長時間化を理由に kill・キャンセル・再実行をしてはならない。** 呼び出し元（人間・上位エージェントを問わず）に中断不要だと伝え、気長に完了を待つ。

**まず実行ホストで分岐する**: Claude Code 上なら背景実行（手順1〜4）。`run_in_background` を持たないホスト（Codex/Cursor 等。自分が Codex として動作している場合を含む）は手順1〜4ではなく**手順5の foreground フォールバック**を使う。

1. **`run_in_background: true` で起動する（Claude Code での本筋）**
   Claude Code 上では Bash ツールの `run_in_background` を使う。foreground と違い10分上限で kill されず、呼び出し元をブロックしない。完了時に Claude Code がエージェントを自動再呼び出しし、出力も取得できる。
2. **起動直後に呼び出し元へ予告する**（背景起動でターンが即 yield するので、この一言を必ず出す）
   > 「claude-review をバックグラウンドで開始しました。レビューには数十分かかる場合があります。応答が無くても処理は継続中（ハングではありません）なので、中断せず気長にお待ちください。完了時に結果を報告します。」
3. **完了通知で再呼び出しされたら報告する**
   背景起動時に Bash ツールが返す出力ファイルのパスを `Read` するか `BashOutput` で出力を取得し、下記「結果の整理と報告」の観点でまとめて呼び出し元に返す。
4. **待機中は背景タスクを kill・キャンセル・再起動しない。** 数十分無出力でも推論継続中の正常状態として完了を待つ（40分超の無出力のみガードレール5に従いユーザーへ提示する）。
5. **背景実行を持たないホスト（Codex/Cursor 等）でのフォールバック**
   foreground で実行し、ホストの実行タイムアウトを可能な限り長く確保する（Claude Code の Bash 相当なら上限 `600000`ms=10分）。foreground はブロックするため発話窓は「実行直前」のみ。**起動直前に**次の foreground 用の予告を出す（手順2の文言は「バックグラウンドで開始」を含み foreground では不正確になるため、そのまま流用しない）。
   > 「これからレビューを実行します。完了まで数十分かかる場合があります。応答が無くても処理は継続中（ハングではありません）なので、中断せず気長にお待ちください。」

   結果は Bash の標準出力（戻り値）として直接返るため、背景用の出力ファイル `Read` / `BashOutput` は使わず、その stdout を下記「結果の整理と報告」に従って報告する。ホストのタイムアウト上限が数十分の実行に足りず kill された場合も盲目的に再実行せず、effort を一段下げる（xhigh→high）か対象を絞る（特定ファイル/ディレクトリ）。
6. **補足（実行モードに依らない）**: 背景実行は10分の foreground 上限に縛られないが「無制限」ではない。巨大リポジトリの xhigh が背景でも長すぎる場合は、同様に effort 降格（xhigh→high）や対象の絞り込みで対処する。

## 結果の整理と報告

Claude の出力をそのままユーザーに伝える。必要であれば以下の観点で整理する:

1. **要約**: 主な発見事項（3点以内）
2. **詳細**: 具体的な指摘（優先度順）
3. **推奨対応**: 改善提案と実装方針
4. **補足**: 追加調査が必要な項目

## 注意事項

- `--disallowedTools` により Edit/Write/NotebookEdit は使えず、ファイル変更は不可能
- Markdown やコード片を含むプロンプトを `claude -p "..."` に直接書かない。必ず single-quoted heredoc で渡す
- モデル・effort の既定と選択肢は「モデルと effort」セクションの定義に従う
- `claude-fable-5` はトークン消費が著しく多いためユーザー明示時のみ使用し、自動選択は絶対にしない
- effort は既定 `xhigh`（自動判定）。軽微な依頼や時間優先のときのみ `medium` / `high` に下げる
- `--add-dir` を忘れると対象ディレクトリへのアクセスが制限される場合がある
