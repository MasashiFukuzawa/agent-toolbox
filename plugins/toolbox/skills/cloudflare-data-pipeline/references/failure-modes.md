# Failure Modes — D1 + Vectorize + Queues + Workers 結合部の詳細

SKILL.md のチェックリスト各項目の根拠。典型的な構成を前提とする:

```text
入力 artifact（OCR 等）
   ↓
Queue message
   ↓
Worker consumer
   ↓
chunking → embedding 生成
   ↓
Vectorize upsert
   ↓
D1 rows replace
   ↓
stale vector cleanup
   ↓
search
```

問題は「1箇所のバグ」ではなく複数制約の重なりとして現れる:

```text
大きい入力 → 大量 chunk → 大量 embedding
   → Vectorize payload/batch 制限
   → D1 statement/bind/subrequest 圧力
   → Worker invocation budget
   → Queue retry / DLQ
   → D1 と Vectorize の部分不整合
```

## 1. D1

### 1.1 大量 insert は「行数」より「statement 数」が効く

行単位 INSERT の連打も、100行ずつの小 batch も、statement 数と bind 数が増える点では同じ。
Worker invocation 内の statement 数・subrequest 圧力そのものを下げる必要がある。

```text
悪: chunk ごとに INSERT / 小 batch INSERT の反復（多 statement / 多 bind）
良: 1 JSON payload を bind → json_each(?) で展開 → INSERT ... SELECT ... FROM json_each(?)
```

単に「batch insert にする」だけでは不十分なことがある、が要点。

### 1.2 D1 = recovery ledger（整合性の記録場所）

Vectorize は検索 index であり失敗時の状態管理には向かない。D1 は「何をやるべきだったか」を
durable に残せる。

```text
悪: Vectorize delete 実行 → 失敗 → 何を消すべきだったか失われる

良: D1 に cleanup intent（消すべき stale vector ID）を保存
    → Vectorize delete を試行
    → 成功したら intent row を削除
    → 失敗しても intent が残り再試行できる
```

この「intent 先行記録 → 副作用 → 成功時に intent 削除」パターンは Vectorize に限らず
R2 / 外部 API 副作用全般に適用する。

## 2. Vectorize

### 2.1 delete / upsert は必ず分割前提

- deleteByIds は 100 ID 超で失敗するクラスがある
- upsert も大きい入力では payload が肥大し、単発巨大 request は危険

アプリ側で「大きい入力は来ない」前提を置かず、最初から bounded batch API としてラップする:

```text
悪: deleteByIds([1000 ids]) / upsert([1000 vectors])
良: <=100 ids ずつ deleteByIds / bounded batch ずつ upsert
```

### 2.2 更新順序 — 派生 index を source of truth より先に壊さない

```text
危険な順序:
  既存 vector delete → 新 vector upsert → D1 replace
  （途中で Worker が死ぬと「D1 に chunk はあるが vector がない」不整合）

安全な順序:
  新 vector upsert → D1 replace → 古い vector を cleanup queue へ / delete
```

同一 vector ID を上書きできる場合、same-version redelivery では「先に消す」より「上書き」が安全。

## 3. Queues / DLQ

### 3.1 DLQ は「ゴミ箱」ではなく「証拠保全場所」

```text
悪: DLQ が邪魔 → purge → 見た目は clean → 原因不明のまま再発

良: DLQ を aggregate に分類
      - parseable か / current version か
      - 入力 artifact が存在するか / 処理済み row があるか / 重複か
    → 原因仮説 → bounded redrive
```

### 3.2 batch size は throughput ではなく failure isolation で決める

`max_batch_size=10` は一見普通だが、重い処理（embedding 等）では危険:

```text
batch_size=10 → 1 invocation に大きい入力が複数
             → duration / API / memory / subrequest 圧力が合算
             → 個別 message が悪いのか invocation が重いのか判別不能

batch_size=1  → 1 invocation = 1 unit
             → 失敗原因が unit 単位で隔離され DLQ 診断が容易
```

大きい payload / 外部 API / DB 書き込みを含む consumer は、まず batch_size=1 で設計し、
必要が実証されてから安全に上げる。

### 3.3 redrive は canary 方式

```text
良: baseline metrics 取得 → 3〜5件 redrive → main queue drain 確認
    → DLQ 増加なし確認 → 次 batch
悪: DLQ 全件一括 redrive → 大量再失敗 → 原因も影響範囲も不明
```

段階 redrive にすると「途中で DLQ が増え始めた」を検知して止められる。
redrive は deploy と同格の production mutation として、preflight / canary / stop condition を持つ。

## 4. Worker invocation budget

### 4.1 API 単体の limit と invocation 全体の budget を分けて考える

個々の D1 insert や Vectorize call を修正しても失敗が残る場合、
「個別の呼び出しは合法でも 1 invocation 全体では重すぎる」可能性を疑う:

```text
個々の操作は制限内 → でも入力が大きい → chunk が多い → embedding call も多い
→ D1 / Vectorize / cleanup も多い → invocation 全体が budget 超過
```

### 4.2 重い非同期処理は job state machine に寄せる

Queue message だけに状態を持たせず、D1 に job state を持つ:

```text
jobs: pending → reading_input → chunking → embedding
      → vector_upserting → d1_replacing → stale_cleanup_pending → complete
```

checkpoint があれば途中失敗からの再開・stale worker の排除・repair が可能になる。

## 5. Logging / Observability

### 5.1 raw error message を出さず bucketization する

error.message には機密が混入しうる（入力テキスト断片・storage key・document ID・
source URL・provider response・ファイル名・token・内部パス）。
sanitize（free-form を加工して出す）ではなく bucketization（allow-list 分類のみ出す）を基本にする:

```text
bucket 例:
  input_artifact_unavailable / embedding_count_mismatch / embedding_provider_empty
  vectorize_error / d1_error / worker_api_limit / rate_limited / timeout / error_unclassified
```

### 5.2 成功/失敗の2値ではなく aggregate 診断フィールドを最初から設計する

`embed_failed` だけでは診断不能。機密を含まない coarse-grained fields を最初から出す:

```text
embed_failed
  error_summary=d1_error
  document_version=current
  had_current_chunks=true
  chunk_count_bucket=500_1000
```

## 6. 一言でまとめると

```text
Cloudflare の serverless 構成では「各 API を正しく呼ぶ」だけでは足りない。
D1 を source of truth / recovery ledger にし、
Vectorize を派生 index として扱い、
Queues は at-least-once 前提で idempotent にし、
DLQ は消さずに診断証拠として扱う。
```
