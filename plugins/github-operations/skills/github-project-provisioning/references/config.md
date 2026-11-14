# configの契約

JSONで書く。意味のある名前を保存し、GraphQLのnode IDやoptionのIDは保存しない。

```json
{
  "version": 1,
  "host": "github.com",
  "owner": "example-org",
  "repositories": ["primary-repository"],
  "default_repository": "primary-repository",
  "project": {
    "title": "Product Development",
    "visibility": "PRIVATE",
    "short_description": "Shared engineering work tracking",
    "readme": "How this project is used",
    "template": {
      "owner": "template-owner",
      "title": "Product Development Template"
    },
    "status_field": "Status",
    "inbox_option": "Inbox",
    "priority_field": "Priority",
    "contract": {
      "statuses": ["Inbox", "Ready", "In Progress", "In Review", "Done"],
      "priorities": ["P0: now", "P1: next", "P2: later"],
      "views": [
        {
          "name": "Board",
          "layout": "BOARD_LAYOUT",
          "fields": ["Title", "Assignees", "Status", "Linked pull requests", "Sub-issues progress"],
          "vertical_group_by": ["Status"]
        },
        {
          "name": "Table",
          "layout": "TABLE_LAYOUT",
          "filter": "-status:Done",
          "fields": ["Title", "Assignees", "Status", "Repository", "Priority"]
        },
        {
          "name": "Roadmap",
          "layout": "ROADMAP_LAYOUT",
          "fields": ["Title", "Assignees", "Status", "Linked pull requests", "Sub-issues progress"]
        }
      ],
      "workflows": [
        {"name": "Item added to project", "enabled": true, "set_status": "Inbox"},
        {"name": "Pull request linked to issue", "enabled": true, "set_status": "In Review"},
        {"name": "Code changes requested", "enabled": true, "set_status": "In Progress"},
        {"name": "Pull request merged", "enabled": true, "set_status": "Done"},
        {"name": "Item closed", "enabled": true, "set_status": "Done"},
        {"name": "Item reopened", "enabled": true, "set_status": "In Progress"},
        {"name": "Auto-add sub-issues to project", "enabled": false},
        {"name": "Auto-close issue", "enabled": false}
      ]
    }
  }
}
```

`project.template` は任意。省いていて、対象のProjectが存在しない場合、planは別のProjectをcopyせず、契約から新しいProjectをbootstrapする。bootstrapの契約には、望むfieldとviewを定義する。組み込みの `Status` fieldはその場で調整し、`Priority` のような独自のsingle-select fieldは、意味のあるoption名で作る。

bootstrapは、GitHub APIでfieldとviewを作り、configにあるrepositoryをlinkする。viewのgroupingと組み込みworkflowの設定は、ブラウザでの作業が要る操作として明示的に残す。公開されている変更APIでは、それらを安全に設定しきれないためである。`set_status` は組み込みworkflowの意味上の遷移先で、ブラウザでの作業が要る操作へ引き継がれる。公開APIで分かるのはworkflowの名前と有効・無効までで、設定された遷移先のstatusは分からない。planとjournalは、これらの操作を分けて表示する。

`auto_add` は任意で、指定した時だけ有効になる。repositoryのauto-addを無効のままにするなら省く。明示的に頼まれた場合は `{"default_repository_only": true}` を使い、planのworkflow数の上限の範囲で、既定のrepositoryだけを設定する。

認証情報をcommitしない。Organizationやrepositoryに固有の設定は、信頼できるローカルの置き場から明示的に渡せる。
