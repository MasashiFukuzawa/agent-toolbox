# モデル・effortの初期候補

整理日: 2026-09-29。既存review skillの運用値を集約したもの。独立した性能ベンチマークや価格比較としては未検証。利用可能性は起動ホストで確認する。

| Provider | モデルID | effort初期値 | 主な初期候補用途 |
|---|---|---|---|
| OpenAI | `gpt-6-luna` | `high` | 設計済みの実装、範囲の明確な調査・差分レビュー |
| OpenAI | `gpt-6-sol` | `medium` | 設計判断、高い不確実性、複雑な実装 |
| OpenAI | `gpt-6-astra` | `low` | controller、特に難しい横断判断。明示指定または選択権限が必要 |
| Anthropic | `claude-sonnet-5-5` | `medium` | 設計済みの実装、範囲の明確な調査・差分レビュー |
| Anthropic | `claude-opus-5-5` | `low` | 設計判断、高い不確実性、複雑な実装・controller |
| Anthropic | `claude-fable-5-1` | `low` | 特に難しい長時間課題。明示指定または選択権限が必要 |

providerのみ指定された通常レビューは、そのproviderの表の先頭を初期候補とする。設計そのものが対象、不確実性が高い、拠り所の設計がない場合は次の候補を検討する。controllerに必ず特定モデルを要求する表ではない。

モデル指定はfamily/tierを尊重し、版付き指定もこの表の最新の同系列IDへ解決する（既存review skillの方針を維持）。指定版と異なる場合は起動前に置換を伝える。系列の変更はしない。表にない系列や利用不能なIDは推測せず確認する。ユーザーが旧版への固定自体を要件として明示した場合は、この既定との衝突を説明して解決してから起動する。

Anthropicのリリース発表（2026-09-28）でSonnet 5.5のAPI ID `claude-sonnet-5-5` と提供開始を確認: <https://www.anthropic.com/claude-sonnet-5-5>.

Sonnet 5.5でthinkingを無効にして使う設定がある場合は、Sonnet 5の`disabled`ではなく`between_tools`への移行が必要。`between_tools`は`low`/`medium`/`high`で使え、`xhigh`/`max`ではエラーになるため、該当設定とeffortを利用ホスト側で確認する: <https://platform.claude.com/docs/en/models/sonnet-5-5/migration-guide>.

初期値で浅い場合、対象を絞ったうえで上位候補を検討する。上位モデルでは必要に応じてeffortを一段上げる。`high`は難度・影響に見合う理由がある場合、`xhigh`以上は明示指定または明示的な選択権限がある場合に限る。対応しないeffortは黙って降格しない。

能力・時間・費用はタスクとホストに依存する。特定モデルのeffortが常に他モデルより高精度／低精度だとは断定しない。新しいモデルを追加する際はID、対応effort、用途、確認日と根拠をこのファイルで更新する。
