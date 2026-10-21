# Backend and UI boundaries

This document describes the accepted Core/Go boundaries and future UI layers.
UI-BE-04 and EXEC-OBS-01 are implemented; Wails/React remains separately gated.

## Go backend as an anti-corruption adapter

The backend consumes the published Core playbook/artifact protocol through a typed `CoreClient`:

```text
GetCapabilities
ValidateProject  -> playbooks/validate.yml (current CORE-01 filesystem entry point)
BuildDeploymentPlan -> Core-owned plan/private manifest (UI-BE-04B)
StartExecution   -> fixed Execution Node lifecycle (UI-BE-04C)
GetExecution     -> authoritative remote observed state
GetEvents        -> paginated typed events (EXEC-OBS-01)
CancelExecution  -> owned controller cancellation
```

The adapter sends semantic operations to the selected Execution Node and
consumes versioned artifacts. It does not accept a generic invocation, depend
on internal role task names or reconstruct Core decisions.

Recommended ports:

- `ProjectStore`;
- `CoreClient`;
- `ExecutionEnvironment`;
- `SecretBroker`;
- `HostTrustStore`;
- `RunRepository`;
- `ObservedStateRepository`;
- `AuditRepository`;
- `OutputStore`;
- `Clock` and `IDGenerator`.

## Persistence

Application runtime credential input reuses `SetDeploymentRuntimeSecretValues`.
Without `applicationRequirementRef` it retains the full descriptor-set contract.
With this optional field it accepts exactly one Core-issued APPLICATION_SECRET
requirement in the specified application library, bound to current saved
revision, descriptor fingerprint, runtime and node. It merges only that pending
value through the existing Broker. Values never enter structural edit commands.
`GetApplicationRuntimeSecretAvailability` returns presence booleans keyed by
the current evidence's application requirement IDs. It reads pending/lease TTL
without Core discovery, promotion, attachment changes or TTL renewal. Stale
project/revision/runtime/node evidence returns UNAVAILABLE. UI caches are
non-authoritative and discard delayed responses from a previous context.
Application descriptor and in-flight caches bind to the saved revision and
Go-projected Execution Node selection, runtime digest and readiness state.
Changing this identity drops old availability and unsubmitted field values;
late discovery results cannot replace a newer context's descriptors. Context
entry may discover requirements once; periodic presence reads never rediscover.
Explicit descriptor rediscovery keeps the existing attachment invalidation:
it clears already-attached runtime inputs and reattests matching pending inputs.
Page reentry can therefore require new input after earlier pending values have
been promoted; presence polling alone neither clears inputs nor renews TTL.

The managed Ansible project directory—`project.yml`, inventory, `group_vars` and `host_vars`—contains canonical desired state. SQLite, if retained, stores local operational data:

- project index, path, revision and digest;
- execution-environment bindings;
- discovered facts and their expiry;
- trusted host keys;
- disposable local copies of immutable public plans and fingerprints;
- nonauthoritative run/session indexes and sanitized output references;
- audit records;
- non-portable UI preferences.

SQLite must not contain an independently editable copy of topology, endpoints
or TLS desired state. It is not the execution journal: durable run status,
events and terminal result remain authoritative on the Execution Node.

Project save is atomic:

1. receive a document or typed patch with expected revision;
2. validate through Core;
3. reject revision conflict;
4. write affected files to a temporary project staging area;
5. atomically replace the affected canonical files or project revision;
6. update index/digest;
7. publish the new revision.

## Execution environment

Execution-node configuration is local Installer state, not portable
infrastructure intent. Core/Python execute only on the selected trusted Linux
Execution Node; the workstation uses Go and SSH/SCP and is not a Core runtime.
The backend interface is semantic, not a generic Core invocation or a set of
domain-specific playbooks:

```text
GetCapabilities
ValidateProject
BuildDeploymentPlan
StartExecution
GetExecution
GetEvents
CancelExecution
```

There is no remote `RunCommand`, `RunShell`, `RunPlaybook`, `RunAnsible` or
caller-supplied argv/path operation. Execution-node bootstrap and target-host
preparation remain separate workflows.

## Runtime secrets

The backend may keep secrets in an application-scoped memory session so navigation between pages does not lose them. The UI can query only availability states such as `MISSING`, `PRESENT` or `EXPIRED`; it cannot read a stored value back.

Durable integration with an OS credential store, if introduced, is a separate policy and does not alter the portable project contract.

## API shape

Avoid a single adapter with a method per UI button. Use focused command/query facades:

- Project API;
- Catalog API;
- Editor API;
- Execution API;
- Environment API;
- Secrets API;
- Journal API.

Mutating commands carry `expectedRevision`. Read responses use a consistent envelope containing data, revision, findings and a structured safe error.

Core events flow through the existing typed ExecutionEvent envelope.
RunObserver consumes paginated GetEvents and feeds bounded typed subscribers
and a derived Installer-side runtime mirror. Future Wails transports those
subscriptions; React never reads the local file, parses Ansible output or
implements redaction. EXEC-OBS-01 exposes no raw stdout/stderr API.
See [EXEC-OBS-01](work/execution/exec-obs-01.md) for CLI, replay and failure semantics.

## UI project editor

The UI displays the Core catalog and edits the portable project through backend commands.

State ownership:

- backend query cache: project snapshot, catalog, validation, plans and runs;
- one project draft with base revision;
- page-local state: selection, modal, tab and search only;
- active execution: backend-owned and recoverable after navigation/restart;
- secrets: backend session availability only.

The topology editor supports zero to many deployments of every service type. It uses manifest-defined modes, roles, listeners and constraints. A specialized editor may improve complex service UX but cannot redefine the manifest.

## Import and export

Two workflows are planned:

- **Import copy** creates a managed local copy and never mutates the source file.
- **Open workspace** works directly with a standalone project and detects external changes by digest.

Round-trip guarantees semantic preservation, stable IDs and declared extension fields. Byte-for-byte YAML formatting and comments are not guaranteed. Migration is explicit, creates a backup and produces a report; apply never migrates silently.

## V1 components to preserve as behavior

- SSH host-key pinning and `CHANGED` blocking;
- runtime-only credentials;
- precise cancellation;
- interrupted-run reconciliation;
- structured events plus complete sanitized output;
- transactional project deletion ownership;
- audit lifecycle;
- localized safe errors and offline help;
- visual and accessibility testing.

These behaviors should be reimplemented against V2 contracts rather than copied with V1 DTOs.
