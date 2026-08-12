# Task source と作業journal

Autopilotはtask trackingを1つの役割として扱う。設定されたtask sourceが、タスクの選択・再開、
durableな書込面がある場合の作業journal、対応可能な状態遷移をまとめて担う。選択と記録を同じadapterへ
置くことで、opaqueなtask identityが2つの実装間でずれる不変条件を増やさない。

汎用lifecycleは次の3遷移だけを持つ。

- `start`: AIがタスクをclaimし作業を開始した。
- `review`: 実装が独立reviewまたはPR reviewへ進める状態になった。
- `complete`: 設定された受入条件を満たした。

Escalationは第4の状態ではなくjournal entryである。task source固有のqueue状態は持てるが、
orchestratorはそれを別sourceへ再現しない。

## 作業journalの慣習

task sourceにdurableな追記面がある場合、作業の進行に合わせて次のMarkdown entryを残す。
これは人間が読める慣習であり、機械可読なevent schemaではない。

### `## Plan`

- 確認した事実と受入条件
- 検討した選択肢と採用案
- scopeとnon-goal
- 検証計画

### `## Review — round N`

- reviewerと固定されたreview対象
- verdictとmust-fix
- 採用・棄却・後送した指摘と理由
- 必要だった場合の再review結果

### `## Decision`

PlanやReviewだけでは明確にならない重要な選択に限って使う。選択肢、判断、理由、影響、再検討条件を
残す。複数タスクへ影響するdurableなarchitecture判断は、repoにADR運用があればそちらにも記録する。

### `## Progress`

重要な観測、前提の変更、外部から確認可能なcheckpointに使う。日常的なcommand logは転記しない。

### `## Escalation`

blocking condition、安全に実施済みの確認、不足している権限または判断、最短の再開手順を残す。

### `## Completion evidence`

- 利用可能になった能力
- PRまたは同等の変更参照
- 検証したsource revisionと、異なる場合は最終merge/release revision
- quality-gate署名と重要なtest結果
- 必要なdeploy/runtime検証
- 既知制約とdurableなfollow-up

日常的なentry追記と3つの状態遷移は通常のautopilot実行であり、entryごとの人間承認は不要である。
既存のmerge/deploy gateと、解除不能な破壊操作ルールをauthority境界として維持する。

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
  しない。既にin-progressのタスクを再開するだけならclaimを呼ばず、assigneeを書き換えない。
- adapterは単一repository Project専用であり、Issue URLのowner/repo/numberがconfigと一致しないitemを
  claim前にfail loudlyとする。
- Plan、Reviewの採否、Decision、Progress、Escalation、Completion evidenceを選択したIssueへ追記する。
  Issue comment面を持たないdraft itemはclaim前にfail loudlyとする。
- `review`と`complete`は設定された`statusNames`を使う。省略時は従来の`In Progress`、
  `In Review`、`Done`を使う。
- 全書込はmain skillのrepo・Project identity guardを維持する。GitHub認証とIDを汎用契約へ持ち込まない。
- draft itemで停止した場合はIssueへ変換してdurable journalを与えるか、そのrunでitem IDを`--exclude`し、
  理由をEnd-of-run Reportへ残す。journal無しでclaimする回避はしない。

## `plan-doc` adapter

tracked checklistのcheck更新は、実装変更と同じtask PRに含める。feature branch上では先にcheck済みに
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
