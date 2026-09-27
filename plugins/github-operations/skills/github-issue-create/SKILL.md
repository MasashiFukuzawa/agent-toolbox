---
name: github-issue-create
description: >-
  任意のGitHub Organization／repoへIssueを起票し、Projectへ登録してStatusと明示Priorityを安全に設定するためのdry-run・apply・resumeを提供する。「GitHub Issueを作って」「IssueをProjectへ登録して」を正のトリガーとし、Issue 作成・Project Inbox 登録・途中失敗からの再開に使う。Project自体の新設・構造検証にはgithub-project-provisioningを使う。特定repoのroutingやlabelsを汎用規則として固定する用途には使わない。
---
# GitHub Issue Create

## Safety contract

- Always create a dry-run plan before creating an Issue.
- Treat an explicit user request to create an Issue as authorization to plan and apply that Issue within the stated scope. Do not ask for a second approval merely because the dry-run plan now exists.
- Pause before apply only when the user requested plan/dry-run/review without execution, a material choice remains unresolved, or the observed identity, target, fields, or operations do not match the authorized request and repository policy.
- Fail closed on identity changes, target mismatch, stale plans, missing labels, ambiguous Project fields, or permissions.
- Never infer and write Priority from urgency prose alone. Set it only when the user explicitly selected it or repository policy deterministically supplies it; otherwise omit it. Do not ask solely to populate an optional Priority.
- On partial failure, resume the existing Issue; never create a replacement automatically.
- Apply repository-specific Issue policy when one exists. This skill must not invent routing or labels.
- `--confirm-target` prevents repository mix-ups; it is not an authorization mechanism. Authorization comes from the user's mutation request, while the content-derived `plan_id` rejects edits between plan and apply.

## Issueの出力言語

- Issueのタイトル・本文・見出し・受入条件は**原則日本語**で書く。autopilotが起票する子Issue・後続課題、manifest内の各Issueにも適用する。毎回言語を確認する必要はない。
- ユーザーが別言語を明示した場合、または対象repoに英語必須などの明示的なIssue言語規約がある場合はそれに従う。両者が衝突する場合はapply前に解決する。
- スキルの説明、コード、エラーログ、雛形が英語であることだけを理由に、説明文まで英語へ切り替えない。既存Issueが英語という事実だけでは日本語の既定を上書きしない。
- API名、コード識別子、コマンド、引用ログ、URL、labels、Projectの選択肢名は原文のまま保持する。機械的に参照するテンプレート見出し・キーも保持し、記入する説明を日本語にする。
- 作成済みIssueの言語を揃えるためだけの再起票・無断翻訳はしない。resumeは保存済みplanとIssueを使い、本文変更が必要なら別の更新操作として扱う。

## 実行前提

- Install the complete `github-operations` plugin. A copied skill directory is intentionally unsupported.
- Require Python 3.11+, `gh`, and an explicit config or `.agents/github-operations.json`.
- When using an explicit config from another installed resource, resolve that file to an absolute path and pass it with `--config`.

## Workflow

Resolve `scripts/run.py` against this skill directory before executing it.

1. Draft the Issue using the target repository's `AGENTS.md`, templates, and available labels. Apply the output-language policy above before creating the plan; verify title and body language during dry-run inspection.
2. Write a long body to a temporary file outside the repository, then plan:

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

   Omit label, assignee, or Priority when not explicitly justified.

   For multiple Issues, create a version 1 JSON manifest using
   [`references/manifest.md`](references/manifest.md), then plan once:

   ```bash
   python3 <skill-dir>/scripts/run.py plan \
     --config <config> \
     --manifest <manifest.json>
   ```

   Do not combine `--manifest` with single-Issue flags. Inspect the distinct repository list,
   entry count, every operation, and the generated fingerprints before apply.

3. Inspect all returned fields, operations, `plan_id`, target, authenticated identity, and expiry. If they match the authorized request and repository policy, apply in the same turn without another approval prompt. If the user requested a dry-run only, display the plan and stop.
4. Apply the matching plan:

   ```bash
   python3 <skill-dir>/scripts/run.py apply --plan-id <id> --confirm-target '<target-from-plan>'
   ```

5. If creation succeeded but Project registration or field editing failed, show the existing Issue URL and remaining steps. Resume the same plan without recreating the Issue when the original request still authorizes the remaining operations:

   ```bash
   python3 <skill-dir>/scripts/run.py resume --plan-id <id> --confirm-target '<target-from-plan>'
   ```

   A manifest apply can return exit code `1` after partial success. Treat its stdout JSON as the
   durable per-entry result, report completed entries, and resume the same plan. Exit code `2`
   means the operation was rejected before it could be proven safe.

If apply reports a stale lock, verify that its process is no longer running, then clear only the confirmed target with `run.py unlock --target '<owner/repo>' --confirm-target '<owner/repo>'`.

## Output contract

- Requested dry-run: identity, repo, title, body, labels, assignee, Project, Status, Priority, and every mutation; do not apply.
- Success: Issue URL, Project item ID, applied fields, and verification result.
- Partial failure: existing Issue URL, completed steps, remaining steps, and safe resume command.
- Manifest success: plan ID, target guard, total/completed counts, and per-entry Issue URL, Project item ID, and state.
- Manifest partial failure: the same machine-readable summary on stdout plus an actionable error on stderr.
