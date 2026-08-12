# Collaboration preflight

task-source の状態だけを「他者が作業していない」根拠にしてはならない。候補タスクをread-onlyで
選択した後、claim、worktree作成、計画、サブエージェントへの分割、コード編集、migration番号の確保より
前に、利用可能なcollaboration surfaceを照合する。

1. VCS hostingが使える場合は、Issue番号・タスクURL・タイトルの主要語を参照するopen/draft PR・MR、
   `Refs` / `Closes`、head branch、author、stacked/依存関係を確認する。
2. remote branchと`git worktree list`を確認し、同じタスクまたは同じ能力を扱う進行中差分を探す。
3. trackerが使える場合は、担当者、着手記録、関連change request、親子・依存タスクを確認する。
4. 同じIssue番号や編集ファイルだけでなく、要求、domain ownership、永続化、API、runtime authority、
   migrationなどの意味論上の重複を比較する。stacked changeは最後の累積headを完成形として扱う。

人間または別agentが所有する重複作業を見つけた場合は、新規実装もclaimも行わない。既存change requestを
正本候補としてread-only監査し、現タスクとのcapability matrixを作り、不足を既存discussion surfaceへ返す。
正本が不明な場合だけ人間へエスカレーションする。

結果と未確認範囲は、書込み可能なdurable journalがあれば`## Collaboration preflight`として記録する。
trackerやchange requestがない場合はrun reportへ記録し、記録先を作るためのshadow Issueやsynthetic statusは
作らない。claimを伴うadapterは、衝突なしの根拠を記録した後だけclaimする。
