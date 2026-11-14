---
name: github-project-provisioning
description: >-
  GitHub Organization Projectの期待構造を調査し、既存Projectのcopyまたは契約からの0→1 bootstrap、repo link・auto-addを含む変更計画を作成して承認後に適用・検証する。「Organization Projectを作って」「Project構造を検証して」を正のトリガーとし、Project 新設・構造 drift 確認・複数 repo の運用 Project 導入に使う。Issueを1件起票するだけの場合にはgithub-issue-createを使い、特定Organizationの規約を汎用設定として固定する用途には使わない。
---
# GitHub Project Provisioning

## 安全契約

- `inspect` か `plan` から始める。どちらのコマンドも、GitHubや追跡ファイルを変更しない。
- 表示したplanと正確な対象をユーザーが明示的に承認するまで、`apply` を実行しない。
- 承認を得る前に、認証済みのアカウント、owner、repository、Projectのタイトル、予定しているすべての変更を、あらためて示す。
- identity・対象・configのdigest・stateのdigestの不一致、権限の不足、名前の重複は、実行せずに失敗させる。
- viewやworkflowを、削除・改名・archive・無断で修復しない。
- このskillを書いたり試したりするだけの目的で、実際のOrganization Projectを作らない。ユーザーが頼んだbootstrapは運用上の変更であり、inspect、plan、明示的な承認の関門を通す。
- `--confirm-target` は対象の取り違えを防ぐもので、承認の仕組みではない。人の承認は、hostでのやり取りとして必要である。内容から導く `plan_id` が、承認済みのplanファイルがapplyの前に編集されることを防ぐ。

## 実行前提

- `github-operations` pluginを丸ごと導入する。skillのdirectoryだけを複製した構成は、意図的に対象外としている。
- Python 3.11以上、`gh`、認証済みのGitHubアカウント、Projectのscopeが要る。
- 明示したconfigか、現在のgit rootの `.agents/github-operations.json` を使う。作る前に [configの契約](references/config.md) を読む。

## 手順

`scripts/run.py` は、実行の前に、このskillのdirectoryを基準に解決する。対象repositoryの作業directoryから、相対pathのまま実行しない。

1. 対象と認証を、読み取りだけで調べる。

   ```bash
   python3 <skill-dir>/scripts/run.py inspect --config <config>
   ```

2. 読み取りだけのplanを作る。

   ```bash
   python3 <skill-dir>/scripts/run.py plan --config <config>
   ```

3. 返されたidentity、対象、templateか `bootstrap` か、repository、操作、ブラウザでの作業が要る項目、`plan_id`、有効期限をまとめ、明示的な承認を求める。
4. 承認の後にだけ、`target` の値をそのまま `--confirm-target` に写す。

   ```bash
   python3 <skill-dir>/scripts/run.py apply --plan-id <id> --confirm-target '<owner/project-title>'
   ```

5. `verify` を実行する。ブラウザでの作業が要ると報告されたら、APIの結果は部分的なものとして扱う。組み込みworkflowの遷移先のstatus、viewのgrouping、auto-addの設定は、分けて報告する。それらの状態の変更には `browser-operations` を使い、変更ごとに確認を得る。

Projectのbootstrap・copyや、repositoryのlinkが途中で止まったら、journalと現在のProjectを示して承認を得てから、元の（内容から導いた）plan IDで `resume` を使う。resumeは、作成済みのProjectを作り直したりcopyし直したりせず、差分を埋める。

applyが古いlockを報告したら、まず、記録されたプロセスがもう動いていないことを確かめる。対象を明示的に確認した後、その対象だけを `run.py unlock --target '<target>' --confirm-target '<target>'` で解除する。動いているlockは消さない。

## 契約としての挙動

- `project.template` がある場合、ownerとタイトルで一意に解決し、draft itemを含めずにcopyする。
- `project.template` が無い場合、対象のProjectが無ければ、意味上の契約から作る。templateの要件を満たすためだけに、別のOrganizationのProjectで代用しない。
- bootstrapは、公開APIでfieldとviewを作成・調整し、fieldの更新では既存のoptionのIDを保つ。別のProjectから、item、repository、view、workflow、説明、履歴を持ち込まない。
- viewと組み込みworkflowは、検証の契約である。copyした構造がずれていて、公開APIで安全に直せないなら、手作業での対処を示して止まる。
- 公開APIで確かめられるのは、workflowの名前と有効・無効までで、ブラウザで設定するStatusの遷移先は確かめられない。workflowのentryは `set_status` を宣言できるが、この値は手作業で確かめる。標準の契約の遷移は次のとおり：Item added → `Inbox`、Pull request linked to issue → linkされたIssueを `In Review`、Code changes requested → `In Progress`、Pull request merged → `Done`、Item closed → `Done`、Item reopened → `In Progress`。sub-issueとauto-closeのworkflowは無効にする。
- bootstrapでは、viewのgroupingと組み込みworkflowの設定を、ブラウザでの作業が要る操作として出力し、applyの後に `browser-operations` で完了させる。それらを確かめるまで、検証が完了したと報告しない。
- repositoryのauto-addは、指定した時だけ有効にする。無効のままにするなら `auto_add` を省く。頼まれた場合は、planが追加のauto-add workflowを明示的に扱っていない限り、既定のrepositoryだけを設定する。ほかのrepositoryは、Issue Form、明示的なIssueの登録、手作業での追加で補う。
- areaのlabelと、repository固有のroutingは、このskillの対象外である。
