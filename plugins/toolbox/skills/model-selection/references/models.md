# モデル・effortの初期候補

整理日: 2026-11-10。既存review skillの運用値を集約したもの。独立した性能ベンチマークや価格比較としては未検証。利用可能性は起動ホストで確認する。

| Provider | モデルID | effort初期値 | 主な初期候補用途 |
|---|---|---|---|
| OpenAI | `gpt-6.2-sol` | `low` | 設計済みの実装、範囲の明確な調査・差分レビュー。力の入れ具合はeffortで調整する（下記） |
| OpenAI | `gpt-6.2-astra` | `low` | ゴールを進めるセッション、特に難しい横断判断。明示指定または選択権限が必要 |
| Anthropic | `claude-sonnet-5-5` | `medium` | 設計済みの実装、範囲の明確な調査・差分レビュー |
| Anthropic | `claude-opus-5-5` | `low` | 設計判断、高い不確実性、複雑な実装、ゴールを進めるセッション |
| Anthropic | `claude-fable-5-2` | `low` | 特に難しい長時間課題。明示指定または選択権限が必要 |

providerのみ指定された通常レビューは、そのproviderの表の先頭を初期候補とする。設計そのものが対象、不確実性が高い、拠り所の設計がない場合、OpenAIは下記のeffort段階を、Anthropicは次の候補を検討する。ゴールを進めるセッションに必ず特定モデルを要求する表ではない。

モデル指定はfamily/tierを尊重し、版付き指定もこの表の最新の同系列IDへ解決する（既存review skillの方針を維持）。指定版と異なる場合は起動前に置換を伝える。系列の変更はしない。表にない系列や利用不能なIDは推測せず確認する。ユーザーが旧版への固定自体を要件として明示した場合は、この既定との衝突を説明して解決してから起動する。

`sol` と `astra` はそれぞれ `gpt-6.2-sol` と `gpt-6.2-astra` に解決する。初期値は両方とも `low` とする。`luna` は候補外の系列として扱い、指定されたら確認する。

OpenAIのAPI変更履歴（2026-11-17）で両モデルのIDを確認した。Codexのモデル一覧（2026-11-18確認）では、両モデルとも `low` / `medium` / `high` / `xhigh` / `max` / `ultra` に対応する。利用するホストで選べるeffortを起動前に確かめる。<https://developers.openai.com/api/docs/changelog>

## OpenAI: effortによるレビュー強度

OpenAIの通常レビュー・調査は `gpt-6.2-sol` から始め、必要に応じてeffortを上げる。通常レビューで Sol から `gpt-6.2-astra` への自動切り替えを検討するのは、effortを上げても横断判断が足りず、Astraを含む選択権限がある場合に限る。

| effort | 使う場面 |
|---|---|
| `low` | 既定。設計済みの差分レビュー、範囲の明確な実装・調査 |
| `medium` | 設計判断そのものが対象、不確実性が高い、拠り所の設計がない |
| `high` | 不可逆操作・セキュリティ境界・広範囲への影響など、見落としの影響が大きく理由を記録できる場合 |
| `xhigh` / `max` / `ultra` | 明示指定または明示的な選択権限がある場合のみ |

Anthropicのリリース発表（2026-09-28）でSonnet 5.5のAPI ID `claude-sonnet-5-5` と提供開始を確認: <https://www.anthropic.com/claude-sonnet-5-5>.

Sonnet 5.5でthinkingを無効にして使う設定がある場合は、Sonnet 5の`disabled`ではなく`between_tools`への移行が必要。`between_tools`は`low`/`medium`/`high`で使え、`xhigh`/`max`ではエラーになるため、該当設定とeffortを利用ホスト側で確認する: <https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide>.

Anthropicのリリース発表（2026-11-09）とモデルページでFable 5.2のAPI ID `claude-fable-5-2`（aliasも同一）、Claude APIと主要クラウドでの提供、対応effort `low`/`medium`/`high`（API既定）/`xhigh`/`max`を確認: <https://www.anthropic.com/claude-fable-and-mythos-5-2>, <https://platform.claude.com/docs/en/models/fable-5-2/overview>. `claude-fable-5-1`はこの版で置き換え、`fable`指定は`claude-fable-5-2`へ解決する。API既定の`high`ではなく`low`を初期値とする。同時発表のMythos 5.2は利用組織が限定されるため候補に含めない。

Fable 5.2はadaptive thinkingが常時有効で、thinkingの無効化や`budget_tokens`指定はエラーになる。advisor toolの組合せ制限など5.1からの非互換もあるため、該当設定を利用ホスト側で確認する。zero data retentionはAnthropicの明示許可がない限り使えないため、データ保持の制約がある環境では起動前に確認する: <https://platform.claude.com/docs/en/models/fable-5-2/migration-guide>.

初期値で浅い場合、対象を絞ったうえで上位候補を検討する。上位モデルでは必要に応じてeffortを一段上げる。`high`は難度・影響に見合う理由がある場合、`xhigh`以上は明示指定または明示的な選択権限がある場合に限る。対応しないeffortは黙って降格しない。

能力・時間・費用はタスクとホストに依存する。特定モデルのeffortが常に他モデルより高精度／低精度だとは断定しない。新しいモデルを追加する際はID、対応effort、用途、確認日と根拠をこのファイルで更新する。
