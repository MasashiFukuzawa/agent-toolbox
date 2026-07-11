# DB Integration Testing

## 基本方針

管理下にあるDBは、可能な限り実物のDBMSで統合テストする。DBとの通信は実装詳細であり、RepositoryやORM呼び出しをモックしても、永続化・制約・transaction・migrationの退行保護は得られない。

ただし、既存repoに明確なDBテスト基盤がある場合はそれに従う。新しい基盤を勝手に導入しない。

## 実装前に確認すること

- 本番と同種のDBMSをテストで使えるか。
- migration管理の方法。
- schemaとreference dataがソース管理されているか。
- テストDBの起動方法: local service、Docker、Testcontainers、compose、CI service。
- transaction管理の方針。
- テストデータのcleanup方針。
- 並列実行の可否。
- 既存のfactory、seed、fixture、repository helper。

## in-memory DB の扱い

SQLiteなどのin-memory DBで本番DBの代替をすることは原則避ける。SQL方言、制約、transaction、index、locking、ORM挙動が異なるため、退行保護が弱く、偽陽性/偽陰性を生みやすい。

例外として許容できるのは、repoが既にそのリスクを受け入れており、対象がDB固有挙動に依存しない単純な読み書きで、より忠実なテストがコストに見合わない場合である。その場合も「本番DBの代替ではなく低忠実度のテスト」と明記する。

## データライフサイクル

推奨:

- 各テストの開始時に対象データを掃除する。
- テストごとに一意な識別子を使う。
- reference dataはmigration/schemaの一部として扱う。
- Assertでは、Arrangeで使ったオブジェクトを再利用せず、DBから再取得して確認する。

注意:

- テスト終了時cleanupだけに頼ると、失敗時に汚れが残る。
- transaction rollbackは速いが、本番のtransaction境界と異なる場合がある。
- 並列実行では共有状態、sequence、unique constraint、clockに注意する。

## 何を直接テストしないか

- Repositoryだけを単独でテストしない。多くの場合、統合テストのシナリオ内で間接的に検証する。
- ORM mapperだけをテストしない。DBを含むシナリオで検証する。
- Event dispatcherだけを大量モックで単独テストしない。外部境界への観察可能な効果を検証する。
- 単純な読み込みは、重要または複雑なqueryでない限りテストしない。

## 統合テストの形

1. Arrange: DBを既知状態にする。必要なら開始時cleanupを行う。
2. Act: 公開API、アプリケーションサービス、コントローラ相当の入口を1回呼ぶ。
3. Assert: DBから再取得した状態、または管理下にない境界への通信を検証する。

外部通知、メール、決済、メッセージバスなど管理下にない依存は、所有アダプタのスパイ/モックに置き換える。DBは管理下依存として実物を使う。
