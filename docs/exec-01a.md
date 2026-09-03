# EXEC-01A: pre-Core Execution Node bootstrap

## Boundary

EXEC-01A prepares a selected Linux Execution Node before Platform Core can run.
It does not replace EXEC-01: after a successful capability handshake, existing
Core playbooks retain ownership of project validation, service semantics,
topology, apply and verify.

Go owns SSH connection lifecycle, explicit host-key trust, elevation invocation,
runtime bundle acquisition/transfer, returned-bundle verification, immutable
cache publication, activation transaction and readiness classification. Core
and Python execute only on the selected Execution Node. The workstation never
acts as a Core/Python runtime. A fresh install node cannot build the bundle
needed to install Python on itself; explicit DEV acquisition therefore uses a
trusted acquisition environment that already has the builder runtime. Core
owns the post-activation capability response. Neither the Go bootstrap layer
nor its bundle builder resolves Ansible precedence or service configuration.

## One offline bundle and source policy

The user-visible distribution is one Installer plus one offline bundle. The
bundle may contain execution runtime, Core, service artifacts and OS package
closures in separate internal namespaces; digest-addressed storage remains an
implementation detail.

The project-root `bundle/` directory is the operational bundle and
distribution root. Published immutable bundles are stored by digest beneath
it, and separately supplied distribution artifacts are kept under
`bundle/artifacts/<service>/`. These files are local operational inputs and
are not desired project state or committed credentials.

```text
execution-runtime/
  manifest.yaml
  ansible-core/
  services/
  contracts/
  catalog/
runtime/{python,packages,artifacts}/
```

`manifest.yaml` declares the bootstrap protocol, Core version, catalog and
schema digests, supported OS/version/architecture tuples, and every component
path, size and SHA-256. The Go verifier rejects traversal, symlinks,
non-regular files, duplicate/unsorted entries and any checksum mismatch before
transfer. It does not execute content from the bundle.

`ansible-core/tools/build_execution_runtime_bundle.py` creates the directory
from the checked-out Core/service/catalog sources and an explicit runtime
input. It makes no network request and runs only on the trusted acquisition
environment. A structurally valid bundle can still be incomplete for a
particular project; completeness is evaluated against the requirements being
installed.

For every install requirement, the actual install node is queried first for a
compatible artifact in its configured approved repositories. If that node
cannot satisfy the exact compatibility constraint, the offline bundle is
checked next. If neither source satisfies it, the operation is `BLOCKED`.
Repository availability is node-scoped: an Execution Node repository is never
treated as a target node repository.

## Explicit DEV acquisition

When a local runtime package closure is absent, DEV acquisition is a separately
confirmed Go operation against a trusted acquisition environment. That
environment's explicitly configured approved repositories acquire the exact
compatible Python/Ansible dependency closure; the existing builder runs there,
and Go transfers the returned bundle to the workstation for verification and
atomic publication. The fresh install target is not used to build the bundle
that bootstraps its own Python/Core. Acquisition is demand-driven; it does not
mirror a repository, change repository configuration or enable public
repositories.

The owner correction supersedes the earlier absolute no-download wording:
installation is repository-first, then offline-bundle fallback, then blocked.
DEV may populate the bundle through explicit acquisition. PROD may install
from a configured node repository, but its distributed offline bundle is
read-only and is never mutated by installation.

The acquisition result contains package identity, platform tuple, local
relative path and digest only. It excludes credential material and repository
URLs.

For DEV-only import of a separately supplied approved service artifact, the
`platform-installer import-artifact` command verifies the regular source file
and expected SHA-256, copies it into a temporary runtime input, sends that
input to the trusted acquisition environment, invokes the same reproducible
bundle builder there, and publishes the verified result through the immutable
cache. The workstation source path is never stored in the bundle, resolver
result or desired state. PROD has no import path and reads only already
published bundle content.

The target repository probe is exposed by the semantic `probe-repository`
operation. It executes a fixed, read-only DNF `repoquery` on the actual target
node, parses package name/version/architecture, and returns
`AVAILABLE_COMPATIBLE`, `AVAILABLE_INCOMPATIBLE`, `NOT_FOUND` or
`REPOSITORY_UNAVAILABLE`. The probe does not choose a source; the existing Go
resolver consumes that single probe result and produces the per-target derived
result. Batch resolution performs one probe per requirement and returns the
target-filtered runtime projection supplied to Ansible; Ansible does not
re-query or select a source. Different nodes may therefore resolve the same
requirement differently.

## Target-side artifact delivery

`ResolvedArtifactSource/v1alpha1` remains the single source-selection result.
When its source is `OFFLINE_BUNDLE`, its immutable artifact entries carry only
a bundle-relative `runtime/...` reference, type, size and SHA-256. The shared
`platform.core.artifact_delivery` role uses the active Execution Node runtime
as the controller-side origin, stages bytes under the fixed target root
`/var/tmp/platform-installer/artifacts`, and verifies target SHA-256 before any
service install task. Repository results do not enter this path.

RPM entries are collected as one local closure and installed with repositories
disabled; archive entries are exposed as staged paths to the owning service
role. Service roles retain extraction, package semantics, configuration,
validation and service lifecycle ownership. Staging names are derived from
the requirement and digest; the controlled cache is retained for digest-aware
repeat applies and is not a persistent desired-state store.

The implementation has focused resolver, metadata, path-safety,
digest-mismatch and repeat-delivery coverage plus real repository-first,
bundle-fallback and blocked-before-mutation RED OS acceptance.

## Production service execution wiring

`executionnode.ServiceExecutionService` is the production entrypoint for the
service path. It collects package-declared requirements, performs one
read-only repository probe per requirement on every install target, calls the
existing resolver and builds target-filtered runtime projections. `Target`
identifies the Execution Node used to run Ansible; `ArtifactTargets` identifies
the actual install nodes whose repository results must remain independent. A
`BLOCKED` projection returns before any Ansible call.

For an allowed projection, `OpenSSHTransport` transfers only standard
Ansible project input and an ephemeral JSON extra-vars file to the Execution
Node, then invokes a fixed service apply/verify playbook. The projection is never written
to inventory, `group_vars` or `host_vars`, and Ansible does not select a
source again. The fixed production allowlist currently covers Kafka and
Keepalived.

## Final acceptance evidence

- The published runtime uses `ansible-core/`, so service playbook relative
  imports resolve inside the immutable bundle. Activation capability checks
  passed; repeated Prepare returned `READY`, `Changed:false`.
- Kafka production E2E: the real target probe returned `NOT_FOUND` for Kafka,
  the resolver selected the verified Kafka 4.3.1 artifact from
  `bundle/artifacts/kafka/`, automatic runtime projection and shared gate ran,
  target SHA-256 verification passed, apply and verify passed, and repeat apply
  returned `changed=0 failed=0`. No Internet download or manual SCP was used.
- Keepalived production E2E: all three actual targets returned
  `AVAILABLE_COMPATIBLE` for 2.4.3, the resolver selected `REPOSITORY`, apply
  and verify passed, repeat apply returned `changed=0 failed=0`, and
  `artifact_delivery` was not invoked.
- BLOCKED acceptance: unsuitable repository plus absent compatible bundle
  stopped the production entrypoint before runtime (`artifact_delivery=0`,
  service mutations=0). The shared Ansible gate independently rejected a
  `BLOCKED` projection before a mutation sentinel.
- Fresh RED OS regression: 177 Core tests and 84 service tests passed; catalog
  and configuration schemas were reproducible; real `validate.yml` passed
  normally and under `sudo unshare -n`; `go test -race ./...` passed with the
  QA-only `golang` toolchain. Windows required only Go and OpenSSH for product
  orchestration and never executed Python/Core.

## Lifecycle

`InspectExecutionNode` is read-only and returns OS/architecture, host-key
state, elevation, disk capacity and installed runtime identity. Host keys are
`UNKNOWN`, `TRUSTED`, `CHANGED` or `REJECTED`; only `TRUSTED` can proceed.
`StrictHostKeyChecking=no` is prohibited.

`PlanExecutionNodePreparation` validates the local bundle and stores a
digest-bound, expiring plan. `Prepare` revalidates both plan and bundle, uses
the common repository-first/bundle-fallback policy for required node
components, stages the verified runtime into a contained versioned location,
verifies it, then atomically switches the active runtime. A failed stage is
discarded; the prior active runtime remains available. An unchanged digest is
not retransferred and returns `Changed=false`.

Readiness states are `UNREACHABLE`, `UNPREPARED`,
`PREPARATION_REQUIRED`, `READY`, `UPDATE_REQUIRED`, `INCOMPATIBLE` and
`BROKEN`. A same-digest ready runtime is a no-change operation. A changed
bundle requires an explicit update plan; a malformed activated runtime is
`BROKEN`, not silently repaired.

## Capability handoff

The first post-activation Core operation is the controller-only
`execution-capabilities.yml` entrypoint. Its
`ExecutionCapabilities/v1alpha1` response names bootstrap protocol, Core,
catalog, schema and runtime/bundle identity plus supported safe operations.
The initial supported operation is only `validate`; UI-BE-04 planning,
execution, events, cancellation persistence and run history remain out of
scope.

## Security and recovery

Bundle and remote paths are fixed by the backend; caller input never becomes a
remote shell destination. Activation is staged and verified before the active
pointer changes. Runtime credentials remain in the existing runtime-only
mechanism and do not enter manifests, plans, capability responses or
diagnostics. Interrupted stages and failed activation are removed without
deleting a known-good runtime.

RED OS is the first acceptance platform. ALT Linux stays unit-tested and
documented as pending compatibility evidence; no platform is certified merely
by this contract.
