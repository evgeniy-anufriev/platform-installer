# Standalone Ansible Core

## Product contract

Ansible Core must be installable and usable without Platform Installer. A Linux operator must be able to take a portable project and offline bundle and run the complete lifecycle from a documented command surface.

The lifecycle is:

```text
inspect -> validate -> plan -> apply -> verify -> result
```

`apply` requires an exact validated plan fingerprint or generates and confirms it within one controlled standalone session. It may not silently execute a different intent.

## Proposed distribution layout

```text
platform-ansible-core/
  ansible_collections/platform/installer/
    plugins/
      callback/
      inventory/
      modules/
    roles/
      common_prerequisites/
      target_preparation/
      <production-service>/
    playbooks/
      discover.yml
      plan.yml
      deploy.yml
      verify.yml
  catalog/
    services/<type>/manifest.yml
    services/<type>/schema.json
    compatibility/
  schemas/
    project-v1.schema.json
    plan-v1.schema.json
    event-v1.schema.json
    result-v1.schema.json
  artifacts/
    manifest.yml
  examples/
  bin/
  docs/
```

This is a design target, not yet an implemented tree. Packaging may refine it without changing contracts.

## Service package

Each service type is a cohesive, versioned package:

- manifest with identity, modes and capabilities;
- configuration schema and safe defaults;
- topology constraints;
- declared listeners and dependency kinds;
- role entry points;
- validation and verification contract;
- offline artifacts and compatibility declarations;
- standalone fixtures and integration tests.

A service manifest describes capability, not project intent. A project can instantiate the service type zero, one or many times.

## Role contract

Production roles must also work with conventional manual inventory and variables:

```text
manual inventory + group_vars/host_vars -> role
portable project -> compiler -> generated inventory/vars -> same role
```

Rules:

- service-prefixed variables;
- required inputs asserted early;
- no Installer database IDs or DTOs;
- deterministic templates;
- OS mappings isolated from generic orchestration;
- idempotent second execution;
- handlers only on meaningful change;
- no undeclared network downloads;
- `no_log` and restrictive temporary files for sensitive operations;
- safe structured failure plus retained sanitized stdout/stderr.

## Compiler and projections

The portable project is compiled into an ephemeral workspace:

```text
.runtime/<run-id>/
  inventory/hosts.yml
  group_vars/
  host_vars/
  resolved/plan.json
  private/                 # runtime-only, restrictive, cleaned
  events/
  result.json
```

The compiler must:

- validate every reference before generation;
- resolve service modes, member roles and dependencies;
- preserve explicit placements;
- derive named inventory groups deterministically;
- deduplicate endpoints, SANs, ports and dependencies;
- report conflicts instead of silently correcting intent;
- emit stable ordering and canonical fingerprints;
- never write plaintext secrets into ordinary variables.

Generated workspaces are disposable evidence, not editable project state.

## Commands

The final launcher technology is deferred. Its behavioral interface is stable:

```text
platform-ansible inspect <project>
platform-ansible validate <project> [--facts <snapshot>]
platform-ansible plan <project> [--facts <snapshot>] --output <plan>
platform-ansible apply <project> --plan <plan> --secrets-provider <provider>
platform-ansible verify <project> [--result <path>]
```

Commands return documented exit codes and write machine-readable outputs separately from human diagnostics. The launcher must run on the supported Linux execution environment and remain callable directly by operators and by the future Go adapter.

## Plan

The immutable plan contains at least:

- contract and Core versions;
- project fingerprint;
- catalog and artifact lock fingerprints;
- facts snapshot references and freshness;
- phases, actions, dependencies and targets;
- required runtime credentials;
- expected package sources;
- reboot requirements;
- warnings and acknowledgements;
- compatibility evidence;
- deterministic plan fingerprint.

No executor may introduce an undeclared mutating action.

## Events and results

Ansible callback plugins emit normalized events. Consumers never need to parse decorated stdout.

Event identity includes:

- schema version;
- run, phase, action, host and service deployment identifiers when applicable;
- task state and elapsed time;
- safe message and structured error code;
- redaction metadata.

Final result includes:

- `SUCCESS`, `PARTIAL`, `FAILED`, `CANCELLED` or `INTERRUPTED`;
- outcomes by phase, host and action;
- changed/reboot-required summaries;
- verification findings;
- references to sanitized full diagnostics;
- exact Core, collection, role, payload and artifact versions.

## Secrets

The standalone Core accepts secrets through a replaceable runtime provider, initially protected files, environment-owned descriptors or Ansible Vault where explicitly configured. The portable project contains only references and required-secret metadata.

Secret values must not appear in:

- project YAML;
- generated normal inventory variables;
- plan or result;
- events;
- command-line arguments;
- audit or diagnostics.

## Offline trust

SHA256 provides integrity but not authenticity. Artifact and Core manifests therefore use a signature-neutral envelope with:

- manifest format version;
- payload identifiers and hashes;
- signer/key identifiers;
- signature records as extensible data;
- verification policy and evidence output.

The concrete signature technology can be selected later without changing artifact lookup or project semantics.
