# UI-01D — first write and edit/review session

Status: **DONE (OWNER ACCEPTED WITHOUT REVIEW)** (2026-09-07). Implementation
and executable acceptance are complete; the owner accepted the final tree
without an additional revision-bound review. UI-01 overall remains **NOT
DONE**; UI-01E is not started.

UI-01D adds the shared Go-owned transient edit/review/commit lifecycle and the
narrow first-save UI required to turn a metadata-only managed project into a
complete minimal Ansible project. It does not add the full server, topology,
PKI or service editors and does not start an installation.

## Accepted boundary

- React renders form/session/plan/result state and calls generated Wails
  bindings; it does not parse or write YAML.
- Go owns the bounded in-memory session, candidate assembly, revision-bound
  plan, guarded transaction, rollback/recovery and explicit discard.
- the selected READY Execution Node runs the fixed candidate
  `BuildProjectSnapshot` operation; Core remains authoritative for the
  target-free project snapshot and infrastructure semantics;
- the candidate request is the closed nested
  `platform.installer/project-snapshot-request/v1alpha1` contract and is used
  only after capability negotiation. Older nodes fail without candidate
  staging or silent downgrade;
- the first commit creates only `ansible.cfg`, `inventory/hosts.yml` and
  `inventory/group_vars/all/platform-installer.yml`. `project.yml` and unknown
  files are byte-preserved. No credentials, implicit localhost or empty
  `platform_targets` project is committed.

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

## Deferred scope

UI-01E owns the full server editor, session credentials and Execution Node
selection/preparation panel. UI-01F–H own topology, PKI and service forms.
UI-02 owns installation planning/execution/progress/result composition. No
later milestone was started by UI-01D.
