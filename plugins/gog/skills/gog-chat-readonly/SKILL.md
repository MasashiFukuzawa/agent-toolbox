---
name: gog-chat-readonly
description: >-
  gog CLI で Google Chat のスペース・メッセージ・スレッド・DM を読み取る。Chat 内の情報検索や履歴確認で使う。送信、リアクション、スペース作成などの書き込み操作には使わない。「Chatを検索」「スレッドを確認」などの参照依頼を正のトリガーとし、Calendar参照には gog-calendar を使う。
---
# Google Chat の読み取り

## 安全契約

- 実行してよいのは `gog chat` の読み取りサブコマンドだけ。
- 送信、作成、更新、削除、リアクションは実行しない。
- アカウントや OAuth client を推測しない。複数候補がある場合はユーザーに選択を求める。
- 認証情報、token、keyring の内容を表示・保存・共有しない。

## 前提確認

1. `command -v gog` で CLI を確認する。
2. 秘密値を出さない公式コマンドで利用可能なアカウントを確認する。
3. 必要なら `--account <alias-or-email>` と `--client <alias>` を付ける。既定値は埋め込まない。

## 基本操作

```bash
gog chat spaces list --max 50 --json --no-input
gog chat spaces find "<display-name>" --json --no-input
gog chat messages list "spaces/SPACE_ID" --max 50 --order "createTime desc" --json --no-input
gog chat threads list "spaces/SPACE_ID" --max 50 --json --no-input
gog chat dm space "<user-identifier>" --json --no-input
```

結果は必要な範囲だけ要約し、個人情報や会話本文を過剰に転載しない。権限エラーは回避せず、必要な read-only scope と対象スペースへの閲覧権限を案内する。
