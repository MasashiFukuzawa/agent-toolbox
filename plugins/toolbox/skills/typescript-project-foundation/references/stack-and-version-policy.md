# Stack と version policy

## 最新 version の原則

新規 project には、作業当日に解決した最新の stable version を入れる。version、compatibility date、設定の schema を、記憶や過去の project から転記しない。同梱の resolver と公式 source で当日に解決し、解決した version と取得日を foundation record に残す。

ここでの「最新」は、cooling period を通過した最も新しい compatible stable release を指す（下の policy）。cooling period のために1つ前の release を選んだ場合は、その事実と、最新の release へ上げる時期を記録する。

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

## Default stack

この表が default の正本である。`SKILL.md` と resolver の profile はこの表に従う。

| Capability | Default | なぜ既定か | 切り替える条件 | 既定を見直す時 |
|---|---|---|---|---|
| Package manager | pnpm | cooling period、lifecycle script の allowlist、exotic な取得元の遮断を設定で強制できる | 既存の標準が別の manager で、同等の supply-chain 設定を強制できる | 必要な設定が廃止・改名された |
| HTTP API | Hono | Web 標準の Request・Response に依存し、Workers と Node で同じ route が動く。runtime を替えても書き直しが少ない | runtime や framework の要件と実質的に衝突する | 対象 runtime の公式 adapter が保守されなくなった |
| Trust-boundary validation | Zod | 1つの schema から runtime の検証と TypeScript の型の両方を得られる | 既存の contract の仕組みが runtime の検証を所有している | 計測した bundle size や検証の速度が要件を満たさない |
| Relational data | Drizzle | SQL に近い型付きの query と versioned な migration を持ち、edge の runtime でも動く | relational な保存先が無い、または platform 固有の access 層が明確に優れる | 対象の database・driver への公式対応が切れた |
| SPA | React + Vite | 公式 starter と platform の plugin が揃い、client-rendered な SPA に server の前提を持ち込まない | SSR・streaming・native の要件が別の architecture を求める | 採用する platform の公式 starter が別の構成へ移った |
| Tests | Vitest | Vite と設定を共有し、ESM と TypeScript をそのまま実行でき、runtime 固有の pool がある | runtime 固有の公式 harness が別の runner を求める | 対象 runtime の公式 harness が別の runner へ移った |
| Lint/format | oxlint + oxfmt | 実行が速く、hook と CI で毎回全体に掛けられる。lint と format の所有者を1つの toolchain にできる | 必要な file の種類や rule が不足する、または Biome が既存の標準である | project が必要とする rule を提供できない状態が続く |
| Dead-code analysis | Knip | 使われていない export・file・依存を1つの tool で検出できる | package の形に適用できない。除外は狭く記録する | 採用する framework の entry を解釈できない |
| Hooks | Lefthook | 単体の binary で動き、並列実行と staged な file の絞り込みを持つ | 既存の cross-platform な hook runner が contract を所有している | 必要な platform で動かなくなった |

### 既定そのものの見直し

version だけでなく、default の選択も作業のたびに確かめる。新規 project を作る時に、各 default について次を公式 documentation と release notes で確認する。

1. 保守が続いているか（直近の release、deprecated の表示）。
2. 対象の runtime を公式に support しているか。
3. 表の「切り替える条件」「既定を見直す時」に当たっていないか。

当たっていれば、表ではなく当日の証拠に従って選び、判断と根拠を foundation record に残す。同じ理由が続くなら、この表の更新を提案する。

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
