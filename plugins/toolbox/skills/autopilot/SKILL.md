---
name: autopilot
description: >-
  controllerが複数タスクの選択・委任・現物レビュー・出荷品質・継続監視を管理し、自律的に完了へ運ぶ。独立した作業の並列処理と結果回収を含む。「自律で進めて」「バックログを全部消化して」を正のトリガーとする。単発修正には使わない。品質受入だけならdoneを使う。
---
# autopilot — controllerによる自律開発

controllerは優先順位、モデル選択、委任、割り込み対応、現物レビュー、出荷品質に責任を持つ。workerへ実装・調査・検証を委任できるが、最終受入・出荷判断は委任しない。起動数でなく、受入条件を満たした成果と人間の負担軽減を最適化する。

## 開始契約

既存の指示・正本から次を短く記録する。明らかな内容を再質問しない。

- 目的、優先順位、期限、必須受入条件、非スコープ
- 計画・タスク詳細・実装・実環境証跡それぞれの正本
- controllerへ委任された判断、予約された人間判断、モデル利用範囲（無人時に使えるreview providerを含む）
- merge/deployの対象環境・許可条件、並列上限、実行上限と停止条件
- controller/runの識別子、担当タスク、実行ハンドル、再開用索引の場所

通常設計は選択肢と理由を記録してcontrollerが決める。公開範囲・リスク許容・権限・スコープを委任範囲外へ変えるときは人間判断。相談には背景、課題、選択肢、推奨、影響、回答期限、待つ間に進める独立作業を揃える。

承認は対象・操作・環境・条件に結び付けて保存する。compactionだけを理由に取り直さない。条件が変われば再評価し、単なる「急いで」「止まらず」をmerge/deploy権限の付与と解釈しない。

## 安全境界と拡張点

設定は今いるrepoの `.agents/autopilot.json` のみから読む。他repoの値を流用しない。全外部書込みの前にrepo同一性を確認し、`gh`には確認済みの`--repo` / `--owner`を明示する。不一致は全書込みを停止する。

merge/deployはconfigの明示許可、または対象・条件を特定したユーザーの明示承認が必要。未設定はhuman。承認をconfigへ自動で書き戻さない。未コミット変更を失う削除、DB・ユーザーデータ削除、force pushは操作前の人間確認を必要とする。

拡張点はrepo configの明示指定 → 同役割のproject skill → 次の既定で解決する。名前はnamespaceでなく役割で扱う。

| 役割 | 既定と責任 |
|---|---|
| モデル選択 | `model-selection`を読み、controllerがタスクに適したmodel/effortを決める |
| 品質受入 | controllerが`done`を使う。workerのPASSを代用にしない |
| 独立レビュー | 許可されたproviderの`claude-review` / `codex-review`。read-only |
| UI/E2E | `e2e-capability-verification`、ブラウザ操作は`browser-operations` |
| 進捗報告 | `progress-report`。再開用索引とは分ける |
| タスク選択・journal | [task sources](references/task-sources.md) |

## Preflight

```bash
<skill-dir>/scripts/autopilot_board.py preflight
```

非ゼロなら書込みを行わない。出力のrepo、baseBranch、mergeGate、deployGate、configDigest、Project情報をrunの設定snapshotとして保持する。digestが変われば再preflightして既存承認への影響を確認する。

自動mergeのbranch protection検査がhumanへ降格した場合、その理由を維持する。単なるauto指定で迂回しない。品質ゲート定義（`.agents/**`、CI設定等）の変更はautoでも人間のmerge確認へ回す。

ホスト名から能力を決めつけず、非同期起動、短いyield、通知、wait、永続ハンドル、再開機構、並列枠を確認する。起動前に [controllerの継続監視](references/controller-runtime.md) を読む。再起動をまたぐ自動復帰を実装していないホストでは保証しない。

## 正本と再開

全体計画が指定されていれば、それを優先順位・依存の正本、Issue等を詳細・受入条件・journalの正本とする。ProjectのReadyは実行候補への射影であり、計画との不整合を隠して選択しない。最小限の整合を先に行う。

PR/commit/CIは実装証跡、spec/ADRは現在の設計、配備記録は実環境の証跡。ローカル索引は参照先・担当・承認・待ち条件・実行ハンドルのみを保持し、第二のタスク台帳を作らない。repoごとに隔離された永続state領域を使え、dirtyな作業ツリーへ記録を混ぜない。secret・個人情報・生ログをjournalへ転記しない。

再開時は索引から既存処理を照合して結果を回収する。記憶、`latest`、mtimeから所有者を推測しない。既存の有効な証跡は再利用し、環境・対象revision・前提が変わった箇所を再確認する。

## 選択と並列化

### 候補と所有権

`github-projects`では次を使う。`CONFIG_DIGEST`はpreflight出力から取得する。

```bash
<skill-dir>/scripts/autopilot_board.py next-task \
  --expected-config-digest "$CONFIG_DIGEST"
```

出力は候補であり実行権限ではない。[collaboration preflight](references/collaboration-preflight.md)をclaim・worktree作成・委任・編集前に実施する。In Progressを無条件に再開しない。同じGitHub assigneeでもsession所有者は異なり得る。

Task identityを確認後、新規候補だけ`github-operations`の`project_task.py claim`を使う。`--repo`、`--owner`、`--project-number`、`--in-progress`、`--item-id`、`--issue-url`、`--issue-number`、`--expected-status`にはadapterが返した値を渡す。再開はjournalで自分の所有権を確認し、assigneeを書き換えない。

claim成功直後、委任・編集前にIssueの`## Progress`へ`controller-run: <run_id>`、task identity、担当worktree、開始時刻を記録する。ローカル索引にも同じ参照を残す。記録失敗時はclaimを繰り返さず現状態を照合し、記録を補うまで着手しない。再開は元run IDを継承して照合し、担当交代は前所有者の停止/引継ぎ根拠を記録する。

controllerをこのrunの唯一の選択・claim担当にする。workerは次タスクを取得しない。実行中・別session所有・未解消の待ち条件があるitemは`--exclude <itemId>`で除外し、理由と再評価条件をjournalへ残す。再開時も復元する。claimは複数controller間の原子的session lockではないため、所有権が曖昧なら該当タスクを止める。

候補nullは「今選べる候補がない」であり、実行中・未回収・確認待ちがあればrun完了ではない。`plan-doc` / `none`は既存adapterの1 run 1件制限を維持し、その1件の独立した作業を委任できる。

### 並列作業

独立した調査・設計・実装は並列化する。上限は利用可能枠、レビュー処理能力、CI・共有環境の容量から決める。明示された直列条件は尊重する。別sessionの存在だけを全体停止の理由にしない。

- 各実装workerに別のtask branch/worktreeと変更範囲を割り当てる。`git-worktrees`の規律を使う。
- dirtyなrootや他者の差分をreset・stash・commit・cleanupしない。自分のtask treeへ隔離する。
- 同じ機能・ファイル・migration番号・共有DB・環境の競合は担当と統合順を調整する。
- merge、共有環境のdeploy/Job/migrationは既存のlockや担当者で対象ごとに直列化する。
- レビュー待ちが積み上がれば新規着手を減らし、回収・受入を優先する。worker数を成果にしない。

## タスクの実行契約

controllerは目的・受入条件・非スコープ・変更範囲・依存・許可操作・検証・提出先をworkerへ渡す。難所は着手前に解消し、局所的な手段はworkerへ委任する。workerによる再委任・第三者レビューは事前に指定した範囲のみ許可する。

通常設計はcontrollerが判断しjournalへ残す。設計の不確実性が高い、不可逆、影響が大きい、controller自身が主要部分を実装する、repoが要求する場合は独立レビューを行う。全件のプランレビューや逆providerを機械的に強制しない。

第三者レビューの要否・対象・観点・モデルはcontrollerが決める。workerが起動する場合も事前委任が必要。原文・対象revision・未検査範囲をcontrollerへ直接確認可能な形で残す。reviewerの再帰起動は禁止。独立レビューのPASSを最終承認としない。

workerは実装、自己点検、必要なテストを実行し、変更revision、コマンド・結果・証跡、既知の不足を提出する。提出は「レビュー待ち」であり出荷可能を意味しない。テストを弱めて通さない。

## controllerの最終ゲート

1. 全成果物の差分と必要な周辺実装を自分で読み、受入条件、正しさ、必要性、境界、文書整合を確認する。
2. `done`または設定された同等ゲートで証跡を確認する。実行はworkerへ委任できるが、自己申告やPASS文字列だけを根拠にしない。同一対象・設定・環境の有効な証跡は再利用する。
3. 第三者指摘を該当箇所と突合し、採否と理由を記録する。修正後は影響範囲の検証と再レビューを行う。必須レビュー不能なら承認しない。
4. commit hookが書き換えた変更も検証対象へ含める。最終commit treeと受入対象treeの一致を確認する。複数PRの個別PASSは統合後の保証ではない。

done configが無い場合は代替ゲートを明示して合意し、doneのPASSを偽装しない。UI/E2Eが必須で手段が無い場合は未完了条件として残す。

## PR・CI・出荷

- feature branchからPRを作る。証跡収集だけのDraft PRではIn Progressを維持し、workerの実装・自己検証が提出されcontrollerのレビューを受けられる段階でreviewへ移す。reviewはcontroller承認済みの意味ではない。mainへ直接commit/pushしない。
- CIは短い状態取得または非同期watchで監視する。controllerを長時間ブロックしない。原因を調べて修正し、同じ決定的失敗を3回機械的に再実行しない。待機は失敗ではない。
- merge直前に対象head、controller承認、required checks、統合状態、権限を再確認する。別PRがbaseを変えた影響は必要な統合検証で確認する。
- deployは許可された公式workflow/configのラッパーを使う。生の`terraform apply`は行わない。実行ID、対象revision、環境、結果を記録する。部分失敗時は後続の状態変更を止め、安全な回収・診断を先に行う。
- `deploy.needed=false`ならdeployを省略する。必要なら承認された`deploy.steps`を記載順にrun→その実行のmonitorとして処理し、成功確認後に次stepへ進む。任意の最新runへ接続せず実行IDを固定する。configへの書込み権限はrun/monitorの任意コマンド実行権限に相当する。
- コード受入、merge、配備、実機受入を区別する。`stagingVerify.method=manual`、MCP不可、`skip`設定だけで必須受入条件を消さない。
- 全必須条件成立後にCompletion evidenceを記録し、adapterのcompleteへ遷移する。squash等でSHAが変わる場合は検証revisionとrelease revisionの対応を残す。

GitHubの状態遷移は既存`autopilot_board.py set-status --project-id ... --item-id ... --phase inReview|done`を使う。`plan-doc`のcheck更新は同じtask PRへ含め、baseへ直接書かない。配備等の必須受入がmerge後に残るならcheckを先に完了にせず、別の承認済みtracking方法を定める。

## 待ち・失敗・内省

回答待ちは依存する操作だけを止める。回答に依存せず成果が使え、未承認の前提を既成事実化せず、最優先作業を遅らせない独立作業を進める。無ければhost-native waitで待機し、稼働率のための仕事は作らない。

局所的な失敗は該当レーンを止める。複数失敗が共通原因を示す場合は新規着手を止めて診断する。外部レビューをすべての詰まりの必須経路にしない。

同じ受入ゲートの修正・再レビューは既定3roundを上限に一旦止め、原因・費消・残る不確実性を再評価する。controllerは既存権限/実行上限内で理由と次の打切り条件を記録して延長できるが、無期限に反復しない。

着手前・出荷前・長い無進展・方針変更・再開時に、大目的へ近づいているか、今必要か、単純に成立しないか、細部へ偏っていないかを短く点検する。基準は`ai-native-engineering`。長文の儀式を作らない。

複数タスクを受け入れた節目では、記録済みのbase/headと統合結果から累積の重複・不要な機構も確認する。merge後に空になるbranch差分だけを根拠にしない。広いrefactorは自動で差し込まず、根拠ある後送課題にする。

根拠ある後送課題は重複を確認し、起票権限があればIssueへ「問題・根拠・今やらない理由・着手条件・受入条件」を残す。自動でReadyにしない。trackerが無ければ索引へ参照可能に残す。

GitHub Issueの起票は`github-issue-create`の言語規則に従う。タイトル・本文は原則日本語とし、ユーザーの別言語指定・対象repoの明示規約がある場合はそれを適用する。workerが英語で提出した内容も、そのままIssueへ転載せずこの規則へ合わせる。

## 終了と引継ぎ

進捗メッセージは終了ではない。実行中・未回収・未処理質問・実行可能な承認済み作業があれば、[継続監視](references/controller-runtime.md)に従って継続する。

終了できるのは目的達成、明示停止/一時停止、実行上限、安全上の停止、または外部条件待ちで有用な作業がなく、再開方法と待ち条件を記録した場合。自動再開すると述べるなら、その機構が実際に登録済みでなければならない。

停止時は所有する処理を把握し、安全に停止・完走回収・明示引継ぎのいずれかを選ぶ。副作用中の処理を安易にkillしない。dirtyなtask treeは保持して所有者と再開点を記録し、clean化のために他者の変更をまとめてcommitしない。

`progress-report`で完了、受入待ち、停止理由、次の判断をまとめる。コード承認をshippedと誤記しない。完了報告にはPR/実環境証跡への参照と未達の必須条件を含める。

## Bootstrap

configが無ければrepoのworkflow・task source候補を読んで雛形を提案し、承認後に作成する。別repoのconfigを借用しない。開始契約が成立するまで外部書込み・worker起動をしない。
