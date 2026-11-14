# Quality and delivery foundation

## Tool の所有者

1つの関心事に1つの所有者を置く。

- 型の正しさ：`tsc`
- lint：既定は oxlint
- format：既定は oxfmt
- 使われていない export・file・依存：Knip
- test と coverage：Vitest と、runtime 固有の harness
- git hook：Lefthook

Biome の統合された範囲の方が repository に合う時は、lint と format の組を Biome に替える。Oxc・Biome・ESLint・Prettier を重複した権威として残さない。専用の plugin がまだ必要な場合は、重ならない責務を文書化する。

## 統一 command

`lint`・`typecheck`・`test`・`build`・`verify` の script 名と役割は [Agent-ready repository](agent-ready-repository.md) の表に従う。hook と CI は同じ script を呼び、検査の内容を別の場所に二重に書かない。

## TypeScript の baseline

- `strict: true`
- runtime と global の `types` を明示する
- `noUncheckedIndexedAccess` と `exactOptionalPropertyTypes` を有効にする。確認済みの ecosystem の衝突がある時だけ外し、理由を記録する
- 互換性の逃げ道として、広い `skipLibCheck`、`any`、検査されない assertion を使わない
- runtime が違う場合は、browser・Worker・Node・test の global を分ける
- project references は、package の build と型の境界に便益がある時だけ使う

## Test の戦略

振る舞いと境界を軸に test を設計する。

- 純粋な domain の振る舞いと parsing の unit test
- database の repository、migration、外部 adapter の integration test
- Workers・workerd の挙動に対する、runtime に忠実な test
- client が独立している場合の、API の schema と error に対する contract test
- principal や tenant をまたぐ access の negative な認可 test
- runtime の互換性を確かめる build と deploy の dry-run
- application の種類に合った自己検証の手段（[Agent-ready repository](agent-ready-repository.md) の表）

coverage は診断であって目標ではない。行の割合を上げるより、error・retry・rollback・境界の振る舞いに意味のある assertion を求める。

## Hook の分担

local の feedback を速く保つ。

- pre-commit：staged な file の format と lint、secret の走査、workflow の SHA と Pinact の整合、lockfile を凍結する方針
- pre-push：typecheck、全体の lint、Knip、関連する test、build
- CI：clean な install、すべての検査（`verify`）、coverage と integration test、履歴の secret 走査、依存の audit、Pinact の最小経過日数の検証、runtime と deploy の dry-run

network に重く依存する download や、remote の変更を pre-commit に置かない。

## CI/CD

- 外部の Action はすべて full SHA に pin する。
- workflow と job の permissions を最小にして明示する。
- 競合する deploy を防ぐ concurrency group を使う。deploy の途中で cancel しない。
- deploy の前に build と test を行う。migration は、互換性の方針を明示して適用する。
- 操作できる UI・API がある product は、production の前に preview か staging を使う。
- remote の deploy・database・secret の操作は、skill の local 変更への一括承認に含めない。

## Deploy の安全手順

deploy 先に依らず、次の順で行う。command と出力の形式は tool の version に依存するので、実装時に公式 documentation と `--help` で確認する。

1. **preflight**：対象の環境、権限、未適用の migration、新旧の code の互換性を確認する。
2. **capture**：deploy の前に、現在正常に動いている version の識別子を機械が読める形で保存する。これが rollback の対象になる。
3. **deploy**：実行した command、version、結果を記録する。
4. **smoke**：deploy された endpoint に対して、health だけでなく代表的な読み取りの経路を、timeout と retry の上限付きで確かめる。副作用のある操作を smoke に使わない。
5. **rollback**：smoke が失敗したら、保存した version へ戻し、戻した後の状態も同じ smoke で確かめる。
6. **report**：deploy と rollback の両方を含む最終状態を報告する。途中の失敗を成功として扱わない。

rollback できない migration や外部への副作用を含む変更は、自動 deploy を止め、互換期間を持つ expand/contract の設計を先に行う。

## Repository の設定

次は remote の設定なので、適用の前に確認を取る。

- default branch を保護し、直接の push を禁じる。merge の条件に必須の check（`verify` を含む CI）を指定する。
- workflow、security の方針、migration の変更に code owner の review を要求する。repository が対応している場合に限る。
- 例外：1人で保守する disposable-spike。
- 強制する手段：設定を repository の rule として持ち、可能なら設定の定義を code として管理する。

## Architecture check

foundation の規則を、project 固有の検査に変換する。例：

- 生の database client の import は、database・repository の package の中だけに許す
- UUID の直接生成は ID module の外で禁止する
- tenant が所有する repository は、すべて tenant の scope を必須にする
- API の ID・日時・金額の field は、すべて共有 schema を使う
- log の出力は logger module だけ、環境変数の参照は config module だけ、現在時刻の取得は clock module だけに許す
- package や layer の依存の方向を、import の規則として検査する
- 可変な GitHub Action の参照を置かない
- migration と生成された schema が同期している
- config の binding と型が再生成済みで、差分が無い

違反の message は修正指示として書く（[Agent-ready repository](agent-ready-repository.md)）。同梱の `check_invariants.py` は汎用の検査だけを行う。project 固有の証明と取り違えない。
