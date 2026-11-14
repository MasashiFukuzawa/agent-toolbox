---
name: github-issue-create
description: >-
  任意のGitHub Organization／repoへIssueを起票し、Projectへ登録してStatusと明示Priorityを安全に設定するためのdry-run・apply・resumeを提供する。「GitHub Issueを作って」「IssueをProjectへ登録して」を正のトリガーとし、Issue 作成・Project Inbox 登録・途中失敗からの再開に使う。Project自体の新設・構造検証にはgithub-project-provisioningを使う。特定repoのroutingやlabelsを汎用規則として固定する用途には使わない。
---
# GitHub Issue Create

## 安全契約

- Issueを作る前に、必ずdry-runのplanを作る。
- ユーザーがIssueの作成を明示的に頼んだなら、述べられた範囲でそのIssueをplanしapplyする承認として扱う。dry-runのplanができたというだけで、2回目の承認を求めない。
- applyの前に止まるのは次の場合だけ：ユーザーが実行なしのplan・dry-run・レビューを頼んだ、重要な選択が未解決、確認できたidentity・対象・field・操作が、承認された依頼とrepositoryのpolicyに一致しない。
- identityの変化、対象の不一致、古いplan、labelの欠落、Projectのfieldの曖昧さ、権限の不足があれば、実行せずに失敗させる。
- 緊急度を述べた文章だけからPriorityを推測して書き込まない。ユーザーが明示的に選んだ場合か、repositoryのpolicyが決定的に与える場合だけ設定し、それ以外は省く。任意のPriorityを埋めるためだけに質問しない。
- 途中で失敗したら、既存のIssueを再開する。代わりのIssueを自動で作らない。
- repository固有のIssue policyがあれば適用する。このskillはroutingやlabelを創作しない。
- `--confirm-target` はrepositoryの取り違えを防ぐもので、承認の仕組みではない。承認は、ユーザーの変更依頼から来る。内容から導く `plan_id` が、planとapplyの間の編集を拒む。

## Issueの出力言語

- Issueのタイトル・本文・見出し・受入条件は**原則日本語**で書く。autopilotが起票する子Issue・後続課題、manifest内の各Issueにも適用する。毎回言語を確認する必要はない。
- ユーザーが別言語を明示した場合、または対象repoに英語必須などの明示的なIssue言語規約がある場合はそれに従う。両者が衝突する場合はapply前に解決する。
- スキルの説明、コード、エラーログ、雛形が英語であることだけを理由に、説明文まで英語へ切り替えない。既存Issueが英語という事実だけでは日本語の既定を上書きしない。
- API名、コード識別子、コマンド、引用ログ、URL、labels、Projectの選択肢名は原文のまま保持する。機械的に参照するテンプレート見出し・キーも保持し、記入する説明を日本語にする。
- 作成済みIssueの言語を揃えるためだけの再起票・無断翻訳はしない。resumeは保存済みplanとIssueを使い、本文変更が必要なら別の更新操作として扱う。

## 実行前提

- `github-operations` pluginを丸ごと導入する。skillのdirectoryだけを複製した構成は、意図的に対象外としている。
- Python 3.11以上、`gh`、明示したconfigか `.agents/github-operations.json` が要る。
- 別の導入済みresourceにあるconfigを明示して使う時は、そのファイルを絶対pathに解決し、`--config` で渡す。

## 手順

`scripts/run.py` は、実行の前に、このskillのdirectoryを基準に解決する。

1. 対象repositoryの `AGENTS.md`、template、使えるlabelをもとに、Issueを下書きする。planを作る前に上の出力言語の方針を当てはめ、dry-runの確認でタイトルと本文の言語を確かめる。
2. 長い本文はrepositoryの外の一時ファイルに書き、planを作る。

   ```bash
   python3 <skill-dir>/scripts/run.py plan \
     --config <config> \
     --repo <owner/repo> \
     --title '<title>' \
     --body-file <body-file> \
     --label <label> \
     --assignee <login> \
     --priority '<exact-option-name>'
   ```

   label、assignee、Priorityは、明示的な根拠が無ければ省く。

   複数のIssueは、[`references/manifest.md`](references/manifest.md) に従ってversion 1のJSON manifestを作り、1回でplanする。

   ```bash
   python3 <skill-dir>/scripts/run.py plan \
     --config <config> \
     --manifest <manifest.json>
   ```

   `--manifest` と、単一Issue用のflagを併用しない。applyの前に、repositoryの一覧（重複なし）、件数、すべての操作、生成されたfingerprintを確かめる。

3. 返されたすべてのfield、操作、`plan_id`、対象、認証済みのidentity、有効期限を確かめる。承認された依頼とrepositoryのpolicyに一致していれば、追加の承認を求めず、同じターンでapplyする。ユーザーがdry-runだけを頼んだなら、planを示して止まる。
4. 一致するplanをapplyする。

   ```bash
   python3 <skill-dir>/scripts/run.py apply --plan-id <id> --confirm-target '<target-from-plan>'
   ```

5. 作成は成功したがProjectへの登録やfieldの編集が失敗したら、既存のIssueのURLと残りの手順を示す。元の依頼が残りの操作も承認しているなら、Issueを作り直さず、同じplanを再開する。

   ```bash
   python3 <skill-dir>/scripts/run.py resume --plan-id <id> --confirm-target '<target-from-plan>'
   ```

   manifestのapplyは、一部が成功した後に終了コード `1` を返すことがある。stdoutのJSONを、entryごとの確定した結果として扱い、完了したentryを報告して、同じplanを再開する。終了コード `2` は、安全だと確かめる前に操作が拒否されたことを表す。

applyが古いlockを報告したら、そのプロセスがもう動いていないことを確かめてから、確認した対象だけを `run.py unlock --target '<owner/repo>' --confirm-target '<owner/repo>'` で解除する。

## 出力契約

- dry-runを頼まれた時：identity、repo、タイトル、本文、label、assignee、Project、Status、Priority、すべての変更操作。applyはしない。
- 成功：IssueのURL、Project itemのID、適用したfield、検証結果。
- 途中の失敗：既存のIssueのURL、完了した手順、残りの手順、安全な再開コマンド。
- manifestの成功：plan ID、対象の確認値、全体と完了の件数、entryごとのIssueのURL・Project itemのID・状態。
- manifestの途中の失敗：同じ機械可読の要約をstdoutに、対処できるエラーをstderrに出す。
