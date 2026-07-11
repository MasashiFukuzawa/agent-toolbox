#!/usr/bin/env ruby
require "json"
require "open3"
require "tmpdir"
require "yaml"

payload = JSON.parse($stdin.read)
root = File.expand_path("..", __dir__)
skills = Dir.glob(File.join(root, "plugins/*/skills/*/SKILL.md")).sort.to_h do |path|
  metadata = YAML.safe_load(File.read(path).split(/^---\s*$/, 3)[1])
  [metadata.fetch("name"), metadata.fetch("description")]
end
catalog = skills.map { |name, description| "- #{name}: #{description}" }.join("\n")
if payload.fetch("environment") == "superset"
  catalog += "\n- generic-writing: 一般文章を編集する。専門的な開発workflowには使わない。\n- task-planning: 単純な作業計画を作る。実行や品質ゲートには使わない。"
end
prompt = <<~PROMPT
  You are evaluating skill-trigger metadata for #{payload.fetch("host")}. Select only from the catalog below, or return none, disambiguate, or ask-provider.
  Do not infer an expected answer from evaluation metadata. Judge only the user prompt and descriptions.
  Return exactly one JSON object: {"selected_skill":"<value>"}

  Catalog:
  #{catalog}

  User prompt:
  #{payload.fetch("case").fetch("prompt")}
PROMPT

host = payload.fetch("host")
stdout, stderr, status = if host == "claude-code"
  Open3.capture3("claude", "-p", prompt)
else
  output = File.join(Dir.tmpdir, "trigger-eval-#{Process.pid}.txt")
  _out, err, process = Open3.capture3("codex", "exec", "--sandbox", "read-only", "-o", output, prompt)
  [File.exist?(output) ? File.read(output) : "", err, process]
end
abort(stderr.empty? ? "model command failed" : stderr) unless status.success?
match = stdout.match(/\{\s*"selected_skill"\s*:\s*"([^"]+)"\s*\}/m)
abort("model did not return selected_skill JSON") unless match
puts JSON.generate(selected_skill: match[1])
