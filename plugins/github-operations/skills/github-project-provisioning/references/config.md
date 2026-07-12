# Configuration contract

Use JSON. Store semantic names, never GraphQL node IDs or option IDs.

```json
{
  "version": 1,
  "host": "github.com",
  "owner": "example-org",
  "repositories": ["primary-repository"],
  "default_repository": "primary-repository",
  "project": {
    "title": "Product Development",
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
        {"name": "Item added to project", "enabled": true},
        {"name": "Pull request linked to issue", "enabled": true},
        {"name": "Code changes requested", "enabled": true},
        {"name": "Pull request merged", "enabled": true},
        {"name": "Item closed", "enabled": true},
        {"name": "Item reopened", "enabled": true},
        {"name": "Auto-add sub-issues to project", "enabled": false},
        {"name": "Auto-close issue", "enabled": false}
      ]
    }
  },
  "auto_add": {
    "default_repository_only": true
  }
}
```

Do not commit credentials. Organization- or repository-specific configuration can be passed explicitly from any trusted local source.
