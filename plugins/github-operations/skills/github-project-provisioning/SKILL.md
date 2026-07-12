---
name: github-project-provisioning
description: >-
  GitHub Organization Projectの期待構造を調査し、copy・repo link・auto-addを含む変更計画を作成して承認後に適用・検証する。Project新設、構造drift確認、複数repoの運用Project導入時に使う。Issueを1件起票するだけの場合にはgithub-issue-createを使い、特定Organizationの規約を汎用設定として固定する用途には使わない。
---
# GitHub Project Provisioning

## Safety contract

- Start with `inspect` or `plan`. Neither command may mutate GitHub or tracked files.
- Never run `apply` until the user explicitly approves the displayed plan and exact target.
- Re-display the authenticated account, owner, repositories, Project title, and every planned mutation before approval.
- Treat mismatched identity, target, config digest, state digest, missing permissions, and duplicate names as hard failures.
- Do not delete, rename, archive, or silently repair views/workflows.
- Do not create a live Organization Project while merely authoring or testing this skill.
- `--confirm-target` prevents target mix-ups; it is not an authorization mechanism. Human approval remains a host-level interaction requirement. The content-derived `plan_id` prevents an approved plan file from being edited before apply.

## Prerequisites

- Install the complete `github-operations` plugin. A copied skill directory is intentionally unsupported.
- Require Python 3.11+, `gh`, an authenticated GitHub account, and Project scopes.
- Use an explicit config or `.agents/github-operations.json` at the current git root. Read [the config contract](references/config.md) before creating one.

## Workflow

Resolve `scripts/run.py` against this skill directory before executing it; do not run a bare relative path from the target repository's working directory.

1. Inspect the target and authentication read-only:

   ```bash
   python3 <skill-dir>/scripts/run.py inspect --config <config>
   ```

2. Produce the read-only plan:

   ```bash
   python3 <skill-dir>/scripts/run.py plan --config <config>
   ```

3. Summarize the returned identity, target, template, repositories, operations, browser-required work, `plan_id`, and expiry. Ask for explicit approval.
4. Only after approval, copy the exact `target` value into `--confirm-target`:

   ```bash
   python3 <skill-dir>/scripts/run.py apply --plan-id <id> --confirm-target '<owner/project-title>'
   ```

5. Run `verify`. Report any browser-required auto-add configuration separately. Use `browser-operations` for that state change and obtain confirmation for each change.

If Project copy or repository linking stops partway through, display the journal and current Project, obtain approval, and use `resume` with the original content-derived plan ID. Resume reconciles an already-created Project instead of copying it again.

If apply reports a stale lock, first verify that the recorded process is no longer running. After explicit target confirmation, clear only that target with `run.py unlock --target '<target>' --confirm-target '<target>'`; never delete an active lock.

## Contract behavior

- A template is resolved uniquely by owner and title. Copy without draft items.
- Views and built-in workflows are a verification contract. If the copied structure drifts and the public API cannot safely repair it, stop with manual remediation.
- Free or unknown plans should use one built-in auto-add workflow for the default repository; supplement other repositories through Issue Forms, explicit Issue registration, or manual addition.
- Area labels and repository-specific routing are outside this skill.
