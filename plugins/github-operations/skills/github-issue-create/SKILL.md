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

## Prerequisites

- Install the complete `github-operations` plugin. A copied skill directory is intentionally unsupported.
- Require Python 3.11+, `gh`, and an explicit config or `.agents/github-operations.json`.
- When using an explicit config from another installed resource, resolve that file to an absolute path and pass it with `--config`.

## Workflow

Resolve `scripts/run.py` against this skill directory before executing it.

1. Draft the Issue using the target repository's `AGENTS.md`, templates, language, and available labels.
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

3. Inspect all returned fields, operations, `plan_id`, target, authenticated identity, and expiry. If they match the authorized request and repository policy, apply in the same turn without another approval prompt. If the user requested a dry-run only, display the plan and stop.
4. Apply the matching plan:

   ```bash
   python3 <skill-dir>/scripts/run.py apply --plan-id <id> --confirm-target '<owner/repo>'
   ```

5. If creation succeeded but Project registration or field editing failed, show the existing Issue URL and remaining steps. Resume the same plan without recreating the Issue when the original request still authorizes the remaining operations:

   ```bash
   python3 <skill-dir>/scripts/run.py resume --plan-id <id> --confirm-target '<owner/repo>'
   ```

If apply reports a stale lock, verify that its process is no longer running, then clear only the confirmed target with `run.py unlock --target '<owner/repo>' --confirm-target '<owner/repo>'`.

## Output contract

- Requested dry-run: identity, repo, title, body, labels, assignee, Project, Status, Priority, and every mutation; do not apply.
- Success: Issue URL, Project item ID, applied fields, and verification result.
- Partial failure: existing Issue URL, completed steps, remaining steps, and safe resume command.
