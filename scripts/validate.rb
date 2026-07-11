#!/usr/bin/env ruby
require "json"
require "yaml"

ROOT = File.expand_path("..", __dir__)
errors = []
warnings = []
skills = {}

Dir.glob(File.join(ROOT, "plugins/*/skills/*/SKILL.md")).sort.each do |path|
  text = File.read(path, encoding: "UTF-8")
  match = text.match(/\A---\s*\n(.*?)\n---\s*\n/m)
  unless match
    errors << "missing frontmatter: #{path}"
    next
  end
  begin
    metadata = YAML.safe_load(match[1], permitted_classes: [], aliases: false)
  rescue => e
    errors << "invalid YAML: #{path}: #{e.message}"
    next
  end
  name = File.basename(File.dirname(path))
  errors << "frontmatter keys must be name, description: #{path}" unless metadata.keys.sort == %w[description name]
  errors << "name/directory mismatch: #{path}" unless metadata["name"] == name
  errors << "invalid kebab-case name: #{name}" unless name.match?(/\A[a-z0-9]+(?:-[a-z0-9]+)*\z/)
  description = metadata["description"].to_s
  errors << "description exceeds 500 chars: #{name}" if description.length > 500
  errors << "description is below 120-char target: #{name}" if description.length < 120
  warnings << "description exceeds 300-char warning: #{name}" if description.length > 300
  sentences = description.split(/[。！？]/).reject(&:empty?)
  has_positive = description.match?(/(?:時|依頼|場合|前|障害|検証|確認|調査|レビュー|参照|開発|実装).*使う|正のトリガー/)
  has_negative = description.match?(/使わない|には.+を使う|なら.+を使う|限定する|限定し/)
  errors << "description must express purpose, positive trigger, and negative boundary: #{name}" if sentences.length < 3 || !has_positive || !has_negative
  errors << "description should use folded scalar: #{name}" unless match[1].match?(/^description:\s*>-\s*$/)
  errors << "SKILL.md exceeds 500 lines: #{name}" if text.lines.length > 500
  skills[name] = description
end

total = skills.values.sum(&:length)
errors << "toolbox descriptions exceed 4500 chars: #{total}" if total > 4500

plugin_names = Dir.glob(File.join(ROOT, "plugins/*")).select { |path| File.directory?(path) }.map { |path| File.basename(path) }.sort
plugin_names.each do |name|
  codex_path = File.join(ROOT, "plugins", name, ".codex-plugin/plugin.json")
  claude_path = File.join(ROOT, "plugins", name, ".claude-plugin/plugin.json")
  [codex_path, claude_path].each do |manifest_path|
    begin
      manifest = JSON.parse(File.read(manifest_path))
      errors << "manifest name mismatch: #{manifest_path}" unless manifest["name"] == name
    rescue => e
      errors << "invalid or missing manifest #{manifest_path}: #{e.message}"
    end
  end
end

begin
  codex_marketplace = JSON.parse(File.read(File.join(ROOT, ".agents/plugins/marketplace.json")))
  claude_marketplace = JSON.parse(File.read(File.join(ROOT, ".claude-plugin/marketplace.json")))
  codex_names = codex_marketplace.fetch("plugins").map { |plugin| plugin.fetch("name") }.sort
  claude_names = claude_marketplace.fetch("plugins").map { |plugin| plugin.fetch("name") }.sort
  errors << "Codex marketplace/plugin drift" unless codex_names == plugin_names
  errors << "Claude marketplace/plugin drift" unless claude_names == plugin_names
rescue => e
  errors << "invalid marketplace manifest: #{e.message}"
end

Dir.glob(File.join(ROOT, "evals/results/*.json")).each do |result_path|
  begin
    result = JSON.parse(File.read(result_path))
    rows = result.fetch("results")
    summary = result.fetch("summary")
    errors << "trigger result total mismatch: #{result_path}" unless summary.fetch("total") == rows.length
    %w[passed failed not_run].each do |status|
      errors << "trigger result #{status} mismatch: #{result_path}" unless summary.fetch(status) == rows.count { |row| row.fetch("status") == status }
    end
  rescue => e
    errors << "invalid trigger result #{result_path}: #{e.message}"
  end
end

registry_path = File.join(ROOT, "docs/trigger-registry.yml")
registry = YAML.safe_load(File.read(registry_path), permitted_classes: [], aliases: true).fetch("skills")
missing = skills.keys - registry.keys
extra = registry.keys - skills.keys
errors << "trigger registry missing: #{missing.join(', ')}" unless missing.empty?
errors << "trigger registry has unknown skills: #{extra.join(', ')}" unless extra.empty?
required = %w[canonical_name category supported_hosts runtime_dependencies side_effect_level positive_triggers nearest_neighbors negative_triggers ambiguous_precedence renamed_from]
registry.each do |name, entry|
  errors << "registry fields missing for #{name}: #{(required - entry.keys).join(', ')}" unless (required - entry.keys).empty?
  errors << "registry canonical_name mismatch: #{name}" unless entry["canonical_name"] == name
  Array(entry["nearest_neighbors"]).each { |ref| errors << "unknown nearest neighbor #{ref} from #{name}" unless skills.key?(ref) }
end

banned = {
  "absolute macOS home path" => %r{/Users/[^/\s]+/},
  "email address" => /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i,
  "legacy license/source marker" => /everything-claude-code|cloudflare-starterkit|\bMIT License\b/i,
  "legacy skill reference" => /done@|worktree-flow|write-meaningful-tests|documentation-lookup|research-first/
}
Dir.glob(File.join(ROOT, "**/*"), File::FNM_DOTMATCH).select { |p| File.file?(p) && !p.include?("/.git/") }.each do |path|
  next if File.expand_path(path) == File.expand_path(__FILE__)
  content = File.read(path, encoding: "UTF-8") rescue next
  banned.each do |label, pattern|
    next if label == "legacy skill reference" && [registry_path, File.join(ROOT, "docs/skill-conventions.md")].include?(path)
    errors << "#{label}: #{path}" if content.match?(pattern)
  end
end
errors << "private case study must not be published" unless Dir.glob(File.join(ROOT, "**/case-study.md")).empty?

if errors.empty?
  warnings.each { |warning| warn "warning: #{warning}" }
  puts "validation: PASS (#{skills.length} skills, #{total} description chars)"
else
  warn errors.uniq.join("\n")
  exit 1
end
