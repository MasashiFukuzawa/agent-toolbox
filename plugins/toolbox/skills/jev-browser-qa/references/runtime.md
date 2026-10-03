# Experimental runtime

The runtime is a private Node 24 TypeScript package under `scripts/runtime`. It uses Playwright
1.63.0 and the official `@typesafe-ai/sdk` 0.6.0, pinned to `jev-1.13.0` and the official API origin by default. An explicit independent-playground option targets a
separate third-party service; it never tries another endpoint when authentication fails.
It has not been promoted to a production dependency or published as an npm package.

From the skill directory:

```sh
cd scripts/runtime
pnpm install --frozen-lockfile
pnpm typecheck
pnpm build
pnpm test
pnpm fixture
```

Install Playwright Chromium if it is not already available (`pnpm exec playwright install chromium`).
Run these commands with Node 24. The synthetic fixture makes no paid calls by default.

## Library contract

`dist/index.js` (built from `src/index.ts`) exports protocol version 1, `createSession(Page, Adapter)`, `createJevDecider`,
`Budget` and `openBudget`. The repository adapter owns context checks, exact allowed labels, per-action
permission and independent postconditions. It must restrict network requests and use an isolated
browser context. Selector strings are trusted adapter code; the model sees opaque action IDs,
permitted labels and supplied value aliases only. Password values and surrounding DOM text are
never part of observations. Parent text/value fingerprints remain inside owned browser handles. Matching supplied-value
aliases may appear in `satisfiedInputs`; raw values and unrelated content never do.

Session supports `observe`, `act`, `run`, `checklist` and `close`. Each observation is single-use.
After ordinary handoff, observe again; do not reuse an old action ID. An unconfirmed write
blocks further writes until the original request terminates, the wrapper reconciles its journal,
and a fresh browser Page is created. A successful goal checker never clears this fence. Do not retry it
because of a new observation. Multiple matches to one Rule are rejected; use a unique trusted selector. Current scope,
selector membership and target attributes are rechecked. Unresolved writes survive Session
replacement on the same Page; wrappers must persist an unresolved-mutation journal across process
restarts and reconcile authoritative state before rearming. DOM checks are not atomic with native
Playwright actions: the wrapper must also gate each mutation request. Runs own the Page across checker/model waits; concurrent operator primitives are rejected.
Individual operations are also serialized, and sessions own separate handles. `verified` requires the adapter's
checker. `afterAction=true` requires every external mutation to have committed durably or
be known not dispatched; toast/202/timeout must return false. Local input editing need not
satisfy the whole goal. Checks must include authoritative persisted state when a goal changes data. A goal classifier
cannot assert persistence. The default confidence floor applies to both action and blocker answers and is 0.9; this is an experimental routing
setting, not calibrated correctness or permission evidence.

The DOM reader supports common labelled native/ARIA controls. It does not implement the complete
accessible-name algorithm. Frames, shadow DOM, canvas, arbitrary keyboard widgets, drag-and-drop
and offscreen targets require an agent handoff. Upload requires a visible permitted input and
`Adapter.file` must supply verified in-memory synthetic bytes; path-only fallback is rejected.
It binds permitted bytes
when an exact file digest is part of repository authorization. Visual layout still requires separate inspection.

## Paid fixture experiment

Inject the API key locally; never paste it into a prompt. A repository wrapper may read a
private owner-only file or an approved secret store. Pass an upper bound for card-converted
JPY per USD, including fees, after checking current pricing/exchange conditions. Pricing is copied into an immutable decider snapshot;
recreate the decider to change rates or expiry.

```sh
# Once, in a private 0700 directory. Existing ledgers are never overwritten.
node src/cli.ts budget-init --ledger /private/qa-budget.json
node src/cli.ts fixture --provider jev --key /private/typesafe.key \
  --ledger /private/qa-budget.json --yen-per-usd-upper-bound 400 \
  --input-usd-per-million-upper-bound 0.042 --pricing-expires-at "$QA_PRICING_EXPIRES_AT"
```

Set `QA_PRICING_EXPIRES_AT` to an ISO timestamp within seven days after checking the destination
provider price. Pricing authority expires and is checked before every paid request; the library
also requires an explicit provider-bound pricing object as its sixth argument. It assumes the
confirmed upper bound remains valid until expiry; local accounting is not a provider spend cap.

The rate above is an illustrative conservative bound, not a quoted exchange rate. The budget
ceiling is 500 JPY for this experimental runtime. Share the ledger with application-side costs;
never reset it between comparison arms. The wrapper must reserve application costs before
arming a human paid action. If the application maximum cannot be established, keep it blocked.
SDK retries and logging are disabled. Each request reserves the model's full maximum input-token
cost. Known token usage settles downward; uncertain requests retain the reservation.

The library Budget requires an explicit persistence function; use `openBudget` in
the public entrypoint for a private locked ledger. In-memory persistence is only for synthetic
unit tests and cannot enforce a cumulative paid budget across processes. A missing ledger fails
closed. The ledger directory must be owner-only (0700). Key and ledger paths must be outside Git checkouts.

Only one process may own a budget ledger; an existing lock blocks another process. Do not remove
an unexplained lock. `elapsedMs` includes failed runs and adapter waits; phase events alone are not total control
time. The CLI records mode and ledger cost delta, including uncertain reservations. The run
millisecond limit is a soft between-operation limit; trusted wrapper callbacks need their own
timeouts. `observe`/`act` are operator primitives, not a bounded autonomous loop.

The CLI emits sanitized metrics, never API bodies, credentials, DOM or goals.

`--provider jev` uses the official TypeSafe API and its $0.042/M input-token rate.
`--provider jev-playground` explicitly uses the independent `jevtypesafeai.com/api/v1/decide`
service, standard $0.42/M input tokens. It is not affiliated with TypeSafe AI; its API key
and accounting are separate. Only use an approved key for that destination and synthetic
observations accepted for third-party transmission. Hosted usage is validated and conservatively
charged with a micro-dollar rounding allowance. The same 500 JPY ledger applies.

Use `--mode sequential` for the same two questions in separate calls. `batched` sends both
questions together. Do not infer a performance result from fixture plumbing or compare unequal
question sets as if batching were the only change.

## Sources and reuse

Independent implementation inspired by Page injection in
[jkudish/jev-browser](https://github.com/jkudish/jev-browser), checklist execution in
[cooper667/jev-playwright](https://github.com/cooper667/jev-playwright), agent handoff in
[MahmoudAdelbghany/jev-browser](https://github.com/MahmoudAdelbghany/jev-browser), and snapshot/guard
ideas in [jev-ultrafast](https://github.com/browser-use/jev-ultrafast). No upstream code was copied.
Model limitations and pricing: [official models](https://docs.typesafe.ai/models),
[independent hosted API](https://jevtypesafeai.com/docs).

## Label experiment

`--labels native` keeps the fixture's Japanese labels. `--labels normalized` uses exact trusted
selectors with predeclared English aliases for the same controls. Compare both without changing
the 0.9 confidence floor; a handoff is not a successful goal. The fixture runs every goal so
failed earlier decisions do not hide later attempts, while `Session.checklist` still stops at
the first unverified goal. This is a local integration/quality experiment, not staging adoption.

An independent goal checker never clears an uncertain-write fence. After the wrapper has reconciled its durable journal and the original request has terminated, close the old browser context and start a fresh Page; replacing only the Session cannot reopen writes. Budget handles become unusable when their lock owner closes.

Session origin and DOM scope are fixed. Changing either adapter field blocks operations; create a new Session for a newly authorized scope. The adapter context callback must retain its original principal and resource authority for the Session lifetime, rather than changing its expected identity dynamically. Context checks also reject navigation occurring during asynchronous identity checks.
