# Library and CLI profiles

## 公開する TypeScript library

実装の前に、公開 API の安定性を決める。

- 既定は ESM のみ。CommonJS は、確認済みの利用者の需要がある時だけ足す。
- `exports`、型、対応する runtime の version、side effect の metadata を明示する。
- 宣言 file を出力し、pack した成果物を clean な consumer fixture で test する。
- 実装の module は private に保つ。内部の型を誤って export しない。
- semantic versioning を使い、互換性と廃止の方針を文書化する。
- 現行の lockfile に加えて、対応する最も古い runtime と依存の範囲でも test する。
- 公開配布や保証の要件が正当化する時に、release の自動化、provenance・SBOM、署名を足す。

公開する成果物に workspace protocol の範囲を残さない。release の前に、package の tarball の中身を確認する。

## CLI

- stdin・stdout・stderr の contract と、安定した exit code を定義する。
- 人が読む出力と、機械が読む JSON 出力を分ける。
- 非対話・CI の mode では prompt を出さない。flag を用意し、対処が分かる error で失敗させる。
- 設定と引数を境界で検証する。
- signal と、途中までの書き込みを安全に扱う。
- 導入と配布の対象を決める：npm package、単体の binary、内部の workspace command。
- Windows を support するなら、Windows の path と process の挙動を test する。
- 明示的に要求され、開示され、設定で止められる場合を除き、telemetry を入れない。

どちらの profile でも、package の実際の責務が要求しない限り、React・Hono・Drizzle・Tailwind など application 専用の依存を避ける。
