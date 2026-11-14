# Security and supply-chain foundation

境界の管理策を、すべての production-intent project に適用する。現行の OWASP ASVS と OWASP API Security Top 10 を、儀式的な checklist ではなく、threat model に基づく参照として使う。

## Identity と認可

- provider の identity を内部の identity model へ正規化する。provider の subject は不透明な文字列として保持する。
- secure cookie か bearer credential か、domain と subdomain の構成、SameSite、CSRF、CORS を一緒に決める。
- 所有と tenant の scope は、HTTP middleware だけでなく、共有の data access の境界で強制する。
- actor・tenant・資源の所有・policy を解決できない時は、既定で拒否する。
- 利用者をまたぐ access、tenant をまたぐ access、role の昇格、object 単位と property 単位の access に negative test を足す。
- background job と管理用 script を、明示的な principal と scope を持つ認可の呼び出し元として扱う。
- 権限の変更や管理者の操作など、監査記録が必要な操作は [運用の標準](operational-standards.md) に従って記録する。

References:

- https://owasp.org/www-project-application-security-verification-standard/
- https://owasp.org/www-project-api-security/

## Secret と設定

- 実際の secret、`.env`、`.dev.vars`、credential、token、production の data の copy を commit しない。
- secret でない設定は、version 管理して環境ごとに持つ。secret は deploy 先の platform か CI の secret store に置く。
- preview・staging・production の credential を分け、最小権限にする。
- 対応している場合は、長期の cloud credential より短命の federation・OIDC を優先する。
- secret の走査を、staged な変更に対して hook で、履歴全体に対して CI で実行する。誤検知の allowlist は、狭い範囲と理由を文書化する。
- token、cookie、authorization header、個人 data、機微な domain の field は、log に出す前に秘匿する。

## pnpm の管理策

production-intent の repository では、単一 package であっても、project の security 設定を `pnpm-workspace.yaml` に置く。設定名は pnpm の release に依存するので、生成の前に公式の settings を確認する。

```yaml
minimumReleaseAge: 10080
minimumReleaseAgeStrict: true
blockExoticSubdeps: true
```

lifecycle script が必要な依存には、狭い `allowBuilds` の対応表を定義する。すべてを許可する switch は使わない。cooling period の例外は、最小の package の範囲を名指しし、理由・期限・解除の trigger を foundation record に書く。

## GitHub Actions と Pinact

tag と branch は可変なので、full commit SHA への pin を baseline にする。production-intent の repository で GitHub Actions を使う場合、既定で Pinact を必須にする。

必須の振る舞い：

1. 外部の action と reusable workflow を full commit SHA に pin する。人が読める version の comment を残す。
2. Pinact に、action の更新に対する既定3日の最小経過日数を設定する。
3. local の hook で offline の Pinact 整合検査を、CI で検証と最小経過日数の検査を実行する。
4. `github-actions` と package の両方の ecosystem に対して、Dependabot か同等の更新 service を有効にする。
5. Pinact 自体を pin し、公式 release の checksum を検証する。または、同等に検証された tool manager から取得する。
6. local の `uses: ./...` は対象外にする。それ以外で技術的に pin できない参照は文書化する。
7. 置き換えは、組織の方針と別の tool が、不変の参照・検証・自動更新を同等以上に強制する時だけ許す。

最小の設定（生成の前に現行の schema を確認する）：

```yaml
# .pinact.yaml
version: 3
files:
  - pattern: .github/workflows/*.yml
  - pattern: .github/workflows/*.yaml
min_age:
  value: 3
  always: false
```

加えて：

- workflow と job の permissions を必要最小限にして明示する。
- 信頼できない event の field を shell script へ直接埋め込まない。
- `pull_request_target`、self-hosted runner、cache への書き込み、artifact の利用、workflow の変更を、危険度の高い面として扱う。
- download した binary の checksum か署名を検証する。
- repository が対応していれば、workflow と security 方針の変更に CODEOWNERS などの review の所有者を置く。

Reference: https://docs.github.com/en/actions/reference/security/secure-use

## 依存の保守

- package と Actions の ecosystem に対して、Dependabot か同等の更新 service を有効にする。
- 文書化した severity で audit の gate を実行し、到達可能な影響を調べる。機械的に自動修正しない。
- CI では lockfile を不変に保つ。
- 新しく入る maintainer、install script、exotic な取得元、推移的な native binary を確認する。
- supply chain の例外はすべて、期限付きで、機械的に検査できるか review できる台帳に記録する。

## 検査の水準

同梱の `check_invariants.py` は、曖昧さなく判定できるもの（package manager の正確な pin、lockfile、Action の不変な参照、Pinact、Actions の更新）を error にする。同等の tool で満たせるもの（secret の走査、hook の runner、package の更新 service、workflow の permissions、`noUncheckedIndexedAccess`）は warning にする。warning は、同等の手段を foundation record に書いた場合に限り受け入れてよい。
