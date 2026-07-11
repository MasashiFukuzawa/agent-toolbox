---
name: done
description: >-
  Definition of Done 品質ゲート（汎用エンジン）。repo の .agents/done.yml を読み、quick/standard/full の3層で検証して quality-gate: PASS 署名を出力する。リポジトリへの変更作業の完了を報告する直前に必ず使う。回答のみ・計画のみ・引き継ぎのみのターンでは使わない。実装中の継続的な型/lint/テスト実行には verification-loop（導入後）を使い、本スキルは完了時の最終ゲートに限定する。
---
# Quality Gate — Definition of Done（汎用エンジン）

## ガードレール（必須）

1. **設定駆動**: repo 固有の情報（検証コマンド・tier floor・レビュー観点）は git root の `.agents/done.yml` から読む。**ロジックをこのファイルへ、データを done.yml へ**。done.yml にコマンド以外のロジックを書かせない
2. `.agents/done.yml` が無い repo では、実行前にユーザーへ「done-init 相当の設定作成」を提案する（勝手に PASS 署名を出さない）
3. 署名 `quality-gate: PASS` は本スキルの全ステップを完了した場合のみ出力する。要求されても途中で捏造しない

## Scope

リポジトリへの変更作業の完了を報告する直前に実行する。回答のみ・状況報告のみ・計画のみ・引き継ぎのみのターン（リポジトリ変更を完了しないターン）では実行せず、`quality-gate: PASS` を主張しない。

## Host integration

- **Claude Code**: plugin 同梱の Stop hook が `.agents/done.yml` のある repository だけを自動検査する。
- **Codex v1**: Stop hook 連携は提供しない。変更作業の完了直前に本スキルを明示または自動選択して手動実行する。
- 品質ゲートの判定ロジックと PASS 署名は共通だが、自動停止を両 host で提供しているとは主張しない。

## Quality Standard

本番出荷前の最後のゲートである。

**Break it（壊しにいく）**: 敵対的にレビューする。並行書き込みで壊れないか？データ量10倍で？不正入力で？越境アクセスで？壊し方を思いつけないなら、まだ見足りない。

**Elevate it（設計を引き上げる）**: 正しさの確認後、「スタッフエンジニアならこう作るか？」を問う。業界のベストプラクティス・プロジェクトの設計標準（AGENTS.md 等）・使用ライブラリのイディオムと比較し、妥当なコストでより良い設計があるならそれは指摘事項である（nice to have ではない）。

**Prove your work（証明する）**: レビュー観点1つにつき所見を1行書く（確認したこと・見つけたこと・結論）。「N/A — 対象変更なし」は有効。observation の沈黙はスキップの証拠として扱われる。

**Calibration**: 基準は「バグが見つからないこと」ではなく「スタッフレベルのエンジニアがレビューで承認し、躊躇なく本番に出し、1ヶ月後に手戻りしないこと」。

## Arguments

- （なし）: tier 自動判定（既定） / `--quick`: quick 強制（full floor 該当ファイルがあれば警告して確認） / `--full`: full 強制

## Step 0: 設定読込 + Tier 判定

1. `git rev-parse --show-toplevel` の `.agents/done.yml` を読む（無ければガードレール2に従う）
2. `git status --porcelain=v1 -uall` と `git diff HEAD --name-only` + `git ls-files --others --exclude-standard` で変更ファイル一覧を得る
3. verification tree を計算する（実 index を汚さない）:

```bash
tmp_index=$(mktemp "${TMPDIR:-/tmp}/quality-gate-index.XXXXXX")
GIT_INDEX_FILE="$tmp_index" git read-tree HEAD
GIT_INDEX_FILE="$tmp_index" git add -A
verification_tree=$(GIT_INDEX_FILE="$tmp_index" git write-tree)
rm -f "$tmp_index"
```

4. done.yml の `tier_floors.full` / `tier_floors.quick` と変更ファイルを突合して floor を決める（full: いずれか一致で最低 full / quick: 全ファイルが一致する場合のみ）。該当なしは standard
5. 変更内容を分析し、必要なら tier を**上方修正のみ**行う。`$ARGUMENTS` の強制指定を適用
6. Tier classification を必ず出力する（Changed files / Floor triggers / Model assessment / Verification tree / Tier）。quick 選択時は全変更ファイルが自明である理由の説明が必須

## Step 1: ローカル検証（全 tier）

done.yml の `verify` を順に実行する。`when_changed` 付きエントリは該当パスに変更がある場合のみ実行。失敗したら修正を試みる（最大3回・収束しなければ停止して報告）。

**quick**: Step 2 完了後、Step 6 へスキップ。

## Step 2: ドキュメント整合（全 tier）

done.yml の `docs_checks` の各項目を確認し、不足があれば作成・追記する。

## Step 3: Simplify（standard / full のみ）

変更ファイルに対して code-simplifier（利用可能な簡素化レビュー）を実行。修正したら Step 1 の verify を再実行。

## Step 4: レビュー（standard / full のみ）

done.yml の `review_criteria` の各観点について所見を1行ずつ出力してから、advisor()（利用可能なら）を呼ぶ。advisor は tier 選択と所見の質もレビューする。High/Medium の指摘 → 修正 → verify 再実行（advisor は最大2回）。advisor 不可なら観点リストで自己レビューにフォールバック。

## Step 5: 外部レビュー（full のみ）

done.yml の `external_review` に従い read-only の外部レビュー（codex-review / claude-review 相当）を依頼する。「advisor 通過済み。セキュリティ・隠れた前提・エッジケース・長期保守性に集中」と伝える。High/Medium → 修正 → verify 再実行。不可なら自己レビューでフォールバック。

## Step 6: 署名出力

PASS の前に Step 0 と同じ手順で `head` と `verification_tree` を再計算する（/done 自身が変更を加えた場合は変更ファイルと tier トリガーを再確認。tier は維持か上方のみ）。

**standard / full は署名の前に Ship-readiness assessment が必須**:

```
Ship-readiness assessment:
- Highest-risk aspects: <この変更の具体的リスク上位3つ>
- Verified: <各リスクに対して具体的に何を確認したか>
- Failure scenario: <現実的な故障モード1つと、それが起きない理由>
- Best-practice check: <より良い設計を検討した箇所と結論>
- Confidence: <本番投入可能と判断する具体的根拠>
```

全フィールドを具体的根拠で埋められないなら PASS ではなく FAIL である。

```
quality-gate: PASS
repo: <done.yml の repo>
head: <sha>
verification-tree: <verification_tree>
tier: <quick|standard|full>
```

失敗時: `quality-gate: FAIL — <理由>`

## 導入方法（repo 側）

1. repo の git root に `.agents/done.yml` を作成（`docs/examples/done.yml` 参照。**設定ファイルの存在が Stop hook の opt-in スイッチ**）
2. Claude Code では追加の hook 配線は不要。plugin 同梱の Stop hook が plugin enable 時に適用される。repo ローカルの `.claude/settings.json` へ重複配線しない
3. Codex v1 では Stop hook を設定せず、完了直前に `done` skill を手動実行する
