# Agent Toolbox

Claude Code と Codex で利用できる、汎用エージェントスキルの公開コレクションです。

## Plugins

- `toolbox`: 設計、調査、レビュー、検証、可視化のスキル
- `done`: リポジトリ定義に従う品質ゲート。Claude Code 用 Stop hook を同梱
- `gog`: `gog` CLI を使う Google Calendar / Chat 読み取りスキル

各スキルの frontmatter はホスト共通の `name` と `description` だけを使います。必要な CLI や安全契約は本文に記載します。

## Security

認証情報、組織固有情報、個人情報をリポジトリへ追加しないでください。`scripts/validate.rb` はスキル規約、内部参照、代表的な機密パターンを検査します。

## License

Apache-2.0
