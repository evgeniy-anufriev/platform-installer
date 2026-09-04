# Backend and UI boundaries

This document defines the layers that will be designed in detail only after the standalone Core contract is stable.

## Go backend as an anti-corruption adapter

The backend consumes the published Core playbook/artifact protocol through a typed `CoreClient`:

```text
GetCapabilities
ValidateProject  -> playbooks/validate.yml (current CORE-01 filesystem entry point)
BuildDeploymentPlan -> deferred to UI-BE-04B
StartExecution   -> deferred to UI-BE-04C
GetExecution     -> deferred to UI-BE-04C
GetEvents        -> deferred to UI-BE-04C
CancelExecution  -> deferred to UI-BE-04C
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

Core events flow through one versioned envelope. Raw stdout/stderr remains a separate sanitized diagnostic stream and is never interpreted by React.

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
