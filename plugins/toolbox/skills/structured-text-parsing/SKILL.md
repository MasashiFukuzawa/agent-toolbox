---
name: structured-text-parsing
description: >-
  ログ、CSV、JSON、コードなど予測可能な構造化テキストを決定的に解析する。抽出や変換を求められた時に使う。曖昧な自然言語理解には使わない。「JSONから抽出」「ログを集計」を正のトリガーとし、入力形式が定義できず意味解釈そのものが必要な依頼には使わない。
---
# Structured text parsing

## 原則

構造が定義できる入力は LLM に全文を渡さず、parser、JSONPath、CSV reader、正規表現など決定的な手段で処理する。LLM は schema の発見や曖昧な分類に限定する。

## 手順

1. 入力形式、encoding、区切り、欠損値、複数行の有無を確認する。
2. 既存 parser を優先し、正規表現は単純で局所的なパターンに限定する。
3. 正常例、境界値、不正入力を fixture にして parser を検証する。
4. 件数、skip 数、parse error を集計し、silent failure を避ける。
5. 個人情報や secret を含む行は出力・ログ・プロンプトへ流さない。

入力構造が安定しない場合は、まず小さな sample から schema を定義する。自由文の意味判断が本質なら、決定的解析だけで解けると装わない。
