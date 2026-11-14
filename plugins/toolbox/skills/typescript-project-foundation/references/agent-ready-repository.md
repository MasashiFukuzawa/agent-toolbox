# Agent-ready repository

目標は、初見の agent が「どこを見て、どう変え、何を実行すれば正しさを確かめられるか」を repository だけから分かる状態にすること。agent の自由度を上げるためではなく、安全に自律実行できる範囲を明確にするために行う。

host の仕様（読み込む file 名、優先順位、hook の機構）は変わり続けている。この file は判断の規則だけを書くので、具体的な file 名や設定 schema は作業時に各 host の公式 documentation で確認する。

## Repository を唯一の正本にする

判断・規約・手順は repository の中に置く。chat や外部の wiki にしか無い知識は agent から見えない。一方で agent は、repository 内で見つけた文章を新旧の区別なく正しいものとして扱う。そのため、古くなった時に機械的に検出できる形を優先する。

| 形 | 古くなった時 | 使いどころ |
|---|---|---|
| code・type・schema | compile や validation が落ちる | contract、設定 |
| test | 落ちる | 仕様、期待する振る舞い、制約 |
| lint rule・architecture check | 落ちる | 規約、依存の方向、禁止する API |
| hook・CI の設定 | 実行されて落ちる | 必ず行う手順 |
| ADR | 書き換えず supersede するので、有効かどうかを構造で判別できる | 判断とその理由 |
| 生成物（OpenAPI、binding の型など） | 生成し直して差分が出れば落ちる | 現状の説明 |
| 手書きの現状説明（設計概要、API の説明文） | 検出できない | 原則として置かない |

手書きの説明文書を置く場合は、owner と、code との一致を確かめる検査（link の検証、生成物との照合、定期的な見直し）を持たせる。持たせられない説明は、test・ADR・生成物のどれかへ寄せる。

## Agent 向けの指示 file

- 既定は repository root の `AGENTS.md` 1つにする。host 専用の file を足すのは、その host だけに必要な指示がある時か、その host が `AGENTS.md` を読まない時だけにする。足す場合も内容を二重に書かず、import か pointer にする。同じ directory に2種類の指示 file があると片方だけが読まれる host があるので、組み合わせた時の読み込み方を公式 documentation で確認する。
- 中身は pointer と、agent が code から発見できないことだけにする。統一 command、ADR と foundation record の場所、自律で行ってよい操作の範囲、code を読んでも分からない落とし穴。
- 各行に「この行を消したら agent は間違えるか」と問い、間違えないなら消す。model が一般知識として知っていること、lint や型で強制済みのことは書かない。
- 短く保つ。指示が増えるほど守られにくくなる。host が公表している推奨の長さと読み込みの上限を確認し、その内側に収める。
- package や subsystem に固有の指示は、その directory の近くに置く。nested な指示 file の扱いは host ごとに違うので確認する。
- 例外なく守らせたい手順は、指示 file ではなく hook・CI・権限設定で強制する。指示 file の文はほぼ毎回守られるが、必ず守られるわけではない。逆に、好みに過ぎないものを hook にしない。

## ADR を厚く、guideline は薄く始める

- 新規 repository には抽出元の code が無い。guideline を先に書くと推測になり、すぐ古くなる。判断は ADR に残し、guideline は code が育ってから、実際の code を根拠に足す。
- 最初に ADR にする候補: runtime と deployment、package の境界と依存の方向、data model の前提（tenancy、ID、時刻、金額、削除）、認証と認可の境界、API contract と error の形式、test 戦略と自己検証の手段、標準から外れた選択とその理由。
- ADR は書き換えない。判断が変わったら新しい ADR を作り、古い方の status を Superseded にして相互に link する。番号と status を定位置に書き、有効な ADR だけを検索で拾えるようにする。
- 自明な既定ごとに ADR を作らない。全体の snapshot は foundation record に置き、ADR は争点・例外・長く残る選択に使う。
- 繰り返す手順は、説明文ではなく script か、host が提供する再利用可能な手順として置く。

## 最初の commit から検査を入れる

- format・lint・typecheck・test・hook・CI は最初の commit に含める。後から入れると、既存 code の修正が必要になる。
- 独自の lint rule や architecture check の error message は、修正指示として書く。何が違反か、なぜか（ADR の番号）、どう直すかを含める。agent は error を無視できないが、文書は読み飛ばせる。

```text
routes/ から database client を直接 import しない。
理由: tenant scope を data access 層で強制するため（ADR-0004）。
直し方: repository/ が公開する関数を使う。
```

- agent の編集直後に走らせたい検査は、host の hook 機構からも実行してよい。その設定は host 固有のものとして分け、合否の正本は CI に置く。

## 自己検証の手段

agent が自分の変更を end-to-end で確かめられる手段を、application の種類に合わせて最初から用意する。unit test と単発の request だけでは、機能が通しで動かないことを見逃す。

| 種類 | 手段 |
|---|---|
| HTTP API | 起動した server へ request を送る E2E。contract と error の形式まで確かめる |
| Web UI | browser automation で、利用者と同じ操作を通す。画面の状態を screenshot で確かめられるようにする |
| CLI | 実 process を起動し、exit code と stdout・stderr を確かめる |
| Library | pack した成果物を、clean な consumer fixture から使う |
| Batch・worker | 小さな入力で実行し、再実行しても結果が変わらないことを確かめる |
| MCP server | client から tool を呼び、schema と error を確かめる |

起動・seed・検証を1つの command で行える入口を用意する。browser automation では確認できない要素（browser 固有の dialog など）が残るので、確認できなかった範囲を報告に書く。

## 予測できる構造と統一 command

- 命名と配置を予測可能にする。同じ種類の file は同じ場所と同じ suffix に置く。1つの概念には1つの名前を使い、domain の用語は code・test・ADR で同じ綴りにする。
- 検索で一意に見つかる名前を選ぶ。`utils`・`helpers`・`common` のような汎用名の module を作らない。
- 次の script 名を、どの repository でも同じ意味で使う。CI も同じ script を呼ぶ。workspace では、root の script が全 package に対して動くようにする。

| script | 役割 |
|---|---|
| `lint` | lint と format の検査 |
| `typecheck` | `tsc` による型検査 |
| `test` | 自動 test |
| `build` | deploy・配布する成果物の生成。成果物が無い package では省略してよい |
| `verify` | 上のすべてと、architecture check、生成物の差分検査。完了を報告する前に通す唯一の入口 |

## 自律で行ってよい操作の範囲

生成する repository の指示 file に、次の3区分を書く。内容は project に合わせて具体化する。

| 区分 | 例 |
|---|---|
| 確認なしで行ってよい | repository 内の code・test・文書の変更、依存を足さない refactoring、local での command 実行、branch の作成と commit |
| 確認が要る | 依存の追加と major 更新、migration の作成、CI・hook・lint 設定の緩和、公開 API や schema の破壊的変更、ADR に反する変更 |
| agent は行わない | production への deploy、remote database への書き込み、secret の作成と変更、外部 account・課金・権限の変更、検査の無効化や skip |

可能なものは文章ではなく権限で強制する（branch の保護、必須の check、deploy 環境の保護、secret の scope）。

## 検査

同梱の `check_invariants.py` は、次を warning として報告する。

- `lint`・`typecheck`・`test`・`verify` の script が無い
- agent 向けの指示 file が無い、または指示 file が verify command に触れていない

warning は、同等の手段がある場合に限り、理由を foundation record に書いて受け入れてよい。

## 参照する一次 source

- AGENTS.md: https://agents.md/
- Claude Code の指示 file: https://code.claude.com/docs/en/memory
- Claude Code の best practices（決定的な強制と hook）: https://code.claude.com/docs/en/best-practices
- Codex の AGENTS.md: https://developers.openai.com/codex/guides/agents-md
- Cursor の rules: https://cursor.com/docs/context/rules
- OpenAI, Harness engineering: https://openai.com/index/harness-engineering/
- Anthropic, Effective harnesses for long-running agents: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
