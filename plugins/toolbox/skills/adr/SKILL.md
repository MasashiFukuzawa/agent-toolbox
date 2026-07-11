---
name: adr
description: >-
  Architecture Decision Record を起票・更新し、設計判断と既存記録の整合性を保つ。複数案から技術選定した時に使う。軽微な変更やコードベース全体の監査には使わない。「ADRにして」「この決定を記録して」を正のトリガーとし、コードベース全体の設計課題探索には codebase-audit を使う。
---
# ADR — 意思決定の記録と保守

## ガードレール

1. **決定の捏造禁止**: 会話・PR・コードから読み取れない「理由」「却下案」を創作しない。不明な項目はユーザーに1問だけ確認するか「記録なし」と書く
2. 既存 ADR と矛盾する変更を実装する場合、**実装より先に ADR の更新（supersede）を提案**する
3. repo に既存の ADR 規約（テンプレート・番号体系・置き場）があればそれに従う。無い場合のみ下記の既定を使う

## Step 1: 起票判断

ADR にする（いずれか該当）: 後から「なぜこうなってる？」と聞かれる選択 / 複数の実行可能な案から選んだ / 元に戻すコストが高い / チーム・将来の自分への制約になる。
ADR にしない: 実装詳細でコードを読めば自明 / いつでも無コストで変えられる / 好みの問題。

## Step 2: 置き場と番号

1. 既存 ADR を探す: `docs/adr/`, `docs/architecture/decisions/`, `adr/` の順に確認
2. 無ければ `docs/adr/` を作成し `README.md`（index）を置く
3. 番号は既存の最大値 +1（ゼロ埋めは既存規約に合わせる）

## Step 3: 本文（既定テンプレート）

```markdown
# ADR-NNNN: <決定を1行で（名詞句でなく決定文）>

- Status: Accepted | Proposed | Superseded by ADR-MMMM
- Date: YYYY-MM-DD
- Deciders: <人/セッション>

## Context
<この決定を迫った状況・制約。3-6行。将来の読者が当時の前提を再構築できる程度に>

## Decision
<何をどうすると決めたか。曖昧語（適切に・柔軟に）を使わない>

## Alternatives Considered
| 案 | 却下理由 |
|---|---|

## Consequences
- 良い影響: <>
- 受け入れたトレードオフ・リスク: <>
- この決定を見直すトリガー: <どういう状況になったら再検討するか>
```

## Step 4: 整合性の維持（起票と同時に必ず）

1. **index 追記**: `docs/adr/README.md`（または規約の index）に1行追加
2. **changelog**: repo に ADR changelog の慣習があれば追記
3. **相互参照**: 関連 ADR に「Related: ADR-NNNN」を追記。supersede 時は旧 ADR の Status を更新
4. **矛盾検出**: 新 ADR がコード・CI・既存 ADR と矛盾しないか grep で確認し、矛盾があれば所見として報告する

## 既存 ADR 群の保守（依頼されたら）

- index と実ファイルの突合（欠番・index 漏れ・Status 不整合）
- 「実装と乖離した ADR」の検出: Decision に書かれたパス・コマンド・構成が現存するか確認し、乖離一覧を提示（勝手に書き換えず、supersede か更新かをユーザーに確認）
