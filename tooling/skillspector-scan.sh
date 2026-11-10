#!/usr/bin/env bash
set -euo pipefail

ref="38a1dfe93325d2f8bfcd4f8d0241eed706334915" # v2.13.3
if ! command -v skillspector >/dev/null 2>&1; then
  command -v uv >/dev/null 2>&1 || python3 -m pip install --quiet --user uv
  export PATH="$HOME/.local/bin:$PATH"
  uv tool install --quiet --python 3.14 "git+https://github.com/NVIDIA/skillspector.git@$ref"
fi

out_dir=${1:-/tmp/skillspector}
shift || true
mkdir -p "$out_dir"
if [[ $# -eq 0 ]]; then
  set -- plugins/*/skills/* .agents/skills/*
fi
for skill_dir in "$@"; do
  [[ -f "$skill_dir/SKILL.md" ]] || continue
  name=${skill_dir#plugins/}
  name=${name/#.agents\/skills\//repo__}
  name=${name/\/skills\//__}
  skillspector scan "$skill_dir" --format json --output "$out_dir/$name.json" --no-llm
done
