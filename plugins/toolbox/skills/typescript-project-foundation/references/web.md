# Web profile

SSR、server components、native の描画、その他 framework 固有の要件が無い client-rendered な web application には、React と Vite を使う。

## Baseline

- 作業時点で互換性のある最新の stable な React と Vite
- 環境ごとに安全な公開設定と、server の secret を分ける
- route と API の schema は、意図した package の境界を通してだけ共有する
- accessible な semantic HTML、keyboard 操作、focus の扱い、error と状態の通知
- error boundary と、loading・空・error の状態
- 振る舞いに対する unit・component test と、少数の価値の高い browser の流れ

## 条件付きの選択

### TanStack Router

SPA に複数の route があり、型付きの path・search params、nested layout、loader、route の prefetch、route 単位の認証の便益がある時に足す。1画面の application に router は要らない。

### TanStack Query

自明でない server state がある時に足す。cache、invalidation、mutation の lifecycle、retry、polling、楽観的更新、route の preload。静的・local の状態や、単発の fetch を、stack の統一だけを理由に包まない。

### Tailwind

utility-first の styling が、意図する component・token の戦略と開発の流れに合う時に足す。API だけの project に足さない。design の判断の代わりにしない。保守する UI があるなら、token、focus の状態、contrast、responsive の振る舞い、component の所有を早く決める。

## Security の境界

- 認証を実装する前に、same-origin か cross-origin かを決める。
- cookie の domain、Secure、HttpOnly、SameSite、CSRF、CORS を一緒に決める。
- Vite の環境変数を通して server の secret を露出させない。
- route guard は利用体験として扱う。権威を持つのは server 側の認可である。
- server の error の詳細や、安全でない HTML を描画しない。
- Content Security Policy、HTTPS の強制、frame への埋め込みの制限を、配信する側の header で設定する。現行の推奨値は作業時に確認する。

## Testing

- component と状態の振る舞いには Vitest
- Mock Service Worker などは、contract を保てる所だけで使う。実際の API との integration test を残す
- 認証、認可の拒否、破壊的操作の確認、重要な利用の流れには browser・E2E test
- agent が自分で画面を確かめられるよう、browser automation による自己検証の入口を用意する（[Agent-ready repository](agent-ready-repository.md)）
- UI の細部には、人による見た目と操作の確認が引き続き必要である
