#!/usr/bin/env ruby
require "json"
require "open3"
require "optparse"
require "time"

options = {output: "evals/results/latest.json", limit: nil, sample: nil, command: nil}
OptionParser.new do |parser|
  parser.on("--output PATH") { |value| options[:output] = value }
  parser.on("--limit N", Integer) { |value| options[:limit] = value }
  parser.on("--sample N", Integer) { |value| options[:sample] = value }
  parser.on("--command COMMAND") { |value| options[:command] = value }
end.parse!

root = File.expand_path("..", __dir__)
cases_json, status = Open3.capture2("ruby", File.join(root, "scripts/trigger_eval.rb"), "--json")
abort("failed to build trigger cases") unless status.success?
matrix = JSON.parse(cases_json)
work = matrix.fetch("hosts").product(matrix.fetch("environments"), matrix.fetch("cases"))
work = work.first(options[:limit]) if options[:limit]
if options[:sample] && options[:sample] < work.length
  work = options[:sample].times.map { |index| work[(index * work.length / options[:sample].to_f).floor] }
end

results = work.map do |host, environment, kase|
  base = {host: host, environment: environment, skill: kase.fetch("skill"), type: kase.fetch("type"), case_id: kase.fetch("id")}
  unless options[:command]
    next base.merge(status: "not_run", actual: nil, error: "no evaluator command supplied")
  end
  payload = JSON.generate({host: host, environment: environment, case: kase})
  stdout, stderr, process = Open3.capture3(options[:command], stdin_data: payload)
  begin
    actual = JSON.parse(stdout).fetch("selected_skill")
    expected = kase.fetch("expected")
    base.merge(status: process.success? && actual == expected ? "passed" : "failed", actual: actual, error: stderr.empty? ? nil : stderr)
  rescue => error
    base.merge(status: "failed", actual: nil, error: "#{error.message}; stderr=#{stderr}")
  end
end

counts = %w[passed failed not_run].to_h { |key| [key, results.count { |result| result[:status] == key }] }
document = {schema_version: 1, generated_at: Time.now.utc.iso8601, summary: {total: results.length, **counts.transform_keys(&:to_sym)}, results: results}
path = File.expand_path(options[:output], root)
Dir.mkdir(File.dirname(path)) unless Dir.exist?(File.dirname(path))
File.write(path, JSON.pretty_generate(document) + "\n")
puts "actual trigger evaluation: #{counts['passed']} passed, #{counts['failed']} failed, #{counts['not_run']} not_run (#{results.length} total)"
exit 1 if counts["failed"] > 0
