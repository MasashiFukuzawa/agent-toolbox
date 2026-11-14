# Cloudflare profile

edge への deploy、低い運用負荷、世界規模の request 処理、Cloudflare の binding が product に合う時に Workers を選ぶ。長時間の CPU 処理、制限の無い Node・native の依存、任意の長寿命 connection、非対応の protocol が必要な product や、すぐに re-platform を強いられる制限に当たる product に、黙って選ばない。

現行の制限と互換性は、実行時に公式 documentation で確認する。platform の数値の上限や、記憶している `compatibility_date` を新しい repository に写さない。

## Preset

### Worker API

- Hono と Zod
- Drizzle は、relational な D1・PostgreSQL の data がある時だけ
- Wrangler が生成する binding の型
- 現行の公式 Cloudflare Workers pool・harness を使う Vitest
- [運用の標準](operational-standards.md) に従う構造化 log と request ID

### Full-stack SPA + Worker

Vite と Workers Assets が SPA と API を1単位として build・deploy できる時は、現行の公式 Cloudflare Vite plugin と単一 package を優先する。UI と API を独立に deploy する、実在する package の境界を共有する、runtime や型の環境が違う、のいずれかに当たる時は workspace にする。

React と Vite を足す。TanStack Router・Query と Tailwind は、一般の判断規則に当たる時だけ足す。

## 設定と binding

- `wrangler.jsonc`（または現行の公式の同等物）を正本にし、dashboard との drift を避ける。
- compatibility date は、現行の runtime の挙動と flag を確認した上で、作成日の日付にする。
- binding の型を Wrangler で生成し、生成物に差分が出たら CI を失敗させる。
- local・preview（staging）・production を明示して定義する。
- secret は Cloudflare の secret storage に置く。平文の `vars` や commit した `.dev.vars` に置かない。
- production 以外の環境には、別の資源か、明確に分離した識別子を使う。

## D1

- data の reference にある、SQLite の識別子と integer の規則を適用する。
- UUIDv7 は application 側で生成する。
- 最初から versioned な migration を持ち、local と runtime に忠実な環境で test する。
- tenant の filter、foreign key、検索する field、cursor の並び順に index を張り、重要な経路の query plan を確認する。
- migration と deploy の順序、expand/contract の互換性を決める。
- D1 の transaction は、原子的に実行される batch を前提に設計する。現行の仕様を公式 documentation で確認する。
- 現行の D1 documentation と test が対応を証明しない限り、JavaScript の `BigInt` を bind しない。int64 の境界を明示的に保つ。

## Queues と Durable Objects

- Queue の配信は retry され、重複しうる。有効にする前に、冪等性、retry の分類、試行回数の上限、dead-letter と復旧の振る舞いを決める。
- Durable Objects は、単一の調停点、強い順序の更新、alarm、connection の所有が必要な状態にだけ使う。一般的な CRUD のために足さない。
- D1・Queues・Vectorize など複数 service の整合性は、source of truth を1つ決め、派生する index を source より先に壊さない順序で更新する。外部への副作用は intent を先に記録する。

## Observability と delivery

- log の項目と秘匿は [運用の標準](operational-standards.md) に従う。
- Workers Logs と trace は、環境ごとの sampling、保持期間、費用を決めた上で有効にする。
- runtime に忠実な test と、deploy の dry-run を CI で実行する。
- deploy は [Quality and delivery](quality-and-delivery.md) の安全手順に従う。deploy、remote の D1 の変更、secret の書き込みは、明示的な確認の後に行う。

Primary sources:

- https://developers.cloudflare.com/workers/best-practices/workers-best-practices/
- https://developers.cloudflare.com/workers/get-started/guide/
- https://developers.cloudflare.com/workers/testing/vitest-integration/
- https://developers.cloudflare.com/workers/observability/logs/workers-logs/
- https://developers.cloudflare.com/d1/
- https://hono.dev/docs/getting-started/cloudflare-workers
- https://orm.drizzle.team/docs/sqlite/connect-cloudflare-d1
