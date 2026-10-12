# UI-01B — Wails shell and read-only existing-project opening

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01b-checkpoint-002).

UI-01B creates the first native desktop surface without creating a second
desired-state store. The Wails process is a Go transport and React renderer;
the authoritative `ProjectSnapshot/v1alpha1` is still built by Core on the
selected READY Execution Node.

## Scope and exception

The module baseline is Go 1.25.0 because Wails v2.15.0 requires it. The only
UI-01D item intentionally advanced is the fixed read-only
`BuildProjectSnapshot` protocol operation:

```text
native folder dialog -> Go path guard -> fixed SSH staging ->
Execution Node project-snapshot.yml -> ProjectSnapshot/v1alpha1 -> React
```

The request contains no playbook, remote path, command, candidate bytes,
owned-path classification, secret or mutation flag. The Execution Node invokes
only its fixed controller-only `project-snapshot.yml`, uses an empty
`platform_installer_owned_paths` set, returns a bounded 2 MiB response and
deletes that request's staging directory after replying. It makes no target
contact.

UI-01B does not implement EditSession, EditCommand, candidate projects, first
save, inventory ownership, archive/writer hardening, SecretRef hardening,
mutation, commit or rollback. Those remain UI-01D.

## Desktop surface

`main.go` binds only `ChooseProject`, `OpenProject`, `CurrentProject` and
`CloseProject`. A native directory dialog selects an existing project. The
runtime binding is supplied only through launch-time Execution Node transport
flags and a verified local immutable bundle; there is no settings editor or
credential persistence in this milestone. If the binding is absent or fails,
the UI reports a safe error and the local project is unchanged.

The Russian shell follows the accepted mockup ordering: Project, Servers,
Topology, Certificates, Services, Installation, Logs, Help, About and
Settings. Only Project is active. It has explicit loading, no-project, error
and read-only snapshot states. Future sections do not call a backend and no
save control exists.

## Reproducible commands

```powershell
go test ./...
Push-Location frontend
npm.cmd ci
npm.cmd run lint
npm.cmd test
npm.cmd run build
Pop-Location
wails build -nopackage -clean
```

The native application requires `-execution-node-address`,
`-execution-node-user`, `-execution-node-identity`,
`-execution-node-known-hosts`, `-execution-node-fingerprint` and
`-execution-bundle` to enable remote opening. These are runtime transport
inputs, never project settings or frontend-visible secrets.

## Acceptance evidence

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-01b-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
