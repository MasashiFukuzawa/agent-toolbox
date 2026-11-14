# Issueのmanifest

複数のIssueを、確認付きの1つのplanにまとめる時はJSONファイルを使う。manifestは不変のplanに埋め込まれるので、applyとresumeは、元のファイルが残っていることに依存しない。

```json
{
  "version": 1,
  "issues": [
    {
      "key": "api-timeout",
      "repo": "owner/repository",
      "title": "Handle upstream timeouts",
      "body": "Describe the expected behavior and acceptance criteria.",
      "labels": ["bug"],
      "assignee": "octocat",
      "priority": "P1: next"
    }
  ]
}
```

`key` は任意だが、付けることを勧める。manifestの中で一意でなければならず、journalのentryを指す安定した識別子になる。省いた場合は、1から始まるentryの位置を使う。

`body`、`labels`、`assignee`、`priority` は任意。Priorityは、明示された場合にだけ設定する。未知のfieldは拒否する。親子（sub-Issue）の関係はversion 1では扱わない。暗黙に推測もしない。

1つのplanが受け付けるのは100 entryまで。内容作成の制限と、途中で失敗した時の復旧を、運用できる範囲に収めるためである。applyはentryを直列に実行し、外部への変更のたびに進み具合を保存する。resumeは、保存済みのIssueとProject itemを再利用し、代わりを作らない。
