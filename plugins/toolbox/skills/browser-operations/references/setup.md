# Setup — 背景と導入手順

どの環境でも使える導入手順を示す。repository固有のscriptには依存しない。

## 導入されるもの

1. `@playwright/cli`：npmのglobal install（`npm install -g @playwright/cli@latest`）。npxは使わない。呼び出しのたびに解決し直すので、CLIの速さとtoken効率の利点が消え、版も固定されない。
2. `~/.mcp/browser-profiles/`（chmod 700）：サイトごとの認証profileを置く親dir。サイトのdir（`github`、`notion` など）は、初回ログイン時にwrapperが作る。
3. `~/.local/bin/pwauth`：wrapper。`open` の時だけ `-s=<key> --persistent --profile=$HOME/.mcp/browser-profiles/<key> --browser=chrome --headed` を付け、それ以外のコマンドには `-s=<key>` を付ける。理由：profileのflagをLLMが手で打つ形だと、1つ付け忘れるだけで黙ってin-memory profileになる（「sessionが消えた」）。wrapperにより、認証の経路が1つの固定した名前になる。

## 設計上の判断（要点）

- **MCPの設定は変えない**（ClaudeもCodexも）。ログイン済みの共有profileをMCP serverの既定に入れると、信頼できないサイトの閲覧を含むすべての作業にcookieを持ち込み、並行sessionが1つのprofile lockで直列になる。CLI側のwrapperなら、認証が実際に要る時だけ、repoをまたぐ永続化が得られる。
- 共有profile1つではなく、**サイトごとのprofile key**にする。作業ごとの認証情報の露出が最小になり、別のサイト同士が同じlockを取り合わない。
- **安全側に倒す**：wrapperを導入する前に、CLIが `--persistent/--profile/--headed/--browser` を持つことを確かめる。flagの構成が変わっていたら止める。

## 手作業の手順（repoが手元に無い場合）

```bash
npm install -g @playwright/cli@latest
mkdir -p ~/.mcp/browser-profiles && chmod 700 ~/.mcp ~/.mcp/browser-profiles
# 導入したCLIのflagを確かめてから、ローカルのwrapperを作る
```

このSkill同梱のinstallerを実行する:

```bash
bash scripts/install-pwauth.sh
pwauth --help 2>/dev/null || true
```

installerはCLIの必須flagを検証してから、`~/.local/bin/pwauth`と権限`0700`のprofile rootを作る。repository固有のhealth-check scriptには依存しない。

## 付録（任意）：Playwright MCPでもrepoをまたぐprofileを使う

推奨しない（設計上の判断を参照）。repoごとのfallback profileが実際に負担になった場合だけ行う。手順はhostごとに異なるので、実行時点の各hostの文書とhelpで確かめる。

1. Playwright MCP serverの起動引数に `--user-data-dir=$HOME/.mcp/browser-profiles/playwright-mcp --browser chrome` を足す。
   - Claude Code：既存のPlaywright MCP（pluginで入れたもの）を外してから、user scopeのMCP serverとして登録し直す。skillを同梱するplugin（chrome-devtools-mcpなど）は外さない。
   - Codex：`~/.codex/config.toml` の `[mcp_servers.playwright]` のargsを同じように書き換える。
2. **flagが子プロセスまで届いていることを確かめる。** npx経由のMCPで引数が落ちる報告がある。session開始後に `ps aux | grep mcp-server-playwright` で `--user-data-dir=…` が見えること、または使用後にprofile dirのmtimeが変わることを確かめる。落ちているなら、npxを介さず導入済みのbinaryを直接呼ぶ。
3. このSkillの既定が避けている不利益を受け入れる：すべてのMCP閲覧作業でcookieが共有され、session間でlockを取り合う。
