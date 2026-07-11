#!/usr/bin/env bash
set -euo pipefail

ref="326a2b489411a20ed742ff13701be39ba00063c8"
if ! command -v skillspector >/dev/null 2>&1; then
  command -v uv >/dev/null 2>&1 || python3 -m pip install --quiet --user uv
  export PATH="$HOME/.local/bin:$PATH"
  uv tool install --quiet --python 3.12 "git+https://github.com/NVIDIA/skillspector.git@$ref"
fi

out_dir=${1:-/tmp/skillspector}
shift || true
mkdir -p "$out_dir"
if [[ $# -eq 0 ]]; then
  set -- plugins/*/skills/*
fi
for skill_dir in "$@"; do
  [[ -f "$skill_dir/SKILL.md" ]] || continue
  name=${skill_dir#plugins/}
  name=${name/\/skills\//__}
  skillspector scan "$skill_dir" --format json --output "$out_dir/$name.json" --no-llm
done
