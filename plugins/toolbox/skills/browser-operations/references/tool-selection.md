# tool選択 — 詳細

## 3つのtool

| | @playwright/cli | Playwright MCP | Chrome DevTools MCP |
|---|---|---|---|
| 役割 | **act**（第一選択） | act（fallback） | **observe**（debug・性能） |
| 呼び出し | Bash：`playwright-cli` / `pwauth` | MCPのtool `browser_*` | MCPのtool（snapshot、traceなど） |
| tokenの消費 | 最小。結果は `.playwright-cli/` に書かれ、必要なものだけ読む | 多い。ほとんどの操作の後にsnapshotがcontextへ返る | 中程度。必要な時に取りに行く |
| 認証session | `pwauth` 経由の、サイトごとの永続profile（repo間で共有） | **repoごと**の永続profile（workspaceのhash） | 共有の永続profileが1つ |
| 既定でheadlessか | はい（`--headed` で表示。`pwauth open` は常にheaded） | いいえ（headed） | いいえ（headed） |
| 対応browser | chromium/firefox/webkit/chrome/msedge | 同じ | Chromeのみ |

## どれを選ぶか

- **actの作業**（移動、click、フォーム入力、内容の抽出、UIの流れの確認、upload/download）：`@playwright/cli`。Playwright MCPへ下がるのは、BashやCLIが使えない時だけ（shellの無いsandboxのhostなど）。
- **observeの作業**（「なぜ遅いか」「何がエラーか」、Core Web Vitals、requestのwaterfall、consoleのエラー、memory）：Chrome DevTools MCP（`performance_start_trace`、`list_network_requests`、`list_console_messages`、`lighthouse_audit`、emulation）。
- **両方が要る**：まずCLIで操作し、失敗を深く調べる必要が出たら、Chrome DevTools MCPで再現する。

## @playwright/cli のコマンド対応表（v0.1.x）

基本の流れ:

```
playwright-cli open <url>            # 認証が要るなら: pwauth <key> open <url>
playwright-cli snapshot              # ページのsnapshot → .playwright-cli/*.yml。要素にrefが付く（e15…）
playwright-cli click e15             # snapshotのrefに対して操作する
playwright-cli fill e20 "text"
playwright-cli eval "document.title"
playwright-cli screenshot [target]   # ファイルのpathが出力される。必要な時だけ読む
playwright-cli close
```

役に立つ追加機能:

- session：`-s=<name>` で複数のブラウザを並行して動かす（`pwauth` はこれをprofile keyに自動で設定する）。
- `console [min-level]`、`requests`、`request <n>`：toolを切り替えずにできる軽いdebug。
- `state-save` / `state-load`：storageStateのファイル。認証情報として扱い、repoのrunbookが求める時だけ使う（この流れは e2e-capability-verification の担当）。
- browserのbinaryが無ければ `install-browser [browser]`。
- 取得物はCWDの `.playwright-cli/` に置かれる。認証済みページのものは認証情報に準じる。commitしない（CLIを使うrepoではgitignoreに入れる）。

真偽値のflagは値を取らない（`--headed` と書き、`--headed=true` とは書かない。`cookie-set --secure=true` はcrashする）。

## Playwright MCP（fallback）の注意

- toolはhostのMCP名前空間の下の `browser_*`（navigate、click、fill_form、snapshotなど）。
- 永続profileはrepoごとで、ログインはrepoをまたいで引き継がれない。認証が要るなら、このブラウザの中で協調ログインを行う。sessionはこのrepoの中でだけ残る。
- pwauthのprofileへ向けない。profileの形式とlockは、2つの経路の間で共有されない。

## Chrome DevTools MCPの注意

- 得意なこと：`performance_start_trace` → `performance_analyze_insight`、`lighthouse_audit`、networkとconsoleの一覧、CPUとnetworkのemulation、heap snapshot。
- profileはrepo間で共有され、ログインを自身で保持する。ただしpwauth側とは*別の*profileなので、あるサイトを認証済みで初めてdebugする時は、そちらで1回ログインが要る。
- profileと取得物は認証情報に準じて扱う（SKILL.mdのガードレール参照）。
