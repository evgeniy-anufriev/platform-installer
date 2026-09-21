# UI-01J — final UI-01 acceptance

Status: **DONE** (2026-09-21). UI-01 overall is **DONE**.

UI-01J adds no infrastructure, Core, catalog, service, PKI or execution
behavior. It closes the UI-01 editor only after cross-platform regression,
native desktop smoke, target-free Core proof and final ownership/safety gates.

## Mockup reconciliation

The native Windows start screen matches the current project-first shell:
Project remains available before a project is open, remaining project pages are
gated, and the shell explains the separate local Save and Core Verify actions.
The editor order remains Servers → Topology → Certificates → Services.

The static HTML's historical import/template illustration is not a UI-01
implementation requirement. UI-01I intentionally supports only native
full-configuration export and reopening; archive/template/import remain out of
scope.

## Windows acceptance

- frontend lint: PASS;
- frontend component suite: **56 PASS**;
- Playwright deterministic browser seam: **1 PASS**;
- TypeScript/Vite production build: PASS;
- `go test ./...` and `go vet ./...`: PASS;
- `wails build -nopackage -clean`: PASS;
- the built `platform-installer-ui.exe` was opened for native smoke. It showed
  the project landing state, Create/Open actions, local Save/Core Verify
  explanation and correct pre-project navigation gating. No project, runtime,
  service or target was mutated.

## RED OS target-free acceptance

A fresh source tree was transferred through `scripts/qa-sync.ps1 -IncludeGo`
to an isolated `/var/tmp/platform-installer-qa-*` workspace and removed after
the checks.

- `CGO_ENABLED=1 go test -race . ./internal/installer ./internal/coreadapter`:
  PASS;
- Core Python suite: PASS;
- `project_snapshot_acceptance.yml`: PASS on controller `localhost` with
  `changed=0`;
- the same ProjectSnapshot acceptance under `sudo -n unshare -n`: PASS;
- fixture catalog and service-configuration schema reproducibility: PASS.

No inventory target was contacted. No apply, verify, Kafka lifecycle, PKI
materialization, Execution Node preparation or runtime activation ran.

## Final export safety decision

The owner approved the Linux namespace-safety rule: zero staging residue is not
required when deleting its root cannot be proven identity-bound under a hostile
sibling-swap race. A pre-publication failure therefore returns the distinct
`EXPORT_STAGING_RETAINED` failure; it never publishes the destination, modifies
the source or deletes a substituted sibling. Windows uses its handle-bound
delete and cleans ordinary failed staging.

Focused tests prove Linux retained status/no publication/sibling survival and
Windows ordinary cleanup. RED OS race tests passed. No helper, automatic
scavenger, pathname retry or background cleanup subsystem was introduced.

## Independent final gates

- Core-contract reviewer: PASS, **0 blocking**. Ansible/Core authority,
  ADR-027 Save/Verify/Plan sequencing and target-free export boundaries remain
  intact.
- Safety reviewer: PASS, **0 blocking** after the owner-authorized retained
  staging correction.
- Changed-scope secret audit found no plaintext secret material. Runtime
  credentials remain write-only session data.
- `git diff --check`: PASS.

QA artifacts and generated Wails/Playwright output were removed. UI-02 does
not start automatically.
