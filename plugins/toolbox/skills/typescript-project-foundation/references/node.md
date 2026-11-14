# Node profile

production の service には、現行の supported な Node LTS を使う。最新の Current line は、明示的に短命な実験か、確認済みの機能要件がある時だけ選ぶ。

## Node API・service

- strict ESM。`module` と `moduleResolution` は、Node の直接実行か、選んだ bundler に合わせる
- Hono の Web Standards の model が service に合う時は、現行の公式 Node adapter を使う
- HTTP、設定、queue、file、外部 service の境界に Zod
- relational database には Drizzle
- timeout、同時実行数の上限、health、graceful shutdown、構造化 log は [運用の標準](operational-standards.md) に従う
- container か serverless かの deploy の contract を明示して選ぶ

Node の process が、定期実行、local の file、WebSocket、background task、memory 上の調停を持つなら、stateless だと仮定しない。実装の前に、process の寿命と停止の意味を決める。

## Batch・worker

- 入力の単位ごとに冪等にし、途中から再開できる checkpoint を持つ
- 同時実行数と1件あたりの timeout に上限を置く
- 1件の失敗で全体を止めず、失敗した入力を退避して後から再処理できるようにする
- schedule による重複実行を防ぐ
- 実行ごとの ID と、成功・失敗・skip の件数を記録する

## Database の選択

- PostgreSQL：native の UUID を使う。supported な server の version が native の UUIDv7 生成を持つならそれを使い、無ければ application の共有 generator を使う。
- SQLite：正確な `INTEGER PRIMARY KEY`、UUID の text・binary、JavaScript の int64 の規則に従う。
- deploy の構成に合った connection pool、transaction、migration、retry の方針を足す。transaction の境界は [Data and API foundation](data-and-api-foundation.md) に従う。
- PostgreSQL の row-level security は多層防御になるが、scope 付きの application の repository と negative test の代わりにはならない。

## Deployment

- 選んだ runtime manager か container の base の方針で、Node の LTS を pin する。
- CI で、clean な install、typecheck、test、build、migration の検証、package と container の security 走査を実行する。
- OIDC と不変の artifact を優先する。artifact を公開する場合や外部の保証要件がある場合は、SBOM と provenance の要件を記録する。
- deploy は [Quality and delivery](quality-and-delivery.md) の安全手順に従う。
