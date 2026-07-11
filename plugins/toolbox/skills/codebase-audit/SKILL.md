---
name: codebase-audit
description: >-
  コードベース全体を横断監査し、重大度・根拠ファイル・改善案を構造化する。技術負債や設計課題の包括的な洗い出しに使う。単一ファイルや PR のレビューには使わない。「技術負債を洗い出して」「横断的にレビュー」を正のトリガーとし、特定差分のセカンドオピニオンには reviewer skill を使う。
---
# Codebase Audit Skill

コードベースを A×B マトリックス（9技術領域 × 5評価軸）で包括的に監査し、構造化された改善提案レポートを生成する。

このスキルは汎用の正本であり、特定 repo の業務前提・セキュリティ境界・運用ルールを本体に埋め込まない。repo 固有の前提は対象 repo の `docs/agents/profile.md` から読み取り、監査時の Domain Lens と repo invariant として適用する。

---

## Step 1: パラメータ収集

起動時に以下を確認する。すでに指定されているパラメータは再確認しない。

```text
コードベース監査を開始します。以下を教えてください。

1. 対象 repo のパス（複数可、カンマ区切り）
2. 追加分析領域（任意。なければ「なし」）
3. スキャン深度
   - quick: 設定ファイル・設計文書・スキーマ・主要実装中心
   - deep: quick + 全実装ファイル精読
```

パラメータが揃ったら、破壊的操作なしで分析を開始する。

---

## Step 2: Repo Context と Domain Lens の抽出

各 repo で次の順に探索する。標準 profile は `docs/agents/profile.md`。存在する場合は最優先で読み、Domain Lens、repo invariant、canonical verification path、secret/PII handling を抽出する。

1. `docs/agents/profile.md`
2. `AGENTS.md`
3. `DESIGN.md` または `docs/**/DESIGN.md`
4. ADR index: `docs/adr/README.md`, `docs/adrs/README.md`, `docs/adr/*.md`, `docs/adrs/*.md`
5. Guidelines / policies / runbooks: `docs/guidelines/`, `docs/policies/`, `docs/runbooks/`
6. Contracts / API / DB / tests: shared schemas, OpenAPI, DB schemas, migrations, policy files, representative tests

`docs/agents/profile.md` がない場合は、警告を出して続行する。その場合、上記 2〜6 から暫定 Domain Lens を抽出し、レポートの `Assumptions` に「profile 不在のため暫定」と明記する。

読み取り時の注意:

- `AGENTS.md` に Document Routing がある repo では、routing の制約を尊重する。ただし profile の有無を確認するための `docs/agents/profile.md` 読み取りは標準探索として扱う。
- secrets、tokens、cookies、storageState 内容、raw PII、機密原文、provider raw payload は読まない・出力しない。必要な場合でも existence、path、metadata、redaction policy の確認に留める。
- Domain Lens は finding の優先度付けに使う。一般的なベストプラクティスだけでなく、repo invariant への違反・未文書化・検証不足も評価する。

---

## Step 3: スキャン対象

### quick モード

以下を優先的に読む。

- ディレクトリ構造
- 設定ファイル: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Dockerfile`, `docker-compose.yml`, `.env.example`, Terraform, CI/CD yaml
- Step 2 の探索順で見つかった AI/doc/routing/ADR/guideline/runbook
- スキーマ・マイグレーション: Prisma, Drizzle, SQL, ORM models
- 主要なドメインモデル、サービス層、API route、policy、代表テスト

### deep モード

quick の内容すべてに加え、全実装ファイルを精読する。ロジック、クエリ、認可境界、状態遷移、運用境界、テスト実効性まで踏み込む。

---

## Step 4: A×B マトリックス分析

発見がある場合のみ記載し、問題のない領域・評価軸は省略する。

### A軸: 技術領域

1. アーキテクチャ・ドメイン設計
2. DB・データ層（スキーマ・マイグレーション・クエリ）
3. API・インターフェース設計
4. 認証・認可・セキュリティ
5. インフラ・CI/CD・環境設定
6. テスト
7. 観測可能性（ログ・メトリクス・トレーシング・アラート）
8. 外部サービス連携
9. DX・開発環境（ローカル開発・ドキュメント・ツールチェーン）

ユーザーが追加した領域があればここに追加する。

### B軸: 評価軸

- **[BP乖離]**: 業界標準・ベストプラクティス・原理原則からのずれ
- **[一貫性]**: 同一コードベース内での設計・命名・実装スタイルの不一致
- **[暗黙知]**: ADR・ガイドライン・profile・runbook 不足で意図や方針が暗黙知になっている箇所
- **[陳腐化]**: デッドコード・古い実装・廃止予定 API・使われていない設定・古いドキュメント
- **[AIドキュメント]**: AI が自律稼働・高精度アウトプットするために整備が必要なドキュメント

### Repo Invariant の扱い

各 finding には、可能な限り profile または探索資料から抽出した repo invariant を紐づける。

例:

```markdown
- [認証・認可][一貫性][高] `path:line`: 問題 / **Repo invariant**: `docs/agents/profile.md` の `<短い不変条件>` / **提案**: ...
```

該当する invariant がない場合は `Repo invariant: なし（一般原則）` と書く。存在すべき invariant が未文書化なら、それ自体を [暗黙知] または [AIドキュメント] finding として扱う。

### 分析姿勢

- サンクコストや修正コストを気にせず、今から設計するならどうあるべきかを起点にする
- 「業界ではよくある」という理由だけで問題を見逃さない
- 具体的なファイルパス・行番号・コード箇所を可能な限り引用する
- 優先度（高/中/低）は「本番稼働時の影響度 × 現時点で直さなかった場合の将来修正コスト」で決める

---

## Step 5: レポート出力

以下のフォーマットで出力する。発見のない領域は省略する。

```markdown
# {REPO_NAME} 監査レポート（{DATE}）

## Domain Lens
- <profile または暫定抽出した重点レンズ>

## Evidence Sources
- <読んだ profile / AGENTS / DESIGN / ADR / guidelines / runbooks / contracts / tests>

## Assumptions
- <profile 不在、未確認領域、読み取り制約、秘密情報を読まなかったことなど>

## サマリー
- 発見件数: 高{N}件 / 中{N}件 / 低{N}件
- 最重要課題（Top3）:
  1. ...
  2. ...
  3. ...

---

## {領域名}

- [{評価軸}][{高|中|低}] `{ファイルパス:行番号 or 対象コンポーネント}`: {問題の説明} / **Repo invariant**: {profile・AGENTS・ADR等との紐づき} / **提案**: {理想形・改善方法}

---

## クロスカッティング・コンサーン（任意）

複数領域にまたがる構造的問題があれば記載。
```

### 複数 repo の場合

各 repo を順番に分析・出力した後、最後に以下を追加する。

```markdown
---

## クロスリポジトリ分析

### 共通問題
複数 repo に同様の問題がある場合に記載。

### repo 間の設計不一致
片方の repo にあってもう片方にない設計・パターン（統一すべきもの）を記載。

### 全体優先度 Top 10
全 repo の高優先度発見から横断的な Top 10 を選出。
1. `[{repo}]` [{領域}][{評価軸}] ...
```
