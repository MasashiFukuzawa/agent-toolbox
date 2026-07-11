---
name: cloudflare-data-pipeline
description: >-
  D1、Vectorize、Queues、Workers をまたぐデータパイプラインの整合性と失敗処理を設計・レビューする。複数サービスの結合部に使う。単一 API の使い方には使わない。「Queue再処理」「D1とVectorizeの不整合」を正のトリガーとし、単一Workerのdeploy安全性には cloudflare-worker-cd を使う。
---
# Cloudflare Data Pipeline — 結合部の設計・レビューガードレール

D1 / Vectorize / Queues / Workers は単体では扱いやすいが、これらをまたいだ
「大きい入力の再処理・部分失敗・再配信・整合性回復」は明示的に設計しないと破綻する。
本スキルはその結合部に特化した設計原則とチェックリストを提供する。

## ガードレール

1. **DLQ を purge しない**。DLQ は障害解析の一次証拠。自然 expiry も purge も「証拠喪失」であり解決ではない
2. **redrive は production mutation として扱う**。preflight / canary（3〜5件）/ stop condition なしの一括 redrive を提案しない
3. **raw error message を本番ログに出す設計を提案しない**。allow-listed failure bucket への分類が基本
4. 障害対応でこのスキルを使う場合も read-only 診断を先行させ、書き込みを伴う修復は影響範囲を提示してから行う

## 核となる役割分担（これに反する設計はレビューで指摘する）

```text
D1        = source of truth + recovery ledger
            （document version / chunk rows / cleanup intent / job state）
Vectorize = D1 の派生 index（検索専用。状態管理に使わない）
Queues    = 処理トリガー（at-least-once。状態を message に持たせない）
```

導かれる不変条件:

- **派生物（Vectorize）を source of truth（D1）より先に壊さない**。
  安全な順序: 新 vector upsert → D1 replace → 古い vector を cleanup。
  同一 vector ID を上書きできるなら「先に消す」より「上書き」
- **外部副作用（Vectorize delete / R2 操作等）は intent を先に D1 に記録**し、
  成功したら消す。失敗しても intent が残るので再試行できる
- **Queue consumer は at-least-once 前提で収束的（idempotent）に書く**。
  同じ document/version が何度来ても、既存 vector を壊さず D1 が同じ状態に収束すること

## 設計・レビューチェックリスト

新規設計と PR レビューの両方でこのまま使う。詳細な根拠と failure mode は
[references/failure-modes.md](references/failure-modes.md) を参照。

```text
D1
□ 大量 insert は statement 数・bind 数・subrequest 数を抑えているか
  （行数より statement 数が効く。json_each(?) + INSERT...SELECT で 1 statement 化）
□ 外部副作用の intent / cleanup queue を D1 に残しているか
□ document version / job state で stale worker を弾けるか
□ partially indexed / repair needed を表現できるか

Vectorize
□ deleteByIds は必ず batch 分割しているか（100 ID 超で失敗するクラスがある）
□ upsert も bounded batch にしているか（巨大 payload の単発 request を作らない）
□ D1 更新前に live vector を消していないか
□ orphan / stale vector を後から repair できるか

Queues
□ consumer batch size は throughput ではなく failure isolation で決めているか
  （重い処理はまず batch_size=1。1 invocation = 1 unit で失敗原因を隔離）
□ redelivery されても idempotent か
□ DLQ を purge せず診断できるか（aggregate 分類 → 原因仮説 → bounded redrive）
□ redrive に canary と stop condition があるか

Workers
□ 1 invocation に大きい入力を複数詰め込んでいないか
□ API 単体の limit だけでなく invocation 全体の budget を見ているか
  （個々の呼び出しが合法でも合算で invocation が死ぬ）
□ 重い処理は job state / checkpoint を D1 に持っているか

Logging / Observability
□ raw error.message を本番ログに出していないか（機密混入経路になる）
□ allow-listed failure bucket に分類しているか
□ 機密を出さずに aggregate diagnosis できる diagnostic fields があるか
  （例: error_summary / version 一致 / chunk_count_bucket）
```

## 使い方

- **設計時**: 上のチェックリストを設計ドキュメントに対して走らせ、未充足項目を列挙する
- **レビュー時**: diff が D1 大量書き込み / Vectorize upsert・delete / Queue consumer に
  触れていたら該当セクションを適用する
- **障害対応時**: DLQ 滞留・不整合の診断手順は failure-modes.md の該当節
  （DLQ 診断・canary redrive・invocation budget）を参照する

## References

- [references/failure-modes.md](references/failure-modes.md) —
  各チェック項目の根拠となる failure mode の詳細（D1 statement 圧力 / JSON bind、
  Vectorize batch 分割と更新順序、DLQ 診断と canary redrive、invocation budget、
  failure bucket logging）
