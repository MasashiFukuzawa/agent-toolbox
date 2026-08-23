# Issue policy

- Treat the Issue as the task's source of truth and the Project as the cross-repository priority queue.
- Resolve owner, repository, Project, fields, options, and labels from current GitHub state.
- Preserve repository-specific language and templates from its instructions.
- Generate a stable operation fingerprint internally and add it to the body. Never accept a caller-selected fingerprint, and do not rely on search indexing alone for idempotency.
- Record the created Issue URL before attempting Project registration.
- A write with an unknown result must be followed by a read and reconciliation, not an unconditional retry.
