---
name: typescript-project-foundation
description: >-
  新規 TypeScript project の runtime・package 境界、stack、API/data contract、security、testing、CI/CD を設計・scaffold・検証する。greenfield repository の新設、初期 architecture 決定、foundation plan のレビュー時に使う。既存 project の機能実装・migration・production UI design・単独 API 調査には使わず、該当する実装・migration・frontend・technical-research skill を使う。
---

# TypeScript Project Foundation

後から高くつく re-platforming を避ける「最小の完全形」を作る。初期 file 数の少なさを最適化しない。長く残る境界は早期に決め、feature mechanism は要件が正当化した時だけ加える。

## Guardrails

1. 指定がなければ **production-intent** と扱う。`disposable-spike` は、利用者が廃棄期限と終了条件を明示した時だけ選ぶ。
2. 実行時点の公式 starter・公式 documentation・registry metadata を調査する。version や compatibility date を記憶から転記しない。
3. cooling policy を満たす最新の compatible stable release を選ぶ。RC・beta・canary・nightly は明示承認なしに選ばない。
4. file 作成、package install、repository 変更の前に read-only plan を示す。列挙した local 変更は一度の承認でよいが、deployment、remote database、secret、外部 account の変更は常に別途確認する。
5. 生成する再利用可能な guidance に、固有の organization 名、private repository 情報、domain、ID、path、運用 data を混入させない。
6. 判断を対象 repository に永続化する。chat 内だけの plan では判断の再現性を担保できない。
7. 強制可能な invariant は type、schema、lint、test、script、CI のいずれかで実行可能にする。prose-only policy を完成扱いしない。

## Workflow

### 1. Capability と stakes を分類する

preset を選ぶ前に次を確定する。

```text
stakes: production-intent | disposable-spike
runtime: cloudflare-workers | node | browser | library | cli
capabilities: http-api? web-ui? relational-data? async-processing?
              durable-coordination? publish-package? multiple-deployables?
tenancy: none | single-tenant | shared-schema | database-per-tenant
user-to-tenant: not-applicable | 1:1 | N:M
```

production-intent product で tenancy または cardinality が不明なら、黙って先送りしない。判断を求めるか、より拡張可能な N:M model を仮採用して assumption を記録する。

preset は出発点としてだけ使う。

- Cloudflare full-stack / Worker API: [Cloudflare profile](references/cloudflare.md) を読む。
- Node API / service: [Node profile](references/node.md) を読む。
- React SPA: [Web profile](references/web.md) を読む。
- 公開 library / CLI: [Library and CLI profile](references/library-and-cli.md) を読む。

### 2. 現行 toolchain を解決する

[Stack and version policy](references/stack-and-version-policy.md) を読む。該当する公式 starter から始め、registry を照会して peer/runtime compatibility を検証する。

同梱 resolver は advisory かつ read-only である。この `SKILL.md` からの相対位置で path を解決し、作者の repository layout を仮定しない。

```sh
python3 <skill-dir>/scripts/resolve_versions.py --profile cloudflare-fullstack --format markdown
```

script が示すのは registry 上の事実だけである。特に TypeScript compiler API consumer と Cloudflare の coordinated toolchain は、公式 compatibility documentation も検証する。

### 3. 後付けコストの高い境界を決める

すべての production-intent project で [Decision catalog](references/decision-catalog.md) を読む。次は該当時だけ読む。

- HTTP API / relational data: [Data and API foundation](references/data-and-api-foundation.md)
- production-intent / authentication: [Security and supply chain](references/security-and-supply-chain.md)
- 保守または deploy する repository: [Quality and delivery](references/quality-and-delivery.md)

後からの変更コストを一貫して分類する。

```text
trivial | config-change | code-migration | data-migration | api-break | re-platform
```

### 4. Foundation plan を提示する

chat 出力は簡潔にし、次を含める。

1. assumption と未解決の判断
2. 選択した capability/profile と理由
3. decision table: 判断、選択、根拠、後からの変更コスト
4. package/deployment diagram
5. 取得日と source を伴う version/compatibility snapshot
6. security、identity、authorization、data boundary
7. 予定する file 変更と install 時の supply-chain effect
8. verification と acceptance criteria
9. defer する mechanism と具体的な再検討 trigger

日付を守るために acceptance criteria を落とさない。scope 変更が必要なら、勝手に縮小せず選択肢と推奨を示す。

### 5. 承認後に scaffold する

複製した static template より、公式 starter と deterministic な変換を優先する。default は次の通り。

- exact `packageManager` version と commit 済み lockfile を持つ pnpm
- strict ESM TypeScript。type の source of truth は `tsc`
- Vitest、Knip、Lefthook
- default は Oxc（`oxlint` + `oxfmt`）。documented switch condition を満たす時だけ Biome に替え、併用しない
- HTTP API は Hono、trust boundary は Zod、relational storage は Drizzle
- SPA は React + Vite

Tailwind、TanStack Query、TanStack Router、OpenAPI、Turborepo、queue、durable state、external observability は conditional とする。要件が未確定でも、identity、authorization、data、time、money、migration、deployment boundary を先送りする理由にはならない。

### 6. 検証して永続化する

同梱の generic invariant checker を実行し、その後に対象固有の type、lint、test、build、architecture、migration、deployment dry-run を行う。

```sh
python3 <skill-dir>/scripts/check_invariants.py --root <target-repository>
```

選択した foundation は対象 repository 既存の architecture document 規約に保存する。規約がなければ `docs/architecture/foundation.md` を作る。主要な議論対象は ADR、package fact は `package.json`/lockfile、強制可能な rule は code/CI に記録する。

skip または失敗した verification をすべて報告する。合意した acceptance criteria がすべて通るまで foundation を ready と報告しない。
