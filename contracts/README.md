# Published contracts

This directory contains the machine-readable contracts shared by standalone
Ansible Core, service packages and future Installer adapters. The contracts do
not depend on Go, Wails, SQLite or a proprietary launcher.

## Published versions

Versions have distinct scopes and can coexist. A listed schema does not prove
an activated runtime supports it or that its application flow passed acceptance.
The standard Core deployment planner emits `plan/v1alpha2`; `plan/v1alpha3`
adds `selectedSourceDeployment` and `targetScope` in its separate schema.
Use the exact runtime capability/binding for execution compatibility, not the
highest version number in this directory.

| Contract | Version | Schema |
| --- | --- | --- |
| Project manifest (`project.yml`) | `v2alpha1` | `project/v2alpha1/project-manifest.schema.json` |
| Project desired topology (`platform_project`) | `v2alpha1` | `project/v2alpha1/desired-state.schema.json` |
| Host desired variables (`platform_host`) | `v2alpha1` | `project/v2alpha1/host-desired-vars.schema.json` |
| Assembled project validation input | `v2alpha1` | `project/v2alpha1/assembled-project.schema.json` |
| Installer application configuration | `v1alpha1` | `application-config/v1alpha1/schema.json` |
| Project edit command (compatibility) | `v1alpha2` | `project-edit/v1alpha2/schema.json` |
| CreateServer command with required type | `v1alpha3` | `project-edit/v1alpha3/schema.json` |
| Server CRUD command with required desired hostname | `v1alpha4` | `project-edit/v1alpha4/schema.json` |
| Server and topology edit commands | `v1alpha5` | `project-edit/v1alpha5/schema.json` |
| Server, topology and provider edit commands | `v1alpha6` | `project-edit/v1alpha6/schema.json` |
| Server, topology, provider and PKI edit commands | `v1alpha7` | `project-edit/v1alpha7/schema.json` |
| Server, topology, provider, PKI and scoped service configuration edit commands | `v1alpha8` | `project-edit/v1alpha8/schema.json` |
| Server, topology, provider, PKI, scoped service configuration, host placement priority and portable project resource-setting edit commands | `v1alpha10` | `project-edit/v1alpha10/schema.json` |
| Local structural Save plan/result | `v1alpha1` | `project-save/v1alpha1/schema.json` |
| Derived saved-revision verification | `v1alpha1` | `project-verification/v1alpha1/schema.json` |
| Service package manifest | `v1alpha1` | `service-manifest/v1alpha1/schema.json` |
| Derived service catalog | `v1alpha1` | `service-catalog/v1alpha1/schema.json` |
| Finding | `v1alpha1` | `finding/v1alpha1/schema.json` |
| Project validation result | `v1alpha1` | `validation-result/v1alpha1/schema.json` |
| Resolved service configuration | `v1alpha1` | `resolved-service-configuration/v1alpha1/schema.json` |
| Resolved plan | `v1alpha1` | `plan/v1alpha1/schema.json` |
| Target-free deployment plan | `v1alpha2` | `plan/v1alpha2/schema.json` |
| Selected-source deployment plan with explicit target scope (schema) | `v1alpha3` | `plan/v1alpha3/schema.json` |
| Normalized execution event | `v1alpha1` | `event/v1alpha1/schema.json` |
| Execution result | `v1alpha1` | `result/v1alpha1/schema.json` |
| Execution node selection | `v1alpha1` | `execution/v1alpha1/schema.json` |
| Execution runtime capabilities (compatibility) | `v1alpha1` | `execution-capabilities/v1alpha1/schema.json` |
| Credentialed execution runtime capabilities | `v1alpha2` | `execution-capabilities/v1alpha2/schema.json` |
| Runtime service-secret descriptor capabilities | `v1alpha3` | `execution-capabilities/v1alpha3/schema.json` |
| Credentialed execution Start request | `v1alpha2` | `execution-start/v1alpha2/request.schema.json` |
| Credentialed execution Start response | `v1alpha2` | `execution-start/v1alpha2/response.schema.json` |
| Target credential lease request | `v1alpha1` | `runtime-secret-lease/v1alpha1/request.schema.json` |
| Target credential lease response | `v1alpha1` | `runtime-secret-lease/v1alpha1/response.schema.json` |
| Secret output delivery request | `v1alpha1` | `secret-output-delivery/v1alpha1/request.schema.json` |
| Secret output safe control response | `v1alpha1` | `secret-output-delivery/v1alpha1/response.schema.json` |
| Secret output discovery metadata | `v1alpha1` | `secret-output-delivery/v1alpha1/metadata.schema.json` |
| Trusted secret output declaration | `v1alpha1` | `secret-output-delivery/v1alpha1/declaration.schema.json` |
| Typed input capability | `v1alpha4` | `execution-capabilities/v1alpha4/schema.json` |
| Service-configuration-preview capability | `v1alpha5` | `execution-capabilities/v1alpha5/schema.json` |
| Ordered deployment-planning capability | `v1alpha6` | `execution-capabilities/v1alpha6/schema.json` |
| Typed safe input descriptors | `v1alpha2` | `runtime-secret-descriptors/v1alpha2/schema.json` |
| Typed credential payload | `v1alpha4` | `target-credential-payload/v1alpha4/schema.json` |
| Typed input lease request | `v1alpha2` | `runtime-secret-lease/v1alpha2/request.schema.json` |
| Typed input lease response | `v1alpha2` | `runtime-secret-lease/v1alpha2/response.schema.json` |
| Trusted service input metadata | `v1alpha1` | `service-secret-inputs/v1alpha1/schema.json` |

Execution selection is project/execution state, not service topology. Candidate
eligibility is evaluated before preparation; `EXECUTION_READY` is reported only
after Python, Ansible, workspace, offline payload and execution identity are
prepared. Target bootstrap is a separate phase and may skip a self-target when
the selected Execution Node uses explicit `ansible_connection: local`.

All schemas use JSON Schema 2020-12 and validate YAML after YAML-to-JSON data
model conversion.

Application configuration is local Installer product behavior, not portable
infrastructure desired state. The project persists only the selected stable
server type ID under `platform_host.type`; its schema validates ID grammar and
does not copy or enumerate the local configured list.

The structural Save contract reports only typed local changes and guarded
filesystem persistence; it contains no Core validation claim. Project
verification is derived runtime evidence for one exact saved revision and is
not portable desired state or execution authorization.

## Versioning

- `apiVersion` selects a contract version; readers reject unsupported versions.
- Alpha versions may change incompatibly, but never silently during `apply`.
- A migration is an explicit, deterministic operation that retains an original
  backup and reports its source and destination versions.
- A stable contract adds compatible optional fields within a major version and
  uses a new major version for incompatible semantic changes.
- Plans and results record the exact project, catalog, artifact and Core
  fingerprints used to create them.

## Extension preservation

Objects intended as extension boundaries accept properties named `x-*`.
Readers and writers must preserve their parsed YAML values semantically even
when the extension is unknown. Field ordering, comments, anchors, scalar style
and byte-identical formatting are not contractual. Unknown properties without
the `x-` prefix are rejected so that misspellings do not silently become
desired state.

## Project directory boundary

The portable contract is intentionally split across ordinary Ansible project
files:

```text
project/
  project.yml
  inventory/
    hosts.yml
    group_vars/all/platform.yml
    group_vars/<group>.yml
    host_vars/<host>.yml
  ansible.cfg
```

Inventory, `group_vars` and `host_vars` remain ordinary Ansible inputs. Host
keys referenced by explicit member placements must exist in the supplied
inventory; that cross-file invariant is checked by Core validation rather than
JSON Schema.

`project.yml` is the only owner of project identity and contract/lock versions.
The value of `platform_project` in `inventory/group_vars/all/platform.yml` contains only
desired topology and policy; it does not repeat project identity or
`apiVersion`. Each `inventory/host_vars/<host>.yml` may expose desired host data under
`platform_host`. The assembled-project schema describes the normalized input
to validation and fingerprinting; it is derived and is not a fourth persisted
project representation. `project/v2alpha1/schema.json` is a convenience alias
for that assembled schema.

## Catalog ownership

Service package manifests are the only authored source of service modes,
roles, placement constraints, listeners and configuration schemas. A CORE-01
service catalog is a derived, fingerprinted artifact whose definitions embed
complete conforming manifests. Projects pin catalog and per-service manifest
digests; projects do not copy catalog definitions into group vars. A referenced
manifest representation is deferred until Core has a defined, tested resolver
for it.

## Runtime schema enforcement status

The schemas are the published contract, but CORE-01 has not yet selected or
bundled a Draft 2020-12 runtime validation dependency. The current dependency-
free manual validator enforces only its documented CORE-01 semantic subset; it
must not be described as full JSON Schema enforcement. The current contract
check is limited to dependency-free JSON syntax and local-reference existence
checks. Semantic tests cover only the explicitly implemented subset until an
offline-safe runtime dependency is approved and bundled.

## Secret boundary

Published desired-state schemas contain only secret requirements and provider
references. Secret values belong to the runtime provider and must never be
written into project files, plans, events or results. JSON Schema establishes
the data shape; Core also performs semantic redaction and forbidden-value
checks.

## Credentialed execution compatibility

`ExecutionCapabilities/v1alpha1` remains immutable and supports existing
readiness and planning behavior. It never authorizes credentialed execution.
`ExecutionCapabilities/v1alpha2` adds only feature negotiation: it requires
`executionStart.protocol = StartExecution/v1alpha2` and may advertise the
closed `targetCredentialLease` capability. The latter names the fixed lease
protocol, its sole payload version, a bounded maximum payload size and the
required Start protocol; it does not carry a secret or redefine either wire
protocol.

`StartExecution/v1alpha2` rejects caller-supplied `runId`. The Execution Node
generates that ID after durable start-attempt and lease attachment. A private
lease ID is permitted only on the trusted Go-to-Execution-Node wire and is not
a desired-state, Wails or React value. A v1alpha2 reply without a compatible
lease capability remains usable for planning, but credentialed Start is
blocked without fallback to v1alpha1 or direct workstation-to-target SSH.

`ExecutionCapabilities/v1alpha3` preserves v1alpha2 and adds only the closed
`runtimeSecretDescriptors` capability and the fixed v1alpha1/v1alpha2/v1alpha3
lease-payload sequence. Older envelopes remain immutable and cannot authorize
descriptor retrieval or a service-secret Start path.

`ExecutionCapabilities/v1alpha4` preserves the planning and Start semantics and
advertises only the typed-input pair `BuildRuntimeSecretDescriptors/v1alpha2`
and `PutRuntimeSecretLease/v1alpha2` with its sole
`TargetCredentialLeasePayload/v1alpha4`. Lease v1alpha2 rejects every other
payload generation; lease v1alpha1 remains unchanged and cannot authorize the
typed-input path. Capability v1alpha4 is emitted only by a runtime that
implements the corresponding descriptor, lease admission, manifest binding,
and operation-scoped Ansible projection.

## Application libraries preparation (A7)

Nonempty application libraries use `plan/v1alpha4` and
`runtime-secret-descriptors/v1alpha3`. Infrastructure-only plans and descriptors
retain their existing versions. Application input descriptors contain public
source refs and library/host scopes; credential values remain in the existing
typed lease and private run custody. Unknown snapshot or image-lock versions fail
closed. Registry availability and concrete source selection are execution state,
never target-free plan identity.

`execution-manifest/v1alpha2/application-operation.schema.json` is a closed
preparation fragment for the two fixed existing application playbooks. A7 does
not publish a full application execution manifest or advertise application Start
capability. Application-aware production plans remain BLOCKED until the A8
all-infrastructure Verify barrier. Existing infrastructure capability negotiation
and Start protocols are unchanged.

A8 completes `execution-manifest/v1alpha2/schema.json` for one mixed run. The
application suffix follows every infrastructure Apply/Verify. Plan v1alpha4
includes all Verify dependencies. `execution-runtime/v1alpha3` Build requests
carry a closed runtime-only `applicationVaultSources` map (provider to
RUNTIME_INPUT or CURRENT_RUN_BOOTSTRAP); absent entries select RUNTIME_INPUT.
This is execution-source metadata, not library desired state or a UI field.
Old v1alpha2 Build consumers do not receive application plans silently.

GetCapabilities with request v1alpha3 returns capability v1alpha7; established
requests retain v1alpha6 and infrastructure behavior. Mixed Start remains
StartExecution/v1alpha2 with the same typed lease and trust protocol. Bootstrap
tokens are excluded from preexisting lease values and copied from exact current
run/provider protected output only after the infrastructure barrier. Durable
output delivery and temporary runtime input cleanup keep their existing rules.

## B0 infrastructure Verify reuse

`execution-runtime/v1alpha4/build-deployment-plan.schema.json` adds an explicit
fixed executionMode. Capability v1alpha8 advertises the three supported scopes;
plan/v1alpha5 and execution-manifest/v1alpha3 bind the Core-derived infrastructure
model and evidence revision. Earlier versions retain their established meaning.
Library-only and Verify-only do not imply selective infrastructure Apply support.
See [execution contract](../docs/contracts/execution-planning-and-events.md#b0-cross-run-infrastructure-verification).
