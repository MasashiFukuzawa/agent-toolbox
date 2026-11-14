# Day-zero decision catalog

後から横断的な作り直しになる判断を、最初に決めるための一覧。その項目が生き残る見込みと変更コストの積が大きいものを、今決める。各項目は「既定」「例外にしてよい条件」「強制する手段」をセットで扱う。

## Stakes と後回しにできる管理策

指定がなければ production-intent とする。他の区分は、利用者と公開範囲（internal-tool・demo）、または廃棄期限と終了条件（disposable-spike）が明示された時だけ選ぶ。表に無い省略はしない。

| 管理策 | production-intent | internal-tool | demo | disposable-spike |
|---|---|---|---|---|
| 入力の検証、secret の扱い、依存の pin と lockfile | 必須 | 必須 | 必須 | 必須 |
| 認証・認可・tenant の境界 | 必須 | 必須（組織の identity provider に任せてよい） | 実 data か外部公開があれば必須 | 実 data を入れない前提で省略可 |
| Data の意味（ID・時刻・金額・削除） | 必須 | 必須 | 残す data があれば必須 | 省略可 |
| Format・lint・typecheck・test・hook・CI | 必須 | 必須 | 必須（test は主要な流れに絞ってよい） | format・lint・typecheck まで |
| Agent 向けの指示と統一 command | 必須 | 必須 | 必須 | 任意 |
| Preview・staging 環境 | 操作できる UI・API があれば必須 | 後回し可 | 後回し可 | 不要 |
| Deploy の自動化・smoke・rollback | 必須 | 手動の deploy でよい。rollback の手順は必須 | 手動でよい | 不要 |
| 監視・alert・復旧の目標 | 必須 | log と error の通知まで | 後回し可 | 不要 |
| 監査記録 | 該当する操作があれば必須 | 該当する操作があれば必須 | 後回し可 | 不要 |
| Rate limit と request size の上限 | 必須 | size の上限まで | 外部公開するなら必須 | 不要 |

- 後回しにした管理策は、foundation record に昇格の trigger とともに書く。
- internal-tool や demo が、想定外の利用者・実 data・外部公開を得たら、production-intent として計画し直す。
- disposable-spike でも、production 用と誤認されうる曖昧な data contract や security contract を作らない。

## Runtime と repository の形

| 判断 | 既定 | 変更コストと規則 |
|---|---|---|
| Runtime | local の都合ではなく、実際の deploy 先に合わせる | re-platform。runtime の制限と使えない API を確認する |
| Module の形式 | strict ESM | code-migration。公開に必要な時以外、ESM と CJS の両対応にしない |
| 単一 package か workspace か | 実在する境界ができるまで単一 package | code-migration。deploy 単位が2つ以上、公開 package がある、runtime が混在する時に workspace にする |
| Task runner | 単純な単一 package では入れない | config-change。package をまたぐ task graph と cache の便益がある時だけ Turborepo を足す |
| 設定 | versioned config を正本にし、secret は外に置く | re-platform と security。local・preview・staging・production を明示して分ける |

## 形ごとの追加の判断

| 形 | 最初に決めること |
|---|---|
| MCP server | transport と認証の方式（仕様と SDK は作業時に公式で確認する）。tool の入力を schema で検証する。tool の名前と schema は公開 contract として扱う。副作用のある tool は冪等にするか、実行前の確認を要求する。呼び出し元の principal で認可し、tool の出力に secret や他 tenant の data を含めない |
| Batch・worker | 入力の単位ごとの冪等性。checkpoint と再開。同時実行数の上限と timeout。1件の失敗で全体を止めない隔離と、失敗した入力の退避先。schedule の重複実行の防止。実行ごとの ID と、部分的な成功の報告 |

## Product と identity の model

schema や route を設計する前に決める。

- product は single-tenant か、shared-schema の multi-tenant か、tenant ごとの database か。
- 1人の利用者が複数の tenant に属せるか。1つの identity が複数の account に対応しうるか。
- どの識別子が内部の user identity で、どれが provider が所有する不透明な subject か。
- HTTP handler・job・script・test のそれぞれで、認可をどこで強制するか。

shared-schema の multi-tenant では、tenant が所有するすべての行に明示的な tenant key を持たせ、すべての access 経路で scope を機械的に強制する。HTTP middleware だけでは認可の境界にならない。

## Data の意味

| 項目 | 決めること |
|---|---|
| 識別子 | すべての ID を分類する：UUIDv7 の entity、内部の integer、複合の関係、外部の principal、natural key、digest、capability |
| UUID の保存 | database の profile ごとに、text か binary かを一度決める。混在させない |
| 時刻 | UUIDv7 とは別に明示的な timestamp を持つ。保存は UTC、業務上の timezone、精度、event の時刻と処理の時刻の区別を決める |
| 金額 | integer の最小単位か、正確な decimal を使う。binary の浮動小数点を使わない。通貨を金額と一緒に持つ |
| 行の来歴 | 作成時刻・更新時刻と、作成者・更新者を最初から持つ。後からは埋め戻せない |
| 同時更新 | 複数の主体が更新しうる行には version の列を持つ。API での強制は同時編集がある時に行う |
| 削除 | 既定は物理削除と監査記録。復元の要件がある時だけ論理削除にし、その場合は query での強制を伴わせる。個人 data の保持期間と消去の方法を決める |
| Migration | versioned な migration と、新旧の code が重なる時の expand/contract を使う。production の前に rollback と復旧を決める |
| 冪等性 | mutation・webhook・queue・定期実行の、retry と重複配信の扱いを決める |
| Data の所在 | 保存先を選ぶ前に、地域と法域の要件を確認する |

詳細は [Data and API foundation](data-and-api-foundation.md) を読む。

## API と client の contract

- error の表現と、安全に開示できる範囲
- 認証の運び方：secure cookie、bearer token、service の credential、または意図した組み合わせ
- domain・cookie・CORS・CSRF の構成
- pagination：変化する順序付きの collection は cursor を既定にする。安定した sort key、tie-breaker、page size の上限を持つ
- API の版と廃止の方針
- request ID と idempotency key
- payload の慣習：日時の形式、null と欠落の区別
- 外部向けと内部向けの contract の区別
- UI がある場合の i18n、accessibility、文言の所有者

## Delivery と運用

- preview・staging・production の構成
- migration と deploy の順序
- smoke、rollback の対象、同時実行の方針
- log の秘匿と保持期間
- observability の sampling と費用の上限
- backup・export・復旧の目標
- 依存と security の更新の owner
- branch の保護と必須の check

詳細は [Quality and delivery](quality-and-delivery.md) と [運用の標準](operational-standards.md) を読む。

## 判断の記録

重要な選択は次の形で記録する。

```text
Decision:
Chosen option:
Alternatives considered:
Evidence/source:
Later-change cost: trivial | config-change | code-migration | data-migration | api-break | re-platform
Enforcement mechanism:
Reconsideration trigger:
```

自明な既定ごとに ADR を作らない。全体の snapshot は foundation document に置き、ADR は争点・例外・長く残る選択に使う。ADR の扱いは [Agent-ready repository](agent-ready-repository.md) に従う。
