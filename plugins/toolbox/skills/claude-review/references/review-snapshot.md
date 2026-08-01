# レビュー用スナップショットの作り方

レビュー対象を不変オブジェクトとして固定し、待ち時間中に呼び出し元がリポジトリを自由に扱えるようにする。実ツリーと index には一切触れない。

## 手順

```bash
IDX=$(git rev-parse --git-path index)     # linked worktree でも正しい index を指す
TMPIDX=$(mktemp)
cp "$IDX" "$TMPIDX"
GIT_INDEX_FILE="$TMPIDX" git add -A       # untracked を含めて現在の状態を固定する
TREE=$(GIT_INDEX_FILE="$TMPIDX" git write-tree)
SNAP=$(git commit-tree "$TREE" -p HEAD -m "review snapshot")
git -c core.hooksPath=/dev/null worktree add --detach <リポジトリ外のパス> "$SNAP"
```

レビュアーには作成した worktree のパスを渡し、依頼文では対象を **`HEAD~1..HEAD` の差分**と伝える。`SNAP` の親が元の `HEAD` なので、これがそのまま未コミット差分になる。

## 性質

- 元のツリーと index は変化しない。`git status --porcelain` は前後で同一
- untracked を含む。**`.gitignore` されたファイルは含まれない**ので、依頼文に明記する
- detached SHA なので、待ち時間中に `git fetch` や branch 操作をしても対象は動かない
- `core.hooksPath=/dev/null` は、`post-checkout` hook がリポジトリルートへ書き込む構成で元のツリーに untracked ファイルが生まれるのを防ぐ
- 汚染チェック（ガードレール1）は、メインツリーではなくこの worktree 側で行う。メインツリーは並行作業で当然変化するため、そちらを見ると恒常的に偽陽性になる

## 後始末

レビュー完了後に worktree を除去する。残すと worktree が溜まる。

```bash
git worktree remove <作成したパス>
```

snapshot commit はどこからも参照されなくなり、通常の `git gc` で回収される。
