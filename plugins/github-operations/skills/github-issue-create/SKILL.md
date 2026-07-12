---
name: github-issue-create
description: >-
  任意のGitHub Organization／repoへIssueを起票し、Projectへ登録してStatusと明示Priorityを安全に設定するためのdry-run・apply・resumeを提供する。Issue作成、Project Inbox登録、途中失敗からの再開を正のトリガーとして使う。Project自体の新設・構造検証にはgithub-project-provisioningを使う。特定repoのroutingやlabelsを汎用規則として固定する用途には使わない。
---
# GitHub Issue Create

## Safety contract

- Always create a dry-run plan before creating an Issue.
- Never apply without explicit approval of owner/repo, title, body, labels, assignee, Project, Status, and Priority.
- Fail closed on identity changes, target mismatch, stale plans, missing labels, ambiguous Project fields, or permissions.
- Never infer and write Priority from prose alone. Present an inferred value as a proposal and require explicit approval.
- On partial failure, resume the existing Issue; never create a replacement automatically.
- Apply repository-specific Issue policy when one exists. This skill must not invent routing or labels.
- `--confirm-target` prevents repository mix-ups; it does not prove human approval. Human approval remains a host-level interaction requirement. The content-derived `plan_id` rejects edits to the approved title, body, labels, fields, or operations.

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

3. Display all returned fields, operations, `plan_id`, target, authenticated identity, and expiry. Ask for explicit approval.
4. Apply only the approved plan:

   ```bash
   python3 <skill-dir>/scripts/run.py apply --plan-id <id> --confirm-target '<owner/repo>'
   ```

5. If creation succeeded but Project registration or field editing failed, show the existing Issue URL and remaining steps. After approval, run:

   ```bash
   python3 <skill-dir>/scripts/run.py resume --plan-id <id> --confirm-target '<owner/repo>'
   ```

If apply reports a stale lock, verify that its process is no longer running, then clear only the confirmed target with `run.py unlock --target '<owner/repo>' --confirm-target '<owner/repo>'`.

## Output contract

- Dry-run: identity, repo, title, body, labels, assignee, Project, Status, Priority, and every mutation.
- Success: Issue URL, Project item ID, applied fields, and verification result.
- Partial failure: existing Issue URL, completed steps, remaining steps, and safe resume command.
