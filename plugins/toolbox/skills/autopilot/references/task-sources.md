# タスクの取り方と、タスクに残す記録

Autopilotはtask trackingを1つの役割として扱う。設定されたtask sourceが、タスクの選択・再開、
durableな書込面がある場合の作業journal、対応可能な状態遷移をまとめて担う。選択と記録を同じadapterへ
置くことで、opaqueなtask identityが2つの実装間でずれる不変条件を増やさない。

汎用lifecycleは次の3遷移だけを持つ。

- `start`: AIがタスクをclaimし作業を開始した。
- `review`: 実装が独立reviewまたはPR reviewへ進める状態になった。
- `complete`: 設定された受入条件を満たした。

全体計画が指定された場合、計画を優先順位・依存の正本、task sourceを詳細・journal・状態遷移の正本として対応付ける。実行候補との不整合は先に整合する。ローカルrun索引は所有者・handle・待ち条件の復旧用であり、第二のbacklogではない。

Escalationは第4の状態ではなくjournal entryである。task source固有のqueue状態は持てるが、
orchestratorはそれを別sourceへ再現しない。

## タスクに残す記録

人が読む進み具合と判断は、ゴールのページに書く。task sourceに追記できる場所（Issueのコメントなど）には、
ほかの人や別のセッションが照合に使う、最小の記録だけを残す。

- **着手**: claim直後に`goal-run: <ゴールの識別子>`、task identity、担当worktree、開始時刻を記録する。
  再開時は元の識別子と照合する。claimに成功して記録に失敗した時は、再claimせず照合して補う。
  記録の前は、編集も委任もしない。セッションが替わる時は、前のセッションが止まった根拠と新しい識別子を追記する。
- **止まった時**: 何を待っているかと、再開の条件を短く書く（ページと同じ内容）。
- **完了**: 利用できるようになったこと、PRまたは同等の変更の参照、検査した版と（異なれば）最終のmerge版、
  重要な検査の結果、残した制約。

着手・完了の追記と3つの状態遷移は通常の実行であり、追記ごとの人の承認は要らない。
merge/deployの決まりと、解除できない破壊操作の決まりは、権限の境界として保つ。

## Source能力

| Mode | 選択・再開 | Durable journal | Lifecycle遷移 | 無人multi-task |
|------|------------|-----------------|----------------|----------------|
| `github-projects` | Project item | Issue comment | Project Status | 対応 |
| `plan-doc` | 先頭の未完了項目 | 会話のみ | task PRに含めるcheck更新 | 1 run 1件 |
| `none` | 会話の依頼 | 会話のみ | なし | 1 run 1件 |

未対応の能力は明示的に報告する。欠けたtracker能力を模倣するためにshadow Issue、local database、
synthetic statusを作らない。

## `github-projects` adapter

- `next-task`は候補をread-onlyで選ぶ。共通collaboration preflight後は`github-operations`のguarded claimを
  呼ぶ。GitHub固有のidentity再確認、self-assignment、`start`遷移、部分失敗contractをautopilotへ重複実装
  しない。既にin-progressでもjournalのsession所有者を確認し、自分の担当と確認できる場合だけ再開する。assigneeの一致だけではsession所有権を証明しない。別担当や未解消の待ち条件はexcludeし、理由と再評価条件を残す。
- adapterは単一repositoryのqueueだけを扱う。共有Projectではcanonical Issue URLから別repositoryと確認できる
  itemを候補選択前に除外し、選択したIssueのowner/repo/numberはclaim前にconfigと完全一致しなければ
  fail loudlyとする。repositoryを安全に判定できないdraft・不正URLは除外で隠さない。
- 着手の記録、止まった時の記録、完了の記録を、選択したIssueへ追記する。
  Issue comment面を持たないdraft itemはclaim前にfail loudlyとする。
- `review`と`complete`は設定された`statusNames`を使う。省略時は従来の`In Progress`、
  `In Review`、`Done`を使う。
- 全書込はmain skillのrepo・Project identity guardを維持する。GitHub認証とIDを汎用契約へ持ち込まない。
- draft itemで停止した場合はIssueへ変換してdurable journalを与えるか、そのrunでitem IDを`--exclude`し、
  理由をゴールのページへ残す。journal無しでclaimする回避はしない。

## `plan-doc` adapter

PR mergeで必須受入が成立するタスクでは、tracked checklistのcheck更新を実装変更と同じtask PRに含める。merge後の配備・実機受入が必須なら先にcheckせず、承認されたtracking方法を決める。このadapterだけで未対応の完了管理を捏造しない。feature branch上では先にcheck済みに
見えてもbase branchは未完了のままであり、merge時に初めて実際の完了状態が反映される。check更新後の
treeをdoneで検証し、未検証のtracking-only変更を出荷しない。

各runの開始時はbase branchをcheckoutせず、fetch後の`origin/<base>:<plan path>`をqueueの正として
項目を選ぶ。同じ項目に対応するbranchやPRがある場合は状態を確認する。local branchだけなら再開、
open PRなら既存review gateで停止、closed-unmergedまたはmergedなのに最新baseで未チェックなら矛盾として
fail loudlyとする。baseへ直接commitしない。Issue番号を持たない非ASCII項目のbranch identityには、
NFKC正規化したtitleのSHA-256 prefixを使う。

このmodeは1 runで1件だけ処理し、journalは会話へ出す。専用のwritable task-source adapterが無い間、
同じrunで次項目をclaimしない。

## `none` adapter

現在の会話をtask source兼journalとする。durable lifecycleやqueueがあるとは主張せず、1回につき1件だけ
処理する。

## Scope境界

task-sourceの中立化はrelease forgeを中立化しない。現在のPR作成、checks、mergeはGitHub CLIを使う。
非GitHub forgeは、実在repoから需要が観測された時に追加する別の拡張点である。
