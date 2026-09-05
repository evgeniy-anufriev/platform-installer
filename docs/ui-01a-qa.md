# UI-01A — documentation QA

Status: PASS, 2026-09-05. Scope was documentation/contracts only; no destructive
E2E, target contact, service mutation or production UI build was run.

## Checks

| Check | Result |
| --- | --- |
| Referenced local Markdown files exist | PASS |
| UI-01A changed only root state/instructions and `docs/` | PASS |
| No Wails/React scaffold, package manifest or production Go/Python/Ansible change | PASS |
| Existing edit operation names checked against `internal/installer/edit.go` | PASS |
| Existing project/edit/snapshot schemas and Go adapter/writer boundaries inspected | PASS |
| Mockup pre-start and acceptance reconciliation | PASS |
| Toolchain discovery and peer/engine audit | PASS |
| Architecture/Core review | PASS, 0 blocking |
| Safety review | PASS, 0 blocking |
| Secret-value scan of changed files | PASS |
| `git diff --check` | PASS; Git reports only the existing LF-to-CRLF notice for the HTML mockup |

## Toolchain evidence

Commands executed on the Windows workstation:

```text
go version
node --version
npm.cmd --version
wails version
wails doctor
npm.cmd view <selected-package> version/engines/peerDependencies
```

Observed Go 1.26.7, Node 24.19.0, npm 11.17.0, Wails 2.15.0 and WebView2
152.0.4191.62. `wails doctor` reported the workstation ready. Repository
`go.mod` remains at Go 1.24. Exact selected frontend versions and compatibility
evidence are recorded in [the toolchain freeze](ui-01a-toolchain.md). No package
was installed and no lockfile/scaffold was created.

## Deliberately deferred execution tests

- Native Wails build and frontend tests start in UI-01B.
- Create/reopen filesystem tests start in UI-01C.
- v1alpha2 schemas, first-write transaction, remote complete-candidate Core
  proof, Windows reparse/ACL tests and project-local Ansible proof start in
  UI-01D.
- Server/session credential tests start in UI-01E.
- Member-origin correction tests start in UI-01F.
- Target credential secret-lease transfer and cleanup are UI-02 acceptance.

Deferral is required by the UI-01A documentation-only boundary and is not
reported as present production behavior.
