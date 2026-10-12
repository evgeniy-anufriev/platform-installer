# EXEC-GENSTATE-01 — persistent machine-owned generated state

The Installer keeps portable desired state and Execution Node generated state
separate. A production execution never writes generated state into the
ephemeral archive/workspace made for an individual run.

```text
portable project → immutable archived copy → run workspace (ephemeral)

Execution Node state root
  projects/<projectIdentity>/generated/platform-state.yml (persistent)
```

`projectIdentity` is the stable managed project ID, not a run ID. Therefore a
new run receives the same generated-state file and may genuinely be
idempotent. Its controller derives the fixed path itself and injects only the
private `platform_generated_state_path` runtime projection. Service playbooks
such as BIND do not know the physical Execution Node root.

The controller accepts only a bounded project ID, creates and verifies the
fixed directories with owner-only permissions, and rejects a symlink,
non-regular file, unsafe permissions or a file over 1 MiB. The BIND lifecycle
binds a loaded state envelope to the same project ID, validates it against the
published generated-state schema before use, validates the next state before
publishing, and writes it atomically. The active-controller per-project run
lock remains the concurrency boundary.

This storage is machine-owned: it is not part of `project.yml`, inventory,
plan, result, event stream, export, or a new desired-state database. Ordinary
standalone Ansible remains compatible through its documented explicit
`platform_generated_state_path` variable; only Installer-managed execution
uses the Execution Node path above.
