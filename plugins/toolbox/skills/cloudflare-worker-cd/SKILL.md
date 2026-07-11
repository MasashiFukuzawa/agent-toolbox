---
name: cloudflare-worker-cd
description: >-
  Cloudflare Workers の deploy、smoke test、失敗時 rollback を設計・レビューする。本番 CD とリリース障害に使う。複数サービスのデータ整合性には cloudflare-data-pipeline を使う。
---
# Cloudflare Workers CD

## ガードレール

- deploy 前に rollback 先の version identifier を取得し、検証する。
- deploy 成功だけでリリース成功としない。外部から副作用のない smoke test を行う。
- smoke 失敗時は捕捉済み version へ戻し、rollback 自体も検証する。
- token、account identifier、production URL をログや成果物へ埋め込まない。
- `wrangler` の command と出力形式は version 依存なので、実装時に公式 docs と `--help` を確認する。

## Pipeline contract

1. preflight: 対象 environment、権限、migration、互換性を確認する。
2. capture: 現在の正常 version を機械可読形式で保存する。
3. deploy: command、version、結果を記録する。
4. smoke: health だけでなく代表的な read path を timeout と retry 上限付きで確認する。
5. rollback: smoke failure なら保存済み version へ戻す。
6. report: deploy と rollback の双方を含む最終状態を通知し、失敗を成功扱いしない。

rollback 不能な migration や外部副作用がある場合は自動 deploy を止め、互換期間を持つ expand/contract 設計を先に行う。
