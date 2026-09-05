# UI-01B — Wails shell and read-only existing-project opening

Status: DONE (2026-09-05).

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

The controlled QA publication produced immutable release
`sha256:4ae17a7b79c5fcbbcdacc6537dd9138a72bfe0bbfca2c42be45c6a3a64b98fe6`
(`qa-ui-01b-20260905-01`). Supported `prepare` activation returned `READY`,
`Changed:true`; the previous `3260257b...` release directory and its manifest
checksum were still present and unchanged. `GetCapabilities` advertised the
fixed `BuildProjectSnapshot` operation.

The Windows production build (`wails build -nopackage -clean`) opened its
native directory dialog and rendered the returned read-only Core snapshot.
The opt-in production-path acceptance test exercised
`App.OpenProject -> OpenSSHTransport -> BuildProjectSnapshot` against the
tracked `examples/valid/ui-project-snapshot` project in 3.18 seconds and
returned `OPEN` with snapshot `PASS`. The seven canonical project-file hashes
were identical before and after; the Execution Node's pre-existing lifecycle
journal directory set was identical too, proving request staging cleanup.

After activation, the node inspection and capability handshake were `READY`/
PASS. Canonical Kafka units remained active without a Kafka execution:
`kafka@kafka-kafka-1` on node1, `kafka@kafka-kafka-2` on node2 and
`kafka@kafka-kafka-3` on node3.

Final local gates passed: `go test ./...`, `go vet ./...`, frontend lint/test/
build and Wails production build. RED OS affected race tests passed for
`./internal/coreadapter`, `./internal/executionnode` and
`./cmd/platform-installer`; catalog and configuration-schema reproducibility
passed. The established full Core suite evidence is `222 passed, 4 skipped`;
the Core tree was unchanged after that run, while the final QA node did not
have `pytest`, so no package was installed merely to repeat it. Review findings
are recorded in [UI-01B review](ui-01b-review.md): 0 blocking.
