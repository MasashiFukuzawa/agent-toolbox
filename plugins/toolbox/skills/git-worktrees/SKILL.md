---
name: git-worktrees
description: >-
  並列開発の git worktree を作成・同期・整理し、衝突を避ける。別セッションや複数タスクを同時進行する時に使う。「worktreeを切って」「worktreeを掃除して」「別セッションと並列で進める」を正のトリガーとし、単一branch内の通常作業や単なるbranch削除には使わない。
---
# Git Worktrees — 並列開発の標準手順

## ガードレール（必須）

1. **削除系は必ず一覧提示 → 確認**: `git worktree remove` / `branch -D` は、対象の一覧と未コミット変更・未push コミットの有無を提示し、ユーザー確認を得てから実行する（自律実行モードでも、未コミット変更が残る worktree は勝手に消さない）。例外は、autopilotのゴールを終える時の片付けである。そのゴールで作ったと記録にあり、未コミット変更も未pushコミットも無く、ブランチが統合済みのworktreeは、確認なしで消してよい
2. worktree は **`~/.claude/skills/` や設定ディレクトリ配下に作らない**。作成先は repo の隣（repo の親 directory の直下の `<repo名>-<topic>`）
3. 元 repo（main worktree）のチェックアウト状態を勝手に変えない（別ブランチ作業は必ず worktree 側で）

## Step 1: 要否判断（作る前に必ず）

worktree はファイルを分離するだけであり、別実装との意味論上の競合や二重着手を防がない。作成前に
autopilotスキルが定義する共通collaboration preflightを完了する。重複を見つけた時の扱い・記録・
人への確認をこのスキルで再定義しない。worktreeを分ければ安全という判断は禁止する。

| 状況 | 判断 |
|---|---|
| 別セッション/エージェントが同じ repo で並列作業中 | **worktree 必須** |
| 自分の作業ブランチを保持したまま別タスクに着手 | worktree 推奨 |
| 現在の作業ツリーが clean で、1タスクずつ順番に進む | **ブランチ切替で十分**（worktree 不要） |
| base からの緊急修正（現作業を中断できない） | worktree 推奨 |

迷ったら判断根拠とともにユーザーに1問だけ確認する（過去の運用で要否の指定揺れが頻発しているため）。

## Step 2: 作成

```bash
git -C <repo> fetch -q origin <base>
git -C <repo> worktree add ../<repo名>-<topic> -b <branch> origin/<base>
```

- `<base>` は作業の起点にする branch。repo の規約や autopilot の設定（`baseBranch`）が定めていればそれを使い、無ければ既定 branch を `git -C <repo> symbolic-ref --short refs/remotes/origin/HEAD` で確かめる。`main` と決めつけない
- `git -C <repo>` の相対 path は `<repo>` が基準になるので、`../<repo名>-<topic>` で repo の隣に作られる

- 命名: ディレクトリ `<repo>-<topic>`、ブランチはリポジトリの規約（feat/fix/chore + issue番号等）に従う
- 作成後の注意: **node_modules / venv は共有されない**。ビルド・lint が必要なら依存インストールから（pre-commit hook が依存を要求する repo では特に）

## Step 3: 最新の base の取り込み（並列作業中の定期同期）

```bash
git fetch origin <base>
git rebase origin/<base>   # 公開済みブランチなら merge を選ぶ
```

- コンフリクト時: 機械的に解決せず、**相手側の変更意図を `git log origin/<base> --oneline -10` で確認してから**解決する
- 別セッションが同じファイルを触っている兆候（同一ファイルの頻繁な conflict）があれば、作業分担の見直しをユーザーに提案する

## Step 4: クリーンアップ（マージ後）

1. 一覧と状態を提示: `git worktree list` + 各 worktree の `git status --porcelain` / 未pushコミット
2. ユーザー確認後:

```bash
git worktree remove <path>        # 未コミット変更があれば --force が要るが、その前に必ず退避を提案
git branch -d <branch>            # マージ済み確認込み（-D は最終手段）
git worktree prune
```

3. リモート削除済み（`[gone]`）ブランチの一括掃除は、ガードレール1と同じく一覧提示とユーザー確認を経て行う

## トラブルシューティング

- `fatal: '<branch>' is already checked out` → そのブランチは他の worktree が使用中。`git worktree list` で特定
- worktree を移動/リネームしたら `git worktree repair`
