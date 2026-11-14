---
name: plugin-release
description: >-
  このリポジトリのプラグインを、Claude CodeとCodexのGitマーケットプレイスへリリースする。版の更新・検証・PR・マージ確認から、各ホストのマーケットプレイス同期と反映確認まで行う。「プラグインをリリースして」「バージョンを上げて配布して」「インストール済みのプラグインを最新にして」などの依頼で使う。完了前の品質ゲートだけならdoneを使い、新規プラグインの作成や個人用ローカルpluginの更新には使わない。
---
# Plugin Release

このリポジトリのプラグインは、同じGit refを2つのマーケットプレイスが参照して配布される。

| ホスト | マーケットプレイス定義 | プラグインの版 |
|---|---|---|
| Claude Code | `.claude-plugin/marketplace.json` | `plugins/<plugin>/.claude-plugin/plugin.json` |
| Codex | `.agents/plugins/marketplace.json` | `plugins/<plugin>/.codex-plugin/plugin.json` |

リリースは「変更を配布元refへ入れる」と「利用者環境のマーケットプレイスを同期する」の2工程に分かれる。片方を済ませても、もう片方が完了したとは扱わない。

## 1. 配布対象を確認する

1. `git status --short --branch`、`git remote -v`、変更差分から、配布するプラグインと各ホストの対象を特定する。片方のホストのマーケットプレイスにしか載っていないプラグインもある。
2. 対象プラグインの各 `plugin.json` の名前・版を確認する。マーケットプレイスJSONはプラグイン名と相対パスを登録するカタログで、通常の版更新では変更しない。

## 2. リリース候補を準備する

1. 各ホストの `plugin.json` は、そのホスト向けパッケージの版を表す。両ホストへ出す変更なら両方を、片方だけの変更なら対象ホストだけを進める。版の上げ方はSemVerに従い、公開スキルの削除・別プラグインへの移動など利用者から見た互換性を壊す変更は、1.0.0未満ではminor、1.0.0以降はmajorを上げる。
2. マーケットプレイスJSONのパスは、プラグインを追加・削除・移動するときだけ更新する。
3. スキルを変えたなら、各スキルのevalsと、READMEの一覧・件数を合わせる。
4. `CHANGELOG.md` の先頭に、版・日付・利用者から見て変わったことを足す。互換性を壊す版には **Breaking** と書き、移行の手順（何を、どの順に）を添える。考え方や責務の境界が変わるなら `docs/design.md` も直す。

5. 次の検証をすべて通す。失敗は修正し、実行していない検証を成功扱いしない。

   ```bash
   uv run ruff check .
   uv run pytest
   uv run python -m scripts.validate
   ```

## 3. 配布元refへ入れる

1. ブランチでPRを作り、差分・版・検証結果を書く。配布元はPRブランチではなく、マーケットプレイスが追跡するref（通常はデフォルトブランチ）である。
2. 必須CIの成功を確認する。
3. **マージは配布元refを書き換える外部操作である。** ユーザーがマージまで依頼したときだけ実行する。PR準備までの依頼なら、レビュー可能なPRを整えて止める。
4. マージ後、`gh pr view <PR> --json mergeCommit` でmerge commitを取り、配布元refに入ったことを確かめる。

   ```bash
   git fetch origin <tracked-ref>
   git merge-base --is-ancestor <merge-commit> FETCH_HEAD
   ```

   PRを作っただけ、CIが通っただけではリリース完了と報告しない。

## 4. 利用者環境へ同期する

同期は利用者環境の状態を変える。ユーザーが反映まで依頼していなければ、手順だけ伝えて実行しない。マーケットプレイス名は推測せず、一覧で実名を確かめてから使う。

**Claude Code**

```bash
claude plugin marketplace list --json
claude plugin marketplace update <marketplace>
claude plugin update <plugin>@<marketplace>
claude plugin list --json
```

`plugin list` で対象の版が上がったことを確認する。反映には新しいセッションが要るため、再起動をユーザーに伝える。

**Codex**

```bash
codex plugin marketplace list
codex plugin marketplace upgrade <marketplace>
codex plugin list --json
```

`plugin list` で対象の版と `marketplaceSource.sourceType` が `git` であることを確認する。プラグイン側の `source.source` が `local` でも、親のマーケットプレイスが `git` ならGit配布である。反映は新しいスレッドで確かめる。

どちらのホストでも、版が変わらないときは成功と決めつけず、配布元ref・マーケットプレイスのsnapshot・manifest・マーケットプレイス名を順に照合する。設定ファイルやキャッシュを手で書き換えて回避しない。

## 5. 完了報告

配布元のref/commit、ホストごとのmanifest版、CI結果、ホストごとの同期結果と `plugin list` で確認した版を分けて報告する。マージ済みでも同期していなければ「公開済み・利用者環境への反映は未確認」とする。
