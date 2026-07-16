# Stack と version policy

## 解決順序

1. runtime と capability を特定する。
2. 現行の公式 starter と公式 compatibility documentation を調べる。
3. registry metadata から stable release、publish 時刻、engine、peer dependency を取得する。
4. cooling period を通過した、最も新しい compatible stable release を選ぶ。
5. exact version を install し、lockfile を commit し、package manager の exact version を記録する。
6. 実際の typecheck、test、build、deployment dry-run を行う。metadata compatibility は証拠であって証明ではない。

日付依存の dependency table をこの skill に埋め込まない。install の事実は lockfile、判断時点の snapshot は foundation record に置く。

## Stable と cooling policy

- prerelease identifier を持つ version は、documented reason が明示承認されない限り選ばない。
- package cooling period は default 7日（`minimumReleaseAge: 10080`）で strict enforcement とする。
- 短縮または bypass は、security fix、あるいはそうしないと compatible に解決できない coordinated toolchain に限定する。
- bypass ごとに最小の package scope、理由、owner、expiry/review date、removal trigger を記録する。
- 古い cooled version を選んだ時に "latest" と呼ばず、"newest eligible stable" と表現する。
- stable な pre-1.0 package は change risk が高い dependency と扱う。exact pin し、documented stability guarantee と changelog を確認し、update 前に compatibility test を要求する。stable `0.x` は prerelease ではないが、SemVer 上は minor release に breaking change を含められる。

## TypeScript

すべての compiler API consumer を検証した後だけ、最も新しい stable TypeScript を使う。type-aware lint、code generation、API extraction、AST tooling、editor plugin、framework 固有 type tooling を確認する。最新 major に必要な API や ecosystem support がなければ、直前の supported major または公式の side-by-side setup を使う。採用を強行するために `strict` を弱めたり broad cast を加えたりしない。

module resolution は runtime に合わせる。

- bundle される browser/Worker application: 現行 tool guidance に従い、`moduleResolution: bundler` と `module: preserve` または `esnext`。
- Node direct execution: bundler が意図的に resolution を所有しない限り `nodenext`。
- global `types` を明示し、偶然入った ambient package に依存しない。

## Node and package manager

- production Node application は、単なる最新 Current release ではなく現行 supported LTS line を使う。
- `packageManager` と CI bootstrap で pnpm の exact version を pin する。
- application の dependency は exact version を優先する。公開 library は compatible peer range を使ってよいが、lockfile で exact resolved version も test する。
- `minimumReleaseAgeStrict`、`blockExoticSubdeps`、狭い lifecycle-script/build allowlist を設定する。

## Default stack と切替条件

| Capability | Default | 切り替える条件 |
|---|---|---|
| HTTP API | Hono | runtime/framework requirement と実質的に衝突する。 |
| Trust-boundary validation | Zod | 既存 contract system が runtime validation を所有している。 |
| Relational data | Drizzle | relational store がない、または platform-native access layer が明確に優れる。 |
| SPA | React + Vite | SSR/streaming/native requirement が別 architecture を要求する。 |
| Tests | Vitest | runtime 固有の公式 harness が別 runner を要求する。 |
| Lint/format | oxlint + oxfmt | 必要な file coverage/rule が不足する、または Biome が既存標準である。 |
| Dead-code analysis | Knip | package shape に適用できない。除外は狭く記録する。 |
| Hooks | Lefthook | 既存 cross-platform hook runner が contract を所有している。 |

Oxc、Biome、ESLint、Prettier を重複 owner として install しない。1つの file type は1つの formatter が所有する。lint tool が type-aware rule を持っていても type authority は `tsc` とする。

## Conditional libraries

- Tailwind: utility-first styling と token/component strategy が必要な時に選ぶ。API-only または最小の visual surface には加えない。
- TanStack Query: 非自明な remote server state、cache、mutation、retry、invalidation、route prefetch がある時に選ぶ。
- TanStack Router: typed params/search、nested layout、loader、route-level auth の便益がある multi-route SPA で選ぶ。
- OpenAPI: external/multiple client、generated SDK、documentation、contract test がある時に選ぶ。対応していれば runtime schema から生成し、duplicate schema を保守しない。
- Turborepo: workspace があるだけでなく、意味のある multi-package task graph、cache、parallel execution がある時に選ぶ。

## 参照する一次 source

- Node releases: https://nodejs.org/en/about/previous-releases
- TypeScript releases: https://devblogs.microsoft.com/typescript/
- pnpm settings: https://pnpm.io/settings
- Vite releases: https://vite.dev/releases
- React versions: https://react.dev/versions
- Vitest: https://vitest.dev/
- Hono: https://hono.dev/
- Zod: https://zod.dev/
- Drizzle: https://orm.drizzle.team/
- Oxc: https://oxc.rs/
- Biome: https://biomejs.dev/
- Knip: https://knip.dev/
