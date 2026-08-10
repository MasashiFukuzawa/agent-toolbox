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

`project.template` is optional. When it is omitted and the target Project does not exist, the plan bootstraps a new Project from the contract instead of copying another Project. A bootstrap contract must define the desired fields and views. The built-in `Status` field is reconciled in place; custom single-select fields such as `Priority` are created with semantic option names.

The bootstrap path creates fields and views through the GitHub API and links the configured repositories. View grouping and built-in workflow settings remain explicit browser-required operations because the supported public mutations do not provide a complete safe configuration surface for them. `set_status` is the semantic target for a built-in workflow and is carried into the browser-required operation; the public API exposes the workflow name and enabled flag, but not the configured target status. The plan and journal must display these operations separately.

`auto_add` is optional and opt-in. Omit it to leave repository auto-add disabled. When explicitly requested, use `{"default_repository_only": true}` to configure only the default repository, subject to the plan's workflow limit.

Do not commit credentials. Organization- or repository-specific configuration can be passed explicitly from any trusted local source.
