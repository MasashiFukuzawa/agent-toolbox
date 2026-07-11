---
name: git-worktrees
description: >-
  並列開発の git worktree を作成・同期・整理し、衝突を避ける。別セッションや複数タスクを同時進行する時に使う。通常の単一ブランチ作業には使わない。「worktreeを切って」「別セッションと並列で進める」を正のトリガーとし、単一branch内の通常作業や単なるbranch削除には使わない。
---
# Worktree Flow — 並列開発の標準手順

## ガードレール（必須）

1. **削除系は必ず一覧提示 → 確認**: `git worktree remove` / `branch -D` は、対象の一覧と未コミット変更・未push コミットの有無を提示し、ユーザー確認を得てから実行する（自律実行モードでも、未コミット変更が残る worktree は勝手に消さない）
2. worktree は **`~/.claude/skills/` や設定ディレクトリ配下に作らない**。作成先は repo の隣（例: `$HOME/projects/<repo>-<topic>`）
3. 元 repo（main worktree）のチェックアウト状態を勝手に変えない（別ブランチ作業は必ず worktree 側で）

## Step 1: 要否判断（作る前に必ず）

| 状況 | 判断 |
|---|---|
| 別セッション/エージェントが同じ repo で並列作業中 | **worktree 必須** |
| 自分の作業ブランチを保持したまま別タスクに着手 | worktree 推奨 |
| 現在の作業ツリーが clean で、1タスクずつ順番に進む | **ブランチ切替で十分**（worktree 不要） |
| main からの緊急修正（現作業を中断できない） | worktree 推奨 |

迷ったら判断根拠とともにユーザーに1問だけ確認する（過去の運用で要否の指定揺れが頻発しているため）。

## Step 2: 作成

```bash
git -C <repo> fetch -q origin main
git -C <repo> worktree add <repo>-<topic> -b <branch> origin/main
```

- 命名: ディレクトリ `<repo>-<topic>`、ブランチはリポジトリの規約（feat/fix/chore + issue番号等）に従う
- 作成後の注意: **node_modules / venv は共有されない**。ビルド・lint が必要なら依存インストールから（pre-commit hook が依存を要求する repo では特に）

## Step 3: 最新 main の取り込み（並列作業中の定期同期）

```bash
git fetch origin main
git rebase origin/main   # 公開済みブランチなら merge を選ぶ
```

- コンフリクト時: 機械的に解決せず、**相手側の変更意図を `git log origin/main --oneline -10` で確認してから**解決する
- 別セッションが同じファイルを触っている兆候（同一ファイルの頻繁な conflict）があれば、作業分担の見直しをユーザーに提案する

## Step 4: クリーンアップ（マージ後）

1. 一覧と状態を提示: `git worktree list` + 各 worktree の `git status --porcelain` / 未pushコミット
2. ユーザー確認後:

```bash
git worktree remove <path>        # 未コミット変更があれば --force が要るが、その前に必ず退避を提案
git branch -d <branch>            # マージ済み確認込み（-D は最終手段）
git worktree prune
```

3. リモート削除済みブランチの一括掃除は `専用のリモートブランチ整理手順` に委譲

## トラブルシューティング

- `fatal: '<branch>' is already checked out` → そのブランチは他の worktree が使用中。`git worktree list` で特定
- worktree を移動/リネームしたら `git worktree repair`
- 「元repoが dirty で Stop hook が誤発火」→ done ゲートは worktree ごとの署名検証なので、**作業した worktree 内で** /done を実行する
