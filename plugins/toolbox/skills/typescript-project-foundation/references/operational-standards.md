# Runtime に依らない運用の標準

deploy して動かし続ける service に適用する。どれも後から足すと、全 call site の書き換えか data の欠落を伴う。各項目は「既定」「例外にしてよい条件」「強制する手段」をセットで決め、強制する手段が無いものを完成として扱わない。stakes ごとに後回しにできる範囲は [Decision catalog](decision-catalog.md) の表に従う。

## 標準

| 項目 | 既定 | 例外にしてよい条件 | 強制する手段 |
|---|---|---|---|
| 構造化 log | 1 event を1つの JSON object で出す。field は時刻、severity、service、environment、release、request ID、operation、outcome、所要時間、秘匿済みの error（種類と code）。出力は logger module だけが行う | 人が読む CLI の出力 | logger module 以外での `console.*` を lint で禁止する。秘匿の test を持つ |
| Request ID と trace context | 受け取った W3C `traceparent` を引き継ぎ、無ければ生成する。すべての log、外向きの request、非同期の message に伝える | 外部と通信しない library | 入口の middleware と共有 client で付与する。伝播を test で確かめる |
| 外向きの通信 | すべてに timeout を設定する。retry は冪等な操作だけに行い、回数の上限と jitter 付きの backoff を持たせる | streaming は全体の timeout の代わりに idle timeout を使う | 共有 client を経由させ、生の `fetch` の直接使用を lint で制限する |
| 設定 | 環境変数を型付きの schema で起動時に検証し、不足や不正があれば起動を失敗させる。値を含まない example file を commit する。secret は platform の secret store に置く | なし | 起動の test を持つ。config module 以外からの環境変数の直接参照を lint で禁止する |
| 環境の分離 | local・preview（または staging）・production を明示し、credential と data を環境ごとに分ける | internal-tool と demo は Decision catalog の表に従う | 環境ごとの設定を versioned config に置く。pull request の CI から production の credential を使えないようにする |
| Health と停止 | 長時間動く process は、生存確認と受付可否の確認を分ける。停止の signal を受けたら新規の受付を止め、処理中の仕事を終えてから終了する | request ごとに起動する serverless・edge の runtime | 起動と停止の integration test を持つ |
| 入口の上限 | request body、page size、upload の上限を決める。公開 endpoint と認証 endpoint には rate limit を掛ける。platform や edge の機能を優先する | 内部専用の endpoint は size の上限だけでよい | 上限を超えた request が拒否されることを test で確かめる |
| 監査記録 | 次の操作を追記専用で記録する：権限や role の変更、管理者の操作、他人の data へのアクセス、金銭や契約に関わる変更、data の削除と export。記録する内容は actor、対象、操作、時刻、結果、request ID。通常の log とは別に持つ | 該当する操作が無い | 該当する操作が監査記録を書くことを test で確かめる。記録の更新と削除を権限で禁じる |
| 復旧の目標 | production に入る前に、失ってよい data の量（RPO）と復旧までの時間（RTO）を決める。backup からの restore を一度実際に行う | 再生成できる data しか持たない | restore を行った記録を foundation record に残す |

## 条件付きで採用するもの

次は全 project の既定にしない。条件に当たる時だけ、初期に決める。

| 項目 | 採用する条件 | 既定の形 |
|---|---|---|
| Outbox | database の更新と外部への副作用（message の送信、他 service の呼び出し）を両方成立させる必要がある | 副作用の intent を同じ transaction で記録し、別の処理が送信して完了を記録する。受け手は重複を許容する |
| Webhook の受信 | 外部 service から webhook を受ける | 署名を raw body に対して検証する。timestamp の許容幅と event ID の重複排除で replay を防ぐ。検証前に内容を処理しない |
| File の upload | 利用者が file を upload する | application を経由させず、object storage へ直接 upload させる（期限付きの URL）。size と種類の上限を決め、申告された content type を信用しない。利用者の file は application と別の origin から配信する |

## 見送る既定

- **Feature flag と kill switch の仕組み**: 既定では入れない。段階的な公開が要件になった時、または外部依存の障害時に機能を切る必要が出た時に足す。それまでは deploy の rollback で足りる。足す時は、flag の owner と削除の期限を決める。
- **外部の observability service**: 既定では platform 標準の log と metric から始める。alert の受け手と対応の手順が決まった時に足す。tracing の backend は後から選べるが、trace context の伝播だけは最初から行う。

## 参照する一次 source

- W3C Trace Context: https://www.w3.org/TR/trace-context/
- OpenTelemetry: https://opentelemetry.io/docs/
