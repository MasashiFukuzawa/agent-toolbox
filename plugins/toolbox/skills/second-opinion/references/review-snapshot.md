# スナップショット（固定した写し）の作り方

レビューや動作確認の対象を不変オブジェクトとして固定し、待ち時間中に呼び出し元がリポジトリを自由に扱えるようにする。実ツリーと index には一切触れない。

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
- 汚染の確認（ガードレール2）は、メインツリーではなくこの worktree 側で行う。メインツリーは並行作業で当然変化するため、そちらを見ると恒常的に偽陽性になる

## 動作確認で使う場合

- 作ったworktreeを作業rootにして起動する。第三者が書き込めるのは、このworktreeの中だけにする（起動の形はproviderごとの参照ファイル）。
- `.gitignore`されたファイルは含まれないので、導入済みの依存やローカル設定は写しに無い。依存の導入は写しの中で行わせる。秘密の値を写しへコピーしない。
- 第三者が写しの中で作ったファイルや変更は成果物ではない。結果の報告を回収したら、下の後始末で写しごと捨てる。

## 後始末

レビュー結果の回収・報告が完了し、session recoveryが不要になった後にworktreeを除去する。割り込み中や未回収の状態では、resume先が同じ対象を再読取できるようにworktreeとsnapshot commitを保持する。復旧不能を報告して回収を断念した時点、またはユーザーが新規レビューを選んだ時点でも不要になる。残すとworktreeが溜まる。

```bash
git worktree remove <作成したパス>
```

snapshot commit はどこからも参照されなくなり、通常の `git gc` で回収される。
