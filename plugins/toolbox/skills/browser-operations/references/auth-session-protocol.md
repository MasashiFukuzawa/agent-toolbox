# Cooperative authentication — protocol details

## Why the user's own Chrome can never help

Chrome 136+ ignores `--remote-debugging-port` on the default user profile (anti-cookie-theft change), and profile dirs are locked while Chrome runs. So there is **no way** for an agent to see a login the user performed in their daily browser. The only working pattern: **the user logs in inside the browser window the agent opened.** Say this plainly when asking — it prevents the frustrating "I logged in but you still can't see it" loop.

## Handoff templates

Opening handoff (after `pwauth <key> open <login-url>`):

> 「ログインが必要です。**今エージェントが開いた Chrome ウィンドウの中で**ログインしてください。普段お使いの Chrome でログインしても、仕様上わたしからは見えません。
> このプロファイルには作業に必要なアカウントだけを入れてください（金融・決済・個人 Google アカウントは入れないでください）。
> ログインが済んだら「done」等で教えてください。一度ログインすれば記憶されるので、次回以降・他の repo でも再ログインは不要です。」

Session-expired variant:

> 「<site> のセッションが切れていました（ログイン画面へリダイレクト）。もう一度、エージェントが開いたウィンドウでログインをお願いします。」

Chrome DevTools lane variant (first authenticated debug):

> 「デバッグには Chrome DevTools 側のブラウザを使います。こちらは操作用とは別のプロファイルなので、このウィンドウでの初回ログインだけ追加でお願いします。」

## Waiting for login

- Poll cheaply: check current URL, or `snapshot` a small target (header/account menu), every few seconds — or simply wait for the user's "done".
- Never snapshot full pages repeatedly while waiting; that is the token-burn pattern this skill exists to stop.
- After login: verify the **displayed user/tenant** matches expectations before doing anything, especially before state-changing actions.

## The 30-second cookie-flush trap (verified)

Chromium writes cookies to the profile's DB asynchronously (~30 s cycle). Verified behavior of `playwright-cli`:

- login → immediate `close` → **session lost** (cookies never reached disk)
- login → ≥40 s of further activity or idle → `close` → session persists and is sent on next open

Rules:

1. After a successful login, do not `close` within ~40 s. Continuing the actual task usually covers this naturally.
2. If the task finishes immediately after login, wait (`sleep 40`) before `pwauth <key> close`.
3. If a "remembered" session is unexpectedly gone, the likely cause is an early close right after login — redo the cooperative login once and keep the browser open longer.

## SSO / MFA / CAPTCHA

- All three are human steps by design — never try to automate or bypass them. The cooperative protocol already handles them: the human completes the challenge in the agent's headed window.
- SSO via IdP redirect: the profile stores the site session; the IdP session may expire earlier. Re-login goes through the same handoff.
- Device-trust prompts ("remember this device"): the user may accept them — the profile persists that trust, reducing future MFA prompts.

## Failure triage

| Symptom | Action |
|---|---|
| Redirect to login / 401 / 403 on a "remembered" site | One cooperative re-login (session likely expired or was closed too early). Recurs → report, don't loop |
| `SingletonLock`-style launch error | Another session is using this profile key. Auth needed → report & wait. Never delete lock files |
| Profile behaves corrupt (crashes, endless login loop) | Delete `~/.mcp/browser-profiles/<key>` only (one site), re-login |
| `pwauth: playwright-cli が PATH にない` | Follow `references/setup.md` and verify the CLI installation |
| Login page blocks automation (bot detection) | Report honestly; do not attempt evasion |
