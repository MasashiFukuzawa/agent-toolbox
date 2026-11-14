# Data and API foundation

## API の境界

信頼できない入力は境界で一度だけ検証し、型の付いた値を内側へ渡す。runtime の検証と TypeScript の型は同じ Zod schema から得る。同じ contract に対して手書きの interface を別に定義しない。

HTTP の error には RFC 9457 の Problem Details を使う。

```json
{
  "type": "https://example.invalid/problems/validation",
  "title": "Validation failed",
  "status": 400,
  "detail": "One or more fields are invalid.",
  "instance": "/requests/request-id"
}
```

- `application/problem+json` で返す。
- `type` は安定した、機械が読める値にする。
- stack trace、SQL、provider の error、secret、内部の構成を出さない。
- 拡張 member は、構造化した検証 error や request ID のように、client が安定して必要とするものだけにする。
- domain の error は一か所で変換する。route ごとに違う形の response を組み立てない。

Reference: https://www.rfc-editor.org/rfc/rfc9457.html

## Payload の慣習

API の公開後に変えると api-break になるので、最初に決めて共有 schema で強制する。

| 項目 | 既定 | 強制する手段 |
|---|---|---|
| 日時 | RFC 3339 の文字列。offset を必ず付け、既定は UTC | 共有の timestamp schema。API の日時 field はすべてこれを使う |
| 金額 | 最小単位の integer と通貨 code の組。JSON の number で小数の金額を運ばない | 共有の money schema |
| ID | 文字列。JavaScript の number で int64 を運ばない | 共有の ID schema |
| null と欠落 | 「値が無い」は null、「送っていない」は field の欠落、と意味を分ける。部分更新では欠落を「変更しない」と解釈する | schema で optional と nullable を区別する。`exactOptionalPropertyTypes` を有効にする |
| 一覧 | cursor による pagination。安定した sort key と一意な tie-breaker を cursor に含め、page size に上限を設ける | 共有の pagination schema と、上限を超えた要求の test |

## API の版と廃止

- 既定は、後方互換を保つ追加だけを行い、破壊的な変更は新しい版として並行して提供する。版の表し方（path か header か）は最初に1つ決める。
- 廃止する時は、告知・並行提供の期間・終了日を決め、廃止予定の endpoint が呼ばれていることを log で確かめられるようにする。
- 例外：同じ repository で同時に deploy される、単一の client だけが使う内部 API は、版を持たなくてよい。その場合も、新旧の code が重なる deploy では expand/contract に従う。
- 強制する手段：公開する contract（OpenAPI か共有 schema）の差分を CI で検査し、破壊的な変更を検出する。

## OpenAPI の判断

外部または複数の client、生成する SDK、公開・社内向けの documentation、contract test のいずれかがある時に OpenAPI を生成する。runtime の schema と route の定義からの生成を優先する。選んだ generator が実際に対応している OpenAPI の版を確認し、古い方言を出力する tool で最新の仕様への対応を謳わない。

同じ場所にある TypeScript の client が1つだけの小さな private API なら、Hono RPC か共有の Zod contract で足りる。後から OpenAPI を足す trigger を記録する。

## 識別子の分類

すべての主たる識別子を分類する。

| 意味 | 既定 |
|---|---|
| 永続する domain の entity | UUIDv7 |
| 関係・join | 意味のある複合 primary key |
| SQLite 内部の行・join の key | `INTEGER PRIMARY KEY` |
| 外部の identity の principal | provider が所有する不透明な文字列 |
| 内容の同一性 | SHA-256 など適切な digest |
| capability・session・reset の token | CSPRNG による乱数。保存時は hash にする |
| 人が読む局所的な連番 | 別の明示的な sequence |

UUIDv7 は時刻順に並ぶが、業務上の時刻・監査の時刻・因果の順序・欠番の無い連番のいずれでもない。`created_at` を別に持ち、`created_at, id` で並べる。UUIDv7 は生成時刻のおおよそを明かすので、それが許されない場所では使わない。

生成と schema を一か所に集める。

```ts
newEntityId()        // UUIDv7
newCapabilityToken() // CSPRNG、別の contract
```

domain の取り違えが起こりうる所では branded な識別子を使う。fixture には `entity-1` のような仮の値ではなく、contract を満たす値を使う。

Reference: https://www.rfc-editor.org/rfc/rfc9562.html

## Transaction の境界

- 既定：transaction は、1つの業務操作を表す data access 層の関数の中で開始し、その中で終える。route handler や UI に近い層で開始しない。
- transaction の中で外部への通信を行わない。database の更新と外部への副作用の両方が必要なら、[運用の標準](operational-standards.md) の outbox に従う。
- 1つの transaction で読み書きする範囲に、認可の scope（actor と tenant）を必ず含める。
- runtime ごとの差を確認する。複数の statement を対話的に実行する transaction を持たない database では、その platform の原子的な batch の仕組みを使い、途中で application の判断を挟まない設計にする。
- 強制する手段：transaction を開始できる API を data access 層だけに公開し、他の層からの import を lint で禁止する。途中の失敗で全体が戻ることを integration test で確かめる。

## 行の来歴と同時更新

- すべての table に `created_at` と `updated_at` を持たせる。利用者や job が更新する行には、作成者と更新者（principal の ID）も持たせる。
- 複数の主体が更新しうる行には、更新のたびに増える `version` の列を持たせる。同時編集が実際に起こる resource では、API で条件付きの更新（`If-Match` など）を要求し、version が合わない更新を拒否する。
- 例外：追記しかしない table（event、監査記録）は `updated_at` と `version` を持たなくてよい。
- 強制する手段：共有の column 定義を使い、data access 層の更新関数が `updated_at` と `version` を必ず更新する。古い version での更新が拒否されることを test で確かめる。

## 削除と保持

- 既定は物理削除と監査記録にする。論理削除は、復元の要件がある時だけ選ぶ。`deleted_at` を足す場合は、data access 層のすべての query が既定で除外するよう強制し、一意制約への影響を先に決める。
- 個人 data を持つ列を schema の時点で分類し、保持期間と消去の方法（削除か匿名化か）を決める。backup と log に残る分の扱いも決める。
- 強制する手段：削除した行が既定の query から見えないこと、消去の処理が分類済みの列をすべて対象にすることを test で確かめる。

## 冪等性と retry

- 資源を作る、または外部への副作用を起こす mutation の endpoint は、client が指定する idempotency key を受け付ける。同じ key の再送には、最初の結果を返す。key の保持期間を決める。
- at-least-once で配信される queue・webhook・定期実行の consumer は、message や event の ID で重複を排除するか、何度実行しても同じ状態に収束する処理にする。
- 例外：読み取りだけの endpoint と、自然に冪等な更新（同じ値への置き換え）は key を要しない。
- 強制する手段：同じ key や同じ message を2回処理しても結果が1回分であることを test で確かめる。

## SQLite と D1

- SQLite の ROWID の別名になるのは、宣言が正確に `INTEGER PRIMARY KEY` の時だけである。
- `INT PRIMARY KEY` と `BIGINT PRIMARY KEY` は同じ挙動にならない。
- commit 済みの ID を再利用してはならない場合を除き、`AUTOINCREMENT` を付けない。欠番の無い連番にはならず、overhead が増える。
- 内部の符号付き64bit integer は、できるだけ database の中に留める。JavaScript の `number` はすべての int64 を安全に表せないので、外には UUID の文字列か、明示的な string・BigInt の contract を出す。
- UUIDv7 は、複雑な SQLite の trigger や default ではなく、application の共有 module で生成する。
- foreign key、tenant の scope、filter、並び順のうち、query plan で必要と分かったものに index を張る。
- migration は、remote に適用する前に、現実的な database の copy か使い捨ての環境で test する。

References:

- https://sqlite.org/rowidtable.html
- https://sqlite.org/autoinc.html
- https://developers.cloudflare.com/d1/best-practices/use-indexes/

## 認可を前提にした query の設計

制限の無い生の database client を、route・job・feature の code に公開しない。actor と tenant の scope を必須にした、狭い repository または session の境界を提供する。同じ境界を、HTTP handler・queue・定期実行・script・test のすべてに強制する。

- PostgreSQL では、多層防御として row-level security を足してよい。
- SQLite と D1 には、application から独立した同等の仕組みが無い。shared-schema の multi-tenant では、scope 付きの query API と、tenant をまたぐ access の negative test が必須になる。
- 省略可能な tenant の引数や、feature ごとに手書きした `WHERE tenant_id = ?` を避ける。
- 認証だけでなく、object 単位と property 単位の認可を test する。

## 時刻と金額

- UTC の timestamp を、文書化した1つの物理表現と精度で保存する。変換は、表示と業務規則の境界だけで行う。現在時刻は、直接取得せず注入できる clock から得る。
- 金額は integer の最小単位か正確な decimal で持ち、必ず通貨を伴わせる。
- 強制する手段：共有の timestamp と money の schema・型を使い、clock module 以外での現在時刻の直接取得と、金額への浮動小数点の演算を lint か architecture check で禁止する。
- 新旧2つの application が重なりうる時は expand/contract の migration を使う。migration が構文上は戻せても、data の rollback が安全だという証明にはならない。
