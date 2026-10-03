# Reviewed static scanner exceptions

The pinned static scanner reports two `TM1` findings on `fs/promises` imports of
`rm` in browser runtime tests. Both cleanup sites remove only their own unique
`mkdtemp` fixture directory in `finally`; they do not delete user directories.
The runtime and these tests received independent review before this exception.

The baseline suppresses only those two exact finding fingerprints. The runner
checks the complete source SHA-256 of every affected file before applying it.
Any edit requires fresh review and updated bindings; wildcard rule exceptions
are rejected. Reports retain suppressed findings (`--show-suppressed`). External
API use, opaque permissions, and the negative human-control test warning remain
visible and are not suppressed. This is not an assertion that the skill is safe
for arbitrary application data: its explicit provider, scope and mutation gates
still apply.
