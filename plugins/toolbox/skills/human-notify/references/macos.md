# macOS adapter

急ぎの連絡（`human_notify.py`）は、Python 3.11以降、Git、macOSの`osascript`と`say`を使う。追加パッケージは不要。
通知センターのバナーは正常終了でも表示されない場合があるため、急ぎの連絡には確認ボタン付きダイアログを使う。
スクリプトはAppleScriptへ本文をargvで渡し、本文をコードとして評価しない。

## 設定と状態

- 設定: `${XDG_CONFIG_HOME:-~/.config}/human-notify/config.json`
- 状態: `${XDG_STATE_HOME:-~/.local/state}/human-notify/`

`configure`はIDと名前を保存する。番号は一覧取得時のもので、配布物やrepo設定へ固定しない。
読み上げ名を変える場合はconfigの`repo_names`へ表示repo名と読み方のmappingを追加する。

```json
{
  "device_id": "42",
  "device_name": "Built-in Output",
  "repo_names": {"example/sample-app": "サンプルアプリ"}
}
```

表示repo名は変えず、音声の先頭だけ読み方を使う。読み方も他repoと区別できる名前にする。
状態には通知識別子のhash、job ID、結果を保存する。通知本文は一時jobファイルに入り、処理終了時に削除する。
中断時は本文が残る場合がある。状態ディレクトリを公開・commitしない。
履歴を消すと重複抑止が解除される。実行中のjobがある状態では削除しない。

## 実機確認

1. `devices`と`configure`で内蔵スピーカーを選ぶ。
2. テスト用eventで`send`を実行する。実際に画面・音が出ることを先に伝える。
3. ヘッドホン接続中に、repo名付きのダイアログと内蔵スピーカーの音声を確認する。
4. `send`がすぐ返り、`status`が終了後にchannel別の結果を返すことを確認する。
5. 同じevent/revisionを再送して`duplicate`となり、再び鳴らないことを確認する。

プロセス結果だけで見えた・聞こえたと判定しない。実際の到達確認はユーザーの報告を使う。

## 止まった時の知らせ（`waiting_notify.py`）

`osascript` の `display notification` でバナーを出す。本文はargvで渡し、コードとして評価しない。

- バナーは、scriptを実行するアプリの通知として扱われる。システム設定の「通知」で、そのアプリの通知を許可する。集中モードの間は表示されない。
- 実機確認: 印を付けたworktreeで `send --message 'テスト'` を実行し、バナーが見えることをユーザーに確かめてもらう。`waiting.log` の `delivered` だけで見えたと判定しない。
- 記録は状態directoryの `waiting.log` に追記される。記録に入るのは案件名・ゴール名・状態と、失敗した時のOSのエラー出力で、本文は入らない。
