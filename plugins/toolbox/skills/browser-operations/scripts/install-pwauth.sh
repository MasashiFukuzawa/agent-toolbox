#!/usr/bin/env bash
set -euo pipefail

command -v playwright-cli >/dev/null || {
  echo "playwright-cli is required. Install a reviewed, pinned @playwright/cli version first." >&2
  exit 1
}

help_text="$(playwright-cli open --help 2>&1 || true)"
for flag in --persistent --profile --browser --headed; do
  grep -q -- "$flag" <<<"$help_text" || {
    echo "The installed playwright-cli does not expose required flag: $flag" >&2
    exit 1
  }
done
grep -Eq -- '(^|[[:space:]])-s([=,[:space:]]|$)' <<<"$help_text" || {
  echo "The installed playwright-cli does not expose required session flag: -s" >&2
  exit 1
}

install_dir="${HOME}/.local/bin"
profile_root="${HOME}/.mcp/browser-profiles"
mkdir -p "$install_dir" "$profile_root"
chmod 700 "${HOME}/.mcp" "$profile_root"
install -m 755 "$(dirname "$0")/pwauth" "$install_dir/pwauth"
echo "Installed $install_dir/pwauth"
