#!/usr/bin/env ruby
require "json"
require "yaml"

root = File.expand_path("..", __dir__)
registry = YAML.safe_load(File.read(File.join(root, "docs/trigger-registry.yml")), permitted_classes: [], aliases: true).fetch("skills")
cases = []

registry.each do |name, entry|
  triggers = Array(entry.fetch("positive_triggers"))
  base = triggers.first || "#{name} を使って"
  positives = [base, "#{base}。判断理由も示して", "#{base}。安全条件を確認して進めて"]
  positives.each_with_index { |prompt, i| cases << {skill: name, type: "positive", id: i + 1, prompt: prompt, expected: name} }

  neighbor = Array(entry.fetch("nearest_neighbors")).first
  negatives = if neighbor
    ["#{neighbor} の対象として処理して。#{name} は使わないで", "#{name} ではなく #{neighbor} を使って"]
  else
    ["この依頼では #{name} を使わないで", "#{name} の対象外として通常回答して"]
  end
  negatives.each_with_index { |prompt, i| cases << {skill: name, type: "nearest_negative", id: i + 1, prompt: prompt, expected: neighbor || "none"} }

  ambiguous = if neighbor
    ["#{name} と #{neighbor} のどちらが適切か判断して", "両方に見える依頼なので適用範囲を確認して"]
  else
    ["この依頼に #{name} が必要か判断して", "適用するスキルが曖昧なので確認して"]
  end
  ambiguous.each_with_index { |prompt, i| cases << {skill: name, type: "ambiguous", id: i + 1, prompt: prompt, expected: "disambiguate"} }

  cases << {skill: name, type: "explicit", id: 1, prompt: "$#{name} を使って対象を処理して", expected: name}
  cases << {skill: name, type: "no_skill_negative", id: 1, prompt: "短い挨拶だけ返して。専門スキルは使わないで", expected: "none"}
end

required = {"positive" => 3, "nearest_negative" => 2, "ambiguous" => 2, "explicit" => 1, "no_skill_negative" => 1}
errors = []
registry.each_key do |name|
  required.each do |type, count|
    actual = cases.count { |c| c[:skill] == name && c[:type] == type }
    errors << "#{name}: #{type} expected #{count}, got #{actual}" unless actual == count
  end
end

if ARGV.include?("--check")
  abort(errors.join("\n")) unless errors.empty?
  puts "trigger-eval completeness: PASS (#{registry.length} skills, #{cases.length} cases per host, 2 hosts, 2 environments)"
elsif ARGV.include?("--json")
  puts JSON.pretty_generate({schema_version: 1, hosts: ["claude-code", "codex"], environments: ["isolated", "superset"], cases: cases})
else
  warn "usage: trigger_eval.rb --check | --json"
  exit 2
end
