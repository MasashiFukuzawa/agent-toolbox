---
name: plugin-release
description: >-
  Codex向けGitマーケットプレイスで、このリポジトリのプラグインを配布・更新する。マニフェスト確認から検証、PR、同期後の反映確認まで行う。「Codexプラグインをリリースして」「Codexの配布を更新して」「Codex marketplaceを更新して」などCodex向け配布の依頼で使う。Claude Codeには対応しない。新規プラグイン作成や個人用ローカルpluginのcachebuster更新には使わない（Codexのplugin-creatorがあれば使い、なければ公式手順を確認する）。
---
# Plugin Release

このスキルは、このリポジトリのCodex向けGitマーケットプレイス配布を扱う。変更をGitHubへマージする工程と、利用者のCodexがマーケットプレイスを同期する工程は別である。片方を済ませても、もう片方が自動で完了したとは扱わない。

Claude Code向けではない。Claude Codeのplugin marketplaceを更新する依頼では使わず、Codexが利用可能な環境で実行する。

## 1. 配布対象と現在の経路を確認する

1. `git status --short --branch`、`git remote -v`、変更差分を確認し、対象ブランチと配布するプラグインを特定する。
2. `plugins/<plugin>/.codex-plugin/plugin.json` の名前・版・skills pathを確認する。`.agents/plugins/marketplace.json` はプラグイン名と相対ソースパスを登録するカタログであり、通常の版更新では変更しない。
3. Codex側のインストール先を推測しない。`codex plugin marketplace list` で marketplace名とrootを確認し、`codex plugin list --json` で対象プラグインの版、`marketplaceSource.sourceType`、sourceを確認する。JSONの階層はCLI版により異なる可能性があるため、キーの入れ子を推測せず、現在の `--help` と実際のJSON出力を読む。プラグインの`source.source`が`local`でも、親の`marketplaceSource.sourceType`が`git`ならGitマーケットプレイスである。
4. Gitマーケットプレイスならこのスキルの手順を続ける。marketplace自体がローカルsourceなら、Gitの同期コマンドや版番号だけで反映されると決めつけず、Codexの [plugin authoring / local marketplace 手順](https://developers.openai.com/plugins/build/plugins) と実際のインストール元を確認する。個人用ローカルpluginの開発・cachebuster更新には、利用可能ならCodexの`plugin-creator`スキルを使う。見つからない場合は同じ公式手順を確認し、このGit marketplace向け手順を流用しない。

## 2. リリース候補を準備する

1. 変更対象のプラグインだけを更新する。各ホストの `plugin.json` はそのホスト向けパッケージの版を表すため、ホスト間で版が異なっていてよい。共通スキルの変更を複数ホストへ出すなら各manifestの版をそれぞれ進め、片方だけの変更なら対象ホストだけを進める。別ホストにも配布する場合は、そのホストのmanifestと互換性も確認する。公開スキルの削除・別プラグインへの移動など、利用者から見た互換性を壊す変更は、1.0.0未満ではminorを上げ、このリポジトリのSemVer方針として扱う。1.0.0以降はmajorを上げる。マーケットプレイスJSONのsource pathは、プラグインを追加・削除・移動するときだけ更新する。
2. スキルの変更なら、各スキルのtrigger/eval、READMEの一覧・件数、マーケットプレイスの整合性を更新する。trigger matrixやskill descriptionを変えた場合はbaselineも再生成する。

   ```bash
   uv run python -m scripts.run_trigger_eval --output evals/results/baseline.json --deterministic
   ```

   秘密情報、利用者の個人パス、非公開運用情報を配布物へ含めない。
3. 次のリポジトリ検証を実行する。

   ```bash
   uv run ruff check .
   uv run pytest
   uv run python -m scripts.validate
   uv run python -m scripts.trigger_eval --check
   ```

   hookやshell scriptを変更した場合は、該当するshell構文検査も加える。失敗は修正し、検証していない項目を成功扱いしない。

## 3. GitHubへ公開する

1. 変更をブランチにまとめ、差分と検証結果を説明したPRを作成する。配布元はPRブランチではなく、マーケットプレイスが追跡するGit refであることを明示する。
2. 必須CIが完了して成功したこと、PRの最終差分が検証対象と一致することを確認する。
3. **マージは配布元refを書き換える外部操作である。** ユーザーがマージまで明示的に依頼している場合にだけ実行する。依頼がPR準備までなら、レビュー可能なPRを整えて停止する。
4. マージ後、PRのmerge commit（`gh pr view <PR> --json mergeCommit`）と、マーケットプレイス設定が追跡するrefを確認する。Codexのmarketplace一覧がrefを表示しない場合は、設定元でURLと明示refを確認する。ref指定がなければ配布元URLが広告する既定refを `git ls-remote --symref <marketplace-url> HEAD` で解決する。確認したrefをURLから直接fetchし、`git fetch <marketplace-url> <tracked-ref>` の後に `git merge-base --is-ancestor <merge-commit> FETCH_HEAD` が成功することを確かめる。同期済みmarketplace rootのローカル `HEAD` だけでは配布元refの確認としない。Git snapshotでない場合は、その環境が提供する更新状態とmanifestで照合する。対象コミットが配布元refに入ったと確認してから同期工程へ進む。PRを作成しただけ、またはCIが通っただけではリリース完了と報告しない。

## 4. CodexのGitマーケットプレイスを同期して確認する

利用者環境または明示的に指定されたCodex環境で、実際のマーケットプレイス名を使う。

```bash
codex plugin marketplace list
codex plugin marketplace upgrade <marketplace-name>
codex plugin list --json
```

- `marketplace upgrade`の結果にエラーがないことを確認し、`plugin list`で対象プラグインの版とsourceが想定したマーケットプレイスを指すことを確認する。
- 版表示が変わらない場合は成功と決めつけず、配布元ref、マーケットプレイスのsnapshot、プラグインmanifest、対象marketplace名を順に照合する。手動で `config.toml` やマーケットプレイスJSONを編集して回避しない。
- 同期後は新しいCodexスレッドでスキルの反映を確認する。古いスキルが見える場合は、アプリの再起動後に再確認する。
- マーケットプレイス同期は利用者環境の状態を変更する。ユーザーが配布確認を依頼していない場合、同期コマンドは実行せず、実行手順と必要な判断を伝える。

## 5. 完了報告

配布元ref/commit、プラグインのmanifest版、CI結果、マーケットプレイス同期の成否、`plugin list`で確認した版/sourceを分けて報告する。マージ済みでも同期未実施なら「公開済み・利用者環境への反映未確認」とし、同期済みでも版表示が確認できなければ未確認とする。
