#!/usr/bin/env bash
# quality-gate-stop.sh (done 汎用版)
# Gates session stop when uncommitted changes exist.
#
# Opt-in: the gate is active ONLY in repos that have .agents/done.yml at the
# git root. Repos without the config are never blocked (plugin can be installed
# user-wide with zero side effects). The repo name is read from done.yml.
#
# Signature-only intent: the hook validates ONLY when the LAST assistant message
# carries a complete quality-gate signature. A turn without that signature
# (answer-only, planning, handoff, or prose that merely mentions "quality-gate")
# is allowed to stop -- this is intentional, see the done skill scope policy.
#
# When a complete signature is present, head and verification-tree are read
# directly FROM the signature text (no marker file): the agent stores evidence in the
# session-scoped transcript, which is never shared across worktrees, so the
# linked-worktree evidence problem does not arise here.
#
# Wired from both the Claude (.claude/settings.json) and Codex (.codex/hooks.json)
# Stop hooks; the python3 parser handles Claude JSONL and Codex transcripts.

set -euo pipefail

HOOK_INPUT="$(cat)"

json_field() {
  local field="$1"
  python3 - "$field" "$HOOK_INPUT" <<'PY'
import json
import sys

field = sys.argv[1]
raw = sys.argv[2]
try:
    value = json.loads(raw).get(field)
except Exception:
    value = None
if value is not None:
    print(value)
PY
}

allow() {
  printf '{}\n'
  exit 0
}

block() {
  local reason="$1"
  python3 - "$reason" <<'PY'
import json
import sys

print(json.dumps({"decision": "block", "reason": sys.argv[1]}))
PY
  exit 0
}

# Prevent infinite loop: if the stop hook already fired and blocked, allow stop.
stop_active="$(json_field stop_hook_active)"
if [[ "$stop_active" == "True" || "$stop_active" == "true" ]]; then
  allow
fi

ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT_DIR" ]]; then
  allow
fi
cd "$ROOT_DIR"

# Opt-in: no .agents/done.yml -> this repo does not use the done gate.
DONE_CONFIG="$ROOT_DIR/.agents/done.yml"
if [[ ! -f "$DONE_CONFIG" ]]; then
  allow
fi

# repo name comes from the config (worktree dir names differ from the repo name).
REPO_NAME="$(sed -n 's/^repo:[[:space:]]*//p' "$DONE_CONFIG" | head -1 | tr -d '"'"'"'"' )"
if [[ -z "$REPO_NAME" ]]; then
  allow
fi

# No uncommitted changes (tracked or untracked): nothing to gate.
if [[ -z "$(git status --porcelain=v1 -uall 2>/dev/null || true)" ]]; then
  allow
fi

current_head="$(git rev-parse HEAD)"

compute_verification_tree() {
  local tmp_index
  tmp_index="$(mktemp "${TMPDIR:-/tmp}/quality-gate-index.XXXXXX")"
  rm -f "$tmp_index"
  trap 'rm -f "$tmp_index"' RETURN
  GIT_INDEX_FILE="$tmp_index" git read-tree HEAD
  GIT_INDEX_FILE="$tmp_index" git add -A
  GIT_INDEX_FILE="$tmp_index" git write-tree
}

current_tree="$(compute_verification_tree)"

# Extract repo/head/tree/tier from the complete quality-gate signature in the
# LAST assistant message of the transcript. Prints a tab-separated record, or
# nothing when no complete signature is present (signature-only intent).
latest_signature() {
  local transcript_path="$1"
  [[ -n "$transcript_path" && -r "$transcript_path" ]] || return 1
  python3 - "$transcript_path" <<'PY'
import json
import re
import sys

path = sys.argv[1]
try:
    text = open(path, "r", encoding="utf-8").read()
except Exception:
    sys.exit(1)

# Match both escaped ("\n" inside a JSON string) and real newlines so the same
# pattern works for Claude JSONL transcripts and Codex transcripts. The repo is
# captured (not hardcoded) so the bash side can report a repo mismatch.
newline = r"(?:\\n|\r?\n)"
signature_pattern = re.compile(
    rf"quality-gate:\s*PASS{newline}\s*"
    rf"repo:\s*(?P<repo>[A-Za-z0-9._-]+){newline}\s*"
    rf"head:\s*(?P<head>[0-9a-f]{{40}}){newline}\s*"
    rf"verification-tree:\s*(?P<tree>[0-9a-f]{{40}}){newline}\s*"
    rf"tier:\s*(?P<tier>quick|standard|full)\b",
    re.IGNORECASE,
)


def iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)


def find_role(value):
    if isinstance(value, dict):
        role = value.get("role")
        if role in {"assistant", "user"}:
            return role
        for item in value.values():
            nested = find_role(item)
            if nested:
                return nested
    elif isinstance(value, list):
        for item in value:
            nested = find_role(item)
            if nested:
                return nested
    return None


def emit(match):
    sys.stdout.write(
        "\t".join(
            (
                match.group("repo"),
                match.group("head"),
                match.group("tree"),
                match.group("tier"),
            )
        )
    )


# Primary path: structured JSONL (Claude). Inspect only the LAST assistant message
# so a PASS followed by a fresh user turn does not keep the stale signature alive.
messages = []
for line in text.splitlines():
    try:
        data = json.loads(line)
    except Exception:
        continue
    role = find_role(data)
    if role in {"assistant", "user"}:
        messages.append((role, "\n".join(iter_strings(data))))

if messages:
    role, payload = messages[-1]
    if role == "assistant":
        match = signature_pattern.search(payload)
        if match:
            emit(match)
    sys.exit(0)

# Fallback: unstructured transcript. Accept the signature only when the last
# signature appears after the last user-turn marker.
matches = list(signature_pattern.finditer(text))
if not matches:
    sys.exit(0)
last_sig = matches[-1]
last_user = max(
    text.rfind('"role":"user"'),
    text.rfind('"role": "user"'),
    text.rfind("'role':'user'"),
    text.rfind("'role': 'user'"),
    text.rfind('"type":"user_message"'),
    text.rfind('"type": "user_message"'),
    text.rfind("<|start|>user"),
    text.rfind("hook_prompt"),
)
if last_sig.start() > last_user:
    emit(last_sig)
PY
}

transcript_path="$(json_field transcript_path)"
signature="$(latest_signature "$transcript_path" || true)"

# Signature-only intent: no complete signature in the last assistant message
# means this is not a completion turn (answer/planning/handoff) -> allow.
if [[ -z "$signature" ]]; then
  allow
fi

IFS=$'\t' read -r sig_repo sig_head sig_tree sig_tier <<<"$signature"

if [[ "$sig_repo" != "$REPO_NAME" ]]; then
  block "quality-gate: PASS signature is for repo '$sig_repo', not '$REPO_NAME'. Run the done skill in this repo before stopping."
fi

if [[ "$sig_head" != "$current_head" ]]; then
  block "quality-gate head mismatch: signature has $sig_head but current HEAD is $current_head. Re-run the done skill after rebasing or committing."
fi

if [[ "$sig_tree" != "$current_tree" ]]; then
  block "quality-gate verification-tree mismatch: signature has $sig_tree but current worktree is $current_tree. Re-run verification after the latest edits."
fi

allow
