# Issue manifest

Use a JSON file for a guarded multi-Issue plan. The manifest is embedded in the immutable plan;
apply and resume do not depend on the source file remaining present.

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

`key` is optional but recommended. It must be unique within the manifest and becomes the stable
journal entry identifier. When omitted, the one-based entry position is used.

`body`, `labels`, `assignee`, and `priority` are optional. Priority remains explicit-only. Unknown
fields are rejected. Parent/sub-Issue relationships are not supported by version 1 and must not be
silently inferred.

One plan accepts at most 100 entries to keep content-creation limits and partial-failure recovery
operationally bounded. Apply runs entries serially and stores progress after every external
mutation. Resume reuses the stored Issue and Project item instead of creating replacements.
