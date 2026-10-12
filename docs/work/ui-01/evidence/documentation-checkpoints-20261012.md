# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## ui-01a-toolchain.md

Source document: [ui-01a-toolchain.md](../ui-01a-toolchain.md).

<a id="ui-01a-toolchain-checkpoint-001"></a>

Status: ACCEPTED for UI-01B bootstrap, audited 2026-09-05. UI-01A installs or
scaffolds nothing. Exact application dependencies enter lockfiles only in
UI-01B and must be checked again against security advisories then.


## ui-01a-contract-freeze.md

Source document: [ui-01a-contract-freeze.md](../ui-01a-contract-freeze.md).

<a id="ui-01a-contract-freeze-checkpoint-001"></a>

### Historical UI-01D remote acceptance before ADR-027

UI-01D was required to add the fixed remote snapshot operation and a standalone acceptance
test for the generated project-local `ansible.cfg`. On RED OS that test changes
to the exported project root, unsets `ANSIBLE_CONFIG`, asserts through
`ansible-config --version` that the active file is that root's `ansible.cfg`,
checks `ansible-config dump --only-changed` and `ansible-inventory --list`, then
runs the target-free Core validation under `sudo unshare -n`. It must prove the
configured inventory and merge policy without relying on the current adapter's
working directory or explicit `-i`. UI-01F owns the provenance bug fix and its
managed/user-owned/inline fixtures; the editor remains disabled for member
values until that evidence passes.



<a id="ui-01a-contract-freeze-checkpoint-002"></a>

Status: ACCEPTED by UI-01A, 2026-09-05. This is an architecture contract, not
an implementation. Normative words MUST, MUST NOT and MAY constrain UI-01B+.


## ui-01.md

Source document: [ui-01.md](../ui-01.md).

<a id="ui-01-checkpoint-001"></a>

Статус: PLAN / IN PROGRESS. Дата: 2026-09-05.
UI-01A–UI-01E6 DONE; UI-01D принят владельцем без финального review;
UI-01F1, UI-01F2, UI-01F3, UI-01F4, UI-01F5 и UI-01F6 DONE; UI-01F в целом DONE. Архитектурное планирование UI-NET-01 начато за отдельным owner gate; UI-01G остаётся следующим этапом Сертификатов. UI-01B реализует только read-only desktop
surface. План не является разрешением на автоматический старт всех milestones.
Каждый этап запускается отдельным запросом владельца.

<a id="ui-01-checkpoint-002"></a>

Статус: **DONE**. Evidence: [UI-01B](../ui-01b.md) and
[review](../reviews/ui-01b-review.md); blocking findings: **0**.

<a id="ui-01-checkpoint-003"></a>

Статус: DONE. Реализация и acceptance evidence: [docs/ui-01c.md](../ui-01c.md).

<a id="ui-01-checkpoint-004"></a>

Статус: **DONE (OWNER ACCEPTED WITHOUT REVIEW)**. Реализация и acceptance
evidence: [docs/ui-01d.md](../ui-01d.md). Финальный revision-bound review принят
владельцем без запуска; commit создан после executable gates.

<a id="ui-01-checkpoint-005"></a>

Статус: **UI-01H1 DONE** ([evidence](../ui-01h1.md)); **UI-01H2 DONE**
([evidence](../ui-01h2.md)); **UI-01H3 DONE** ([evidence](../ui-01h3.md));
**UI-01H4 DONE** ([evidence](../ui-01h4.md)); **UI-01H overall DONE**.

<a id="ui-01-checkpoint-006"></a>

Статус: **UI-01I DONE** ([evidence](../ui-01i.md)).

<a id="ui-01-checkpoint-007"></a>

Статус: **UI-01J DONE** ([evidence](../ui-01j.md)); **UI-01 overall DONE**.


## ui-01b.md

Source document: [ui-01b.md](../ui-01b.md).

<a id="ui-01b-checkpoint-001"></a>

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
are recorded in [UI-01B review](../reviews/ui-01b-review.md): 0 blocking.


<a id="ui-01b-checkpoint-002"></a>

Status: DONE (2026-09-05).


## ui-01a.md

Source document: [ui-01a.md](../ui-01a.md).

<a id="ui-01a-checkpoint-001"></a>

Статус: DONE, 2026-09-05 (documentation/contract only). Реализация UI и новых
production-контрактов не входила. Результат — набор принятых решений, а не
scaffold Wails/React.


## ui-01c.md

Source document: [ui-01c.md](../ui-01c.md).

<a id="ui-01c-checkpoint-001"></a>

Status: DONE, 2026-09-05.


## ui-01e1-architecture.md

Source document: [ui-01e1-architecture.md](../ui-01e1-architecture.md).

<a id="ui-01e1-architecture-checkpoint-001"></a>

### Historical implementation evidence (2026-09-14, before ADR-027)

- New sessions emit the deliberately server-CRUD-only
  `project-edit/v1alpha4`; v1alpha2/v1alpha3 tests remain compatible.
- The existing first-save compatibility form now requires desired hostname and
  reached the then-current Core-backed Review → Commit lifecycle; it is not a Servers
  page or a direct writer.
- Core projects `desiredHostname`, normalized `ansiblePort`, and generic host
  reference records. The Go reducer owns no service-specific delete rules.
- Local gates passed: focused Go tests, `go test ./...`, `go vet ./...`,
  frontend Vitest (7 tests), lint, production build, and
  `wails build -nopackage -clean`.
- A fresh RED OS QA workspace passed 242 Core tests (4 skipped), fixture-catalog
  and configuration-schema reproducibility, and
  `go test -race ./internal/installer ./internal/coreadapter`; the temporary
  workspace was removed. The checks are target-free.
- Added-line secret audit and `git diff --check` passed. Per owner direction,
  no additional reviewer loop was run for this milestone.



<a id="ui-01e1-architecture-checkpoint-002"></a>

Status: **DONE** (2026-09-14). This document defines the backend and contract
integration for server CRUD. UI-01E2 owns the production Servers page and its
Add/Edit/Delete dialogs.


## ui-01d.md

Source document: [ui-01d.md](../ui-01d.md).

<a id="ui-01d-checkpoint-001"></a>

## Real acceptance

Published runtime release `qa-ui-01d-20260907-13`:

```text
sha256:eded05ff714e081658a78bb14b5722acf226fb863440812d44e9c9db8876cd3f
```

The supported acquire/validate/prepare path produced and activated that
immutable release. Previous release manifests retained their original
content-addressed hashes. `GetCapabilities` advertised
`platform.installer/project-snapshot-request/v1alpha1`; the node remained
`READY`. The activation preparation plan was
`sha256:ed6d0827a2cfdda68c6ce0571264bca4b7c1266991efee2209b371e73b1e13b1`.

The opt-in Windows backend acceptance invoked the same methods exported to
Wails:

```text
go test . -run ^TestUI01DRemoteFirstSaveAcceptance$ -v -count=1 -timeout 10m
```

The final bound run completed in 11.04 seconds (11.387 seconds package time)
and proved create -> start session -> append
`CreateServer` -> remote review -> explicit commit -> post-commit remote
snapshot. The accepted plan was
`a87e897411ac10b6f9b24a973836ae67`; the committed and Core-observed revision
was `sha256:aaa77127b8ebb3345554771cbf633c26674c1178cf2fd5433c1b026b25bda126`.
The test compared `project.yml` before and after and found no mutation, required
the exact three first-save files and verified that no `host_vars` tree was
materialized.

The committed project was then exercised directly on RED OS. Its own
`ansible.cfg` resolved the inventory and `hash_behaviour=merge` settings. The
fixed snapshot playbook ran under `sudo unshare -n` and returned `PASS`,
`changed=0`, revision
`sha256:1d91aa6fab38f30cb03c422047c0a63b4dfdadf98cef79bf0bb122bf98f9b968`.
This proves the standalone project path without target-node network access.

Activation did not run service playbooks or alter Kafka desired state.
`kafka@kafka-kafka-1`, `kafka@kafka-kafka-2` and
`kafka@kafka-kafka-3` remained `active/running` on nodes 1–3.



<a id="ui-01d-checkpoint-002"></a>

## Regression evidence

- RED OS Core: 238 tests PASS, 4 skipped;
- RED OS race: `internal/installer` and `internal/executionnode` PASS;
- local `go test ./...` and `go vet ./...`: PASS;
- frontend ESLint: PASS; Vitest: 6/6 PASS; TypeScript/Vite production build:
  PASS;
- `wails build -nopackage -clean`: PASS on Windows with Wails 2.15.0 and Go
  1.25.0;
- catalog digest reproducibility:
  `sha256:e87acc790d389a67ea90da7b785562018cd3450181fa00f4dfa2b38fe9eaeccf`;
- service configuration schema reproducibility: PASS;
- added-line secret audit and `git diff --check`: PASS;
- final architecture/Core-contract/safety reviews: not run on the final tree;
  owner acceptance is recorded explicitly above;
- the last completed architecture pass found 0 overengineering and 0 scope
  creep, but was stale after subsequent contract corrections.

During acceptance three bounded defects were found and corrected: the
candidate archive size guard had leaked into runtime-bundle staging, failed
protocol processes discarded their structured error response, and snapshot
provenance attempted to parse `ansible.cfg` as YAML. The final implementation
keeps candidate limits candidate-only, preserves typed safe errors and treats
`ansible.cfg` as revision/ownership input rather than semantic YAML.
Final review also hardened the writer to use an OS-held persistent lock,
made PREPARING and interrupted rollback recovery idempotent without deleting
unproven parent directories, rejected unknown command fields, kept the Wails
slice limited to the exact `CreateServer` command, and retained draft/plan
state for explicit UI retry after transient or Core-reported blocking results.
Future v1alpha2 command variants remain contract/Core-owned and are not exposed
by this milestone.
The final safety pass additionally preserved existing Windows canonical DACLs
through publish and rollback, applied the canonical parent ACL to new files,
made candidate staging IDs cryptographically unique with ownership-scoped
cleanup and a marker plus directory-identity recheck immediately before
recursive removal, rejected scalar secret settings before staging, reconciled expired
application sessions, and allowed a blocked/expired commit to return to Review.
Windows recovery also binds the original DACL to the transaction journal and
rejects ACL-only external changes without accepting or overwriting them.
The final Core-contract corrections centralize the complete candidate request
shape/type/pattern checks and safely normalize malformed project YAML:
invalid requests return the typed `PROJECT_SNAPSHOT_REQUEST_INVALID` response
before staging or Core execution, without a Python traceback. Presence-aware
Go decoding also rejects explicit schema-invalid optional values such as
`sshPort: 0` and `clearSSHPort: false`.



<a id="ui-01d-checkpoint-003"></a>

Status: **DONE (OWNER ACCEPTED WITHOUT REVIEW)** (2026-09-07). Implementation
and executable acceptance are complete; the owner accepted the final tree
without an additional revision-bound review. UI-01 overall remains **NOT
DONE**; UI-01E is not started.


## ui-01e3-architecture.md

Source document: [ui-01e3-architecture.md](../ui-01e3-architecture.md).

<a id="ui-01e3-architecture-checkpoint-001"></a>

Status: **OWNER-APPROVED PLAN; ADDITIONAL REVIEW WAIVED (2026-09-14)**. This
milestone adds one write-only, runtime-only technical credential for all target
servers in the currently open project. It does not contact targets, prepare an
Execution Node, change project files or implement execution-time secret
transport.


## ui-01e2-architecture.md

Source document: [ui-01e2-architecture.md](../ui-01e2-architecture.md).

<a id="ui-01e2-architecture-checkpoint-001"></a>

### Historical native acceptance before ADR-027

The following records the completed Core-backed E2 acceptance and is not the
acceptance contract for new local Save.

Native Windows acceptance used temporary QA projects and the existing READY
Execution Node only for target-free candidate proof. It covers:

```text
metadata-only project
→ Add two servers
→ Review
→ Commit
→ Edit one server and exercise explicit/clear port
→ Review
→ Commit
→ reopen and compare authoritative rows
→ attempt referenced delete and observe BLOCKED with zero mutation
→ delete an unreferenced server and commit
```

QA must compare project digests around append, blocked review and commit, prove
remote candidate staging cleanup and avoid Kafka/service apply or any target
host contact.

Required gates:

```text
affected Go and Wails tests
go test ./...
go vet ./...
frontend test
frontend lint
frontend production build
wails build -nopackage -clean
affected RED OS race tests
target-free RED OS candidate acceptance on temporary projects
secret audit
git diff --check
```

Core full-suite and catalog/schema reproducibility are required only if a real
E2 defect forces changes to those boundaries; otherwise exhaustive combined
regression remains E6. All E2 QA workspaces are removed after evidence is
captured.



<a id="ui-01e2-architecture-checkpoint-002"></a>

## 18. Historical final acceptance evidence (before ADR-027)

The Windows Wails production build passed with Go 1.25.0 and Wails 2.15.0.
Focused frontend coverage passed 11/11 tests, lint, TypeScript and Vite
production build. `go test ./...`, `go vet ./...` and the RED OS
`go test -race ./internal/installer` gate passed; the isolated RED OS QA
workspace was removed.

The opt-in Wails-bound remote acceptance used the active immutable runtime
`qa-ui-01e2-20260914-02`
(`sha256:dcdd5ea9bec9cc6bf842ae3a15f5f7ff9e71f144fadafc2ac8be79b37cd49ad8`)
on the READY QA Execution Node:

```text
metadata-only project
→ CreateServer node1 (explicit port 22)
→ Review → Commit
→ CreateServer node2 (explicit port 22)
→ Review → Commit
→ UpdateServer node1 (new address, clearSSHPort)
→ Review → Commit
→ DeleteServer node2
→ Review → Commit
```

`TestUI01E2RemoteServerCRUDAcceptance` passed in 56.90 seconds. Every
candidate snapshot returned `PASS`; the final authoritative state contained
only `node1` at `192.0.2.12`, with no Installer-owned `ansible_port` override.
The test uses TEST-NET addresses and performs only target-free snapshot proof.
No service playbook or Kafka deployment was invoked. Remote inspection after
the test confirmed the active release digest, advertised
`BuildProjectSnapshot` capability and zero residual candidate staging
directories. `git diff --check` passed.


<a id="ui-01e2-architecture-checkpoint-003"></a>

Status: **DONE (2026-09-14)**. This milestone implements the
production Servers editor surface over the accepted UI-01D lifecycle and the
UI-01E1 server CRUD contract. It does not implement runtime credentials,
connection discovery, Execution Node management or readiness.


## ui-01e3.md

Source document: [ui-01e3.md](../ui-01e3.md).

<a id="ui-01e3-checkpoint-001"></a>

## Acceptance evidence

Windows automated gates passed:

```text
go test ./...
go vet ./...
frontend: npm run test -- --run     # 12 tests
frontend: npm run lint
wails build -nopackage -clean
```

The production Windows executable opened the existing local `ui-01c`
metadata-only project through the native folder dialog. On Servers, a
non-sensitive test credential produced a safe `Available until` status and
immediately cleared the password field; explicit Clear returned the visible
missing status. The project was not edited and no target or Execution Node was
contacted.

The affected concurrency package passed on RED OS with CGO:

```text
CGO_ENABLED=1 go test -race ./internal/runtimesecret
```

The source was copied with `scripts/qa-sync.ps1 -IncludeGo` to a fresh
`/var/tmp/platform-installer-qa-*` workspace and removed by the same helper.
`git diff --check` passed. No Core/service/Ansible regression was needed:
E3 changes only the desktop application runtime boundary.


<a id="ui-01e3-checkpoint-002"></a>

Status: **DONE** (2026-09-14). UI-01E3 introduces one bounded, project-bound
runtime credential lease for the Servers page. It does not contact targets or
an Execution Node and does not write credential data to a portable project.


## ui-01e4-architecture.md

Source document: [ui-01e4-architecture.md](../ui-01e4-architecture.md).

<a id="ui-01e4-architecture-checkpoint-001"></a>

Status: **DRAFT — awaiting architecture review and owner approval**.


## ui-01e6.md

Source document: [ui-01e6.md](../ui-01e6.md).

<a id="ui-01e6-checkpoint-001"></a>

Status: **DONE** (2026-09-15).


## ui-01e5-architecture.md

Source document: [ui-01e5-architecture.md](../ui-01e5-architecture.md).

<a id="ui-01e5-architecture-checkpoint-001"></a>

## Implementation evidence

- `CheckExecutionNode` uses only the application-owned binding and the
  existing read-only `executionnode.Service.InspectExecutionNode` operation.
- `PlanExecutionNodePreparation` retains the exact saved revision, trusted
  binding, plan ID/digest and expiry only in memory. `PrepareExecutionNode`
  requires that exact plan ID after explicit UI confirmation, re-checks the
  saved revision and binding, then performs a fresh inspection before Verify.
- The Wails surface receives bounded safe readiness/step/finding DTOs only;
  it receives no connection values, credentials, host-key inputs, commands or
  staging paths.
- The Servers panel exposes Check, planning and an explicit confirmation
  button. The global App Shell shows the typed readiness status. Installation
  is gated until `READY`, never performs Prepare, and states that fresh
  `BuildDeploymentPlan` remains mandatory.
- Mockup reconciliation: its global readiness badge and Servers-side
  read-only Check / explicitly confirmed Prepare flow are implemented. The
  mockup's external-host form remains illustrative only; E5 deliberately does
  not turn that form or a project-server candidate into a trusted binding.
- Focused Go tests cover trusted-binding rejection for project candidates,
  revision-bound Prepare continuation and post-Prepare Verify. Frontend tests
  cover the `READY` navigation gate and confirmation flow. `go test ./...`,
  frontend lint/test/build, Wails build and `git diff --check` passed. RED OS
  `go test -race ./internal/executionnode` passed with CGO enabled in a
  temporary workspace that was cleaned afterwards.


<a id="ui-01e5-architecture-checkpoint-002"></a>

Status: **DONE — 2026-09-15**.


## ui-01f-architecture.md

Source document: [ui-01f-architecture.md](../ui-01f-architecture.md).

<a id="ui-01f-architecture-checkpoint-001"></a>

Status: **DRAFT ARCHITECTURE PLAN**

<a id="ui-01f-architecture-checkpoint-002"></a>

Status: **DONE**.

<a id="ui-01f-architecture-checkpoint-003"></a>

Status: **DONE**. Detailed architecture and evidence:
`docs/work/ui-01/ui-01f2-architecture.md` and `docs/work/ui-01/reviews/ui-01f2-architecture-review.md`.

<a id="ui-01f-architecture-checkpoint-004"></a>

Status: **DONE**. Evidence: `docs/work/ui-01/ui-01f3-architecture.md`.

<a id="ui-01f-architecture-checkpoint-005"></a>

Status: **DONE**. Evidence: `docs/work/ui-01/ui-01f4-architecture.md`.

<a id="ui-01f-architecture-checkpoint-006"></a>

Status: **NEXT**; separate owner gate. Plan: `docs/work/ui-01/ui-01f5-architecture.md`.

<a id="ui-01f-architecture-checkpoint-007"></a>

### UI-01F6 — acceptance and regression — DONE


## ui-01f1-architecture.md

Source document: [ui-01f1-architecture.md](../ui-01f1-architecture.md).

<a id="ui-01f1-architecture-checkpoint-001"></a>

## 15. Implementation evidence

UI-01F1 was implemented against the approved plan baseline `9dd719b`.
`UI01F1-DIFF-001` and `UI01F1-DIFF-003` passed targeted review. The owner
authorized the final bounded correction for `UI01F1-DIFF-002`: the published
`genericEndpoint` marker is accepted only when absent or exactly `{}`; scalar,
sequence and nonempty-object forms fail with the existing safe catalog error.
No further architecture-review cycle was run or required for that exact
contract-compliance correction.

Focused Go tests, `go test ./...`, `go vet ./...`, RED OS catalog
reproducibility and `git diff --check` passed. F2 remains **NOT STARTED**.


<a id="ui-01f1-architecture-checkpoint-002"></a>

Status: **IMPLEMENTED**


## ui-01j.md

Source document: [ui-01j.md](../ui-01j.md).

<a id="ui-01j-checkpoint-001"></a>

Status: **DONE** (2026-09-21). UI-01 overall is **DONE**.


## ui-01i.md

Source document: [ui-01i.md](../ui-01i.md).

<a id="ui-01i-checkpoint-001"></a>

## Acceptance evidence

- Windows focused export backend tests: `go test ./internal/installer -run
  TestProjectExport -count=1` — PASS.
- Frontend export/reopen component test: `npm test -- --run App.test.tsx` —
  PASS, 30 tests. It proves Preview → Commit via opaque plan digest → explicit
  `OpenProject(exportedRoot)`.
- Frontend lint and production build — PASS.
- `go test ./...` and `go vet ./...` — PASS.
- `wails build -nopackage -clean` — PASS.
- RED OS isolated workspace: `CGO_ENABLED=1 go test -race
  ./internal/installer -run TestProjectExport -count=1` — PASS. The workspace
  was removed after the test.
- RED OS catalog and schema reproducibility checks — PASS:
  `build_fixture_catalog.py --check` and
  `build_service_configuration_schema.py --check`.
- Existing I3 acceptance remains valid: the built Windows Wails application
  opened the native folder picker; a real temporary export had byte-identical
  portable documents, excluded runtime/generated files, target-free RED OS
  Core validation, and equal source/export snapshot fingerprint
  `sha256:fbb68160f0799444205c2e07c5b1a9ec80e1d5d4938cbf1448507ccd388ffbe9`.
- Changed-scope secret audit found no newly introduced plaintext secret or
  credential value. `git diff --check` passed.

No Core, Execution Node, target host, service deployment, or canonical source
project mutation is part of export. UI-01J is the next milestone; UI-01 overall
remains not done.


<a id="ui-01i-checkpoint-002"></a>

Status: **DONE** (2026-09-21).


## ui-01i-architecture.md

Source document: [ui-01i-architecture.md](../ui-01i-architecture.md).

<a id="ui-01i-architecture-checkpoint-001"></a>

Status: **PLAN — owner-revised after FULL review; targeted recheck pending**


## ui-01h4.md

Source document: [ui-01h4.md](../ui-01h4.md).

<a id="ui-01h4-checkpoint-001"></a>

Status: **DONE**. UI-01H overall is **DONE**.


## ui-01h3.md

Source document: [ui-01h3.md](../ui-01h3.md).

<a id="ui-01h3-checkpoint-001"></a>

## Evidence

- independent H3 full PLAN review: **APPROVE**, zero blocking findings and no
  overengineering finding;
- focused App/component acceptance: composite member Set and Remove commands,
  independent member selection, trusted TLS selector and Certificates return
  without navigation-created session;
- frontend lint, **55** tests and production build: PASS;
- `wails build -nopackage -clean`: PASS on Windows;
- `go test ./...`, `go vet ./...` and `git diff --check`: PASS;
- no Core, Execution Node, Ansible service lifecycle or target host was
  contacted or changed. Python is unavailable on the Windows workstation;
  no catalog/schema source changed, so catalog reproducibility is retained for
  the H4 RED OS acceptance gate.

UI-01H4 remains next.


<a id="ui-01h3-checkpoint-002"></a>

Status: **DONE**


## ui-01h3-architecture.md

Source document: [ui-01h3-architecture.md](../ui-01h3-architecture.md).

<a id="ui-01h3-architecture-checkpoint-001"></a>

## Implementation evidence

The independent FULL PLAN review approved this bounded design with zero
blocking and overengineering findings. H3 extends only the existing frontend
adapter and shared App-owned session: it adds the already-published member
configuration projection, exact MEMBER-scoped v1alpha8 Set/Remove intents,
the trusted TLS-profile ID selector and the application-local
Certificates-to-Services return context. No Go, Core, catalog, schema, writer,
Execution Node, PKI or target behavior changed.

Focused component acceptance covers exact composite Set and Remove targets,
independent member selection, TLS selection from direct managed IDs and the
contextual Certificates round-trip without creating a session. Windows
frontend lint, 55 tests, production build, Wails build, `go test ./...`,
`go vet ./...` and `git diff --check` passed. The local Windows workstation
does not provide Python; catalog generation was unchanged by this frontend-only
slice and is deferred to H4's RED OS acceptance gate. UI-01H4 remains next.


<a id="ui-01h3-architecture-checkpoint-002"></a>

Status: **DONE**


## ui-01h2.md

Source document: [ui-01h2.md](../ui-01h2.md).

<a id="ui-01h2-checkpoint-001"></a>

## Evidence

- focused App/component coverage: Services list/detail, Topology hand-off,
  heading focus, explicit return, one shared v1alpha8 Set command and its
  acknowledgement lock, unavailable catalog without raw value exposure;
- frontend lint, 52 tests and production build: PASS;
- `wails build -nopackage -clean`: PASS on Windows;
- `go test ./...`, `go vet ./...` and `git diff --check`: PASS.

No Core, Ansible, Execution Node, PKI, catalog or service deployment was
contacted or changed. UI-01H3 remains next.


<a id="ui-01h2-checkpoint-002"></a>

Status: **DONE**


## ui-01h2-architecture.md

Source document: [ui-01h2-architecture.md](../ui-01h2-architecture.md).

<a id="ui-01h2-architecture-checkpoint-001"></a>

## Implementation evidence

The approved full PLAN review found four bounded issues (separate list/detail
views, direct configuration projection, exact managed/admitted gating and
focus behavior). The owner accepted the corrections and one targeted recheck
passed all four; no further architecture review was needed.

H2 implements the single Services route, application-local list/detail state
and the Topology hand-off. It uses only H1's direct managed configuration
projection and v1alpha8 Set/Remove intents through the existing shared
EditSession. The unavailable-catalog path exposes only setting identity and
override presence, never a raw value. No Go/Core/schema/catalog/writer,
Execution Node, PKI or target behavior changed.

Focused frontend acceptance covers both entry paths, focus return, one shared
session/intended v1alpha8 command, the acknowledgement lock and safe
unavailable-catalog display. Windows gates passed: frontend lint, 52 tests,
production build and `wails build -nopackage -clean`; `go test ./...`,
`go vet ./...` and `git diff --check` also passed. H3 remains next.


<a id="ui-01h2-architecture-checkpoint-002"></a>

Status: **DONE**


## ui-01h1.md

Source document: [ui-01h1.md](../ui-01h1.md).

<a id="ui-01h1-checkpoint-001"></a>

## Evidence

- focused App/session, catalog/reference and descriptor-validator Go tests;
- `go test ./...` and `go vet ./...` on Windows;
- frontend lint, 49 tests and production build; Wails production build;
- RED OS: `go test ./...`, race tests for `internal/installer` and
  `internal/projectlifecycle`, fixture-catalog reproducibility and nine
  project-edit contract tests;
- changed-scope secret audit found no plaintext material; `git diff --check`
  passed.

The initial targeted DIFF review verified DIFF-001, DIFF-003 and the frozen
review input, then identified a residual hardcoded `tlsProfile` branch. The
owner authorized its exact removal plus a regression; that correction passed
the focused and full Go gates. Per owner direction, no additional architecture
review was run after the correction. UI-01H2 remains not started.


<a id="ui-01h1-checkpoint-002"></a>

Status: **DONE by owner acceptance**


## ui-01h-architecture.md

Source document: [ui-01h-architecture.md](../ui-01h-architecture.md).

<a id="ui-01h-architecture-checkpoint-001"></a>

Status: **H1–H4 IMPLEMENTED; UI-01H DONE**


## ui-01g4.md

Source document: [ui-01g4.md](../ui-01g4.md).

<a id="ui-01g4-checkpoint-001"></a>

Status: **DONE** (2026-09-17). UI-01G overall is **DONE**.


## ui-01g3.md

Source document: [ui-01g3.md](../ui-01g3.md).

<a id="ui-01g3-checkpoint-001"></a>

Status: **DONE** (2026-09-17).


## ui-01g2.md

Source document: [ui-01g2.md](../ui-01g2.md).

<a id="ui-01g2-checkpoint-001"></a>

Status: **DONE** (2026-09-17).


## ui-01g1.md

Source document: [ui-01g1.md](../ui-01g1.md).

<a id="ui-01g1-checkpoint-001"></a>

Status: **DONE** (2026-09-17).


## ui-01g-architecture.md

Source document: [ui-01g-architecture.md](../ui-01g-architecture.md).

<a id="ui-01g-architecture-checkpoint-001"></a>

Status: **UI-01G DONE**. This document remains the governing
architecture for the remaining slices. UI-01G1 added only the additive command
contract, bounded local desired-state projection, final-state references and
guarded local Save; it did not authorize certificate issuance, reissue,
materialization, service apply, or a change to standalone Ansible/Core PKI
behavior. Evidence: [ui-01g1.md](../ui-01g1.md).


## ui-01f6.md

Source document: [ui-01f6.md](../ui-01f6.md).

<a id="ui-01f6-checkpoint-001"></a>

Status: DONE. Date: 2026-09-16.


## ui-01f5-architecture.md

Source document: [ui-01f5-architecture.md](../ui-01f5-architecture.md).

<a id="ui-01f5-architecture-checkpoint-001"></a>

Status: **PLAN / NOT STARTED**


## ui-01f4-architecture.md

Source document: [ui-01f4-architecture.md](../ui-01f4-architecture.md).

<a id="ui-01f4-architecture-checkpoint-001"></a>

## 19. Completion evidence

Completed on 2026-09-16. The bounded plan review finished with zero blocking
findings. The F4 implementation contains no new persistence, Core semantics or
service-specific branch. Focused and full frontend tests, typecheck, lint,
production build, `go test ./...`, `go vet ./...`, Windows Wails build and
`git diff --check` passed. UI-01F5 is **NEXT** and has not started.


<a id="ui-01f4-architecture-checkpoint-002"></a>

Status: **DONE** (2026-09-16)


## ui-01f3-architecture.md

Source document: [ui-01f3-architecture.md](../ui-01f3-architecture.md).

<a id="ui-01f3-architecture-checkpoint-001"></a>

## 15. Implementation evidence

Status: **DONE**, 2026-09-16. UI-01F4 is **NEXT** and remains a separate owner
gate.

- the Wails executable created two Kafka deployments without an Execution
  Node, preserved the shared draft across Servers and Topology, committed once
  through the common Review/Save flow and restored both deployments after a
  native-dialog close/reopen;
- focused frontend coverage proves Add/Delete, stable selection, duplicate-ID
  presentation validation, the shared 16-command limit, conflict recovery and
  `COMMITTED_REFRESH_FAILED` invalidation/reopen behavior;
- the acceptance run exposed and fixed one pre-existing F1 contract defect:
  the catalog reader now accepts the exact published service-manifest
  identifier grammar, including `pg_auto_failover`;
- frontend tests (33), lint, typecheck, production build, `go test ./...`,
  `go vet ./...`, Wails production build, changed-scope secret audit and
  `git diff --check` passed;
- generated catalog/schema inputs were unchanged; the narrow Go grammar fix
  additionally passed `CGO_ENABLED=1 go test -race
  ./internal/projectlifecycle` on RED OS in an isolated workspace, which was
  removed and its absence verified;
- no Core operation, Execution Node or target host was contacted during the
  Windows Save/reopen acceptance.


<a id="ui-01f3-architecture-checkpoint-002"></a>

Status: **DRAFT FOR OWNER APPROVAL; IMPLEMENTATION NOT STARTED**\
Parent milestone: `UI-01F — topology editor`\
Approved implementation baseline: `836653d4def69467e017c50df96d8069acf0698b`\
Contract baseline: `platform.installer/edit-command/v1alpha5`


## ui-01f2-architecture.md

Source document: [ui-01f2-architecture.md](../ui-01f2-architecture.md).

<a id="ui-01f2-architecture-checkpoint-001"></a>

Status: **DONE (2026-09-16)**
