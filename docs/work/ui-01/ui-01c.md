# UI-01C — metadata-only managed project creation

Status: DONE, 2026-09-05.

UI-01C implements local project creation and empty-project reopening. The
operation verifies the trusted local immutable bundle on every create call,
publishes exactly one `project.yml` through an OS-specific no-replace atomic
publication path, and never invokes Core, Ansible, SSH, target hosts, an
Execution Node or an edit/save session.

The Wails/React surface provides a native parent-folder picker. The selected
parent is combined with the current project name; an empty project name is a
visible validation error and never reaches the backend. If the destination is
edited manually, its parent and final segment remain synchronized with later
project-name changes.

Acceptance evidence:

- Windows manual create/reopen produced `Projects/ui-01c/project.yml`.
- The created project directory contains exactly one file.
- The manifest has the managed `project-<16 lowercase hex>` identity, catalog
  lock and artifact lock, with no inventory, variables or desired state.
- `go test ./... -timeout 30m` and `go vet ./...` passed.
- RED OS `CGO_ENABLED=1 go test -race ./internal/projectlifecycle` passed in an
  isolated synced workspace; the workspace was removed and absence verified.
- Frontend tests (4), lint and production build passed.
- `wails build -nopackage -clean` and `git diff --check` passed.

The repository-local bundle auto-discovery used by the development desktop
build still requires full `executionbundle.ValidateRoot` verification. An
explicit `-execution-bundle` remains the higher-priority runtime input.

UI-01D remains next and owns first save, edit session, candidate state and
inventory writer work. No UI-01D implementation is included here.
