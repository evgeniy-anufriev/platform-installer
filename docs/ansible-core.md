# Standalone Ansible Core

## Product contract

Ansible Core must be installable and usable without Platform Installer. A Linux operator must be able to take a portable Ansible project and offline bundle and run the complete lifecycle with standard `ansible-playbook` commands.

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

`platform.core.resolve_application_libraries` is the A1 controller-only library
resolver. Project snapshot/validate entrypoints call it only when application
deployments are declared. It loads validated package defaults using ordinary
Ansible include_vars in independent namespaces and uses built-in recursive combine
with list replacement for composition; Python does not evaluate Jinja or recreate
inventory precedence. Package templates are trusted operator-authored executable
inputs. A1 validates/fingerprints their closure but does not render them or execute
application tasks. See [standalone fixture](../examples/valid/application-libraries/README.md).

A2 adds explicit standalone `application-libraries-apply.yml` and
`application-libraries-verify.yml` entrypoints. They reuse that resolver and the
selected rootless Docker account; template rendering remains native Ansible.
All selected placements pass preflight before materialization. Each library/host
has a shared `.env` and base Compose; per-instance Compose/config files use
validated package render descriptors. Apply uses native Compose and a generated
config-digest ownership label to recover an interrupted configuration activation.
Verify observes files, image identity and readiness without starting or loading
containers. Accounts, Agent, PKI and infrastructure provider hooks remain later
stages. See [runtime fixture](../examples/valid/application-runtime/README.md) and
[A2 evidence](application-libraries/a2-test-journal.md).

Production roles must also work with conventional manual inventory and variables:

```text
manual inventory + group_vars/host_vars -> role
portable project -> resolver -> ordinary resolved role variables -> same role
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

## Project input and resolved projections

The initial portable project is a normal Ansible project:

```text
project/
  project.yml                  # optional machine metadata/compatibility
  inventory/
    hosts.yml                  # desired hosts and normal Ansible groups
    group_vars/all/platform.yml # service topology, endpoints and policies
    group_vars/<group>.yml       # ordinary service/group overrides
    host_vars/<host>.yml         # host/member desired overrides
  ansible.cfg
```

This multi-file layout is one versioned project contract. It avoids a proprietary launcher and does not make the role contract depend on a monolithic Installer DTO.

The Ansible-only user configures inventory and ordinary variables only.
`platform_desired_state` in `group_vars` owns logical deployments and policy;
host `platform_deployments` owns logical members and physical placement.
Generated identities, fingerprints and locks are machine-owned under
`platform_generated_state`, conventionally in
`inventory/group_vars/all/platform-state.yml`. They are not desired
configuration and are never merged back into `platform_desired_state`.

The repository `ansible.cfg` is part of the standalone execution contract.
It requires `hash_behaviour = merge` so inventory policy maps can recursively
overlay role defaults; execution environments must use this configuration.

Core playbooks validate the project and produce an ephemeral resolved workspace:

```text
.runtime/<run-id>/
  inventory/
    hosts.yml
    group_vars/
    host_vars/
  resolved/plan.json
  private/                 # runtime-only, restrictive, cleaned
  events/
  result.json
```

The resolver must:

- validate every reference before generation;
- resolve service modes, member roles and dependencies;
- preserve explicit placements;
- derive named inventory groups deterministically;
- deduplicate endpoints, SANs, ports and dependencies;
- report conflicts instead of silently correcting intent;
- emit stable ordering and canonical fingerprints;
- never write plaintext secrets into ordinary variables.

Generated workspaces are disposable evidence, not editable project state.

## Standard playbook interface

CORE-01 publishes one filesystem playbook entry point. From the installed or
checked-out Ansible Core root, validation uses:

```text
ansible-playbook -i <project>/inventory/hosts.yml playbooks/validate.yml
```

The collection does not currently publish `platform.core.validate`,
`platform.core.plan`, `platform.core.apply` or `platform.core.verify` collection
playbooks. Plan, apply and verify entry points will be named only when their
playbooks exist and their contracts are tested. The contract requires standard
Ansible inventory and automatic inventory-relative loading of normal
`group_vars` and `host_vars`. Playbooks write versioned machine-readable
artifacts separately from human diagnostics and return documented exit
behavior.

A later convenience CLI may wrap these commands, but it remains optional and Ansible Core, projects and roles must work identically without it.

## Plan

The immutable plan contains at least:

- contract, Core and planning-protocol versions;
- stable project identity, project revision and fingerprint;
- relevant catalog/service-definition and artifact-requirement fingerprints;
- phases, actions, dependencies and targets;
- required runtime credential references and purposes;
- reboot requirements;
- warnings and acknowledgements;
- deterministic plan fingerprint.

Planning is target-contact-free and contains no observed facts, repository
probe results or selected package source. `REPOSITORY` versus `OFFLINE_BUNDLE`
is resolved only during execution through the established target-scoped source
resolver.

No executor may introduce an undeclared mutating action.

## Events and results

Ansible callback plugins emit normalized events. Consumers never need to parse decorated stdout.

EXEC-OBS-01 implements the managed `platform.core.execution_events_json`
aggregate callback. The trusted controller enables it and supplies only
semantic identities. The shared `execution_lifecycle` writer resolves paths,
owns cross-process sequence/append/flush and protects critical capacity.
Task-detail failure is best effort and emits one normalized degradation
diagnostic per affected action; critical lifecycle integrity remains
fail-closed. `no_log` task names and all raw module results are excluded.

The Execution Node journal is authoritative. GetEvents returns bounded pages
to Go RunObserver, which maintains the operator's local Installer mirror and
typed subscribers. Local mirror errors cannot change the remote run result.
The existing runtime terminal artifact is `ExecutionResult` with state
`SUCCEEDED`, `FAILED`, `CANCELLED`, `INTERRUPTED` or `CORRUPT_ORPHANED`; richer published result
projections below remain distinct from this private lifecycle artifact.
See [EXEC-OBS-01](exec-obs-01.md) for exact bounds, evidence and operator usage.

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

## Runtime role-variable transfer

Core-derived per-host role variables use `platform.core.runtime_role_variables`
and its narrow action-only `platform.core.apply_runtime_role_variables` adapter.
The adapter copies the current host's validated `platform_*` mapping into facts
without templating individual scalars: integers and boolean-shaped strings retain
their original types independently of Jinja native mode. It has no service rules,
Go dependency, target transport or file writes; it rejects task arguments/invalid
names, reports `changed=false`, and preserves `no_log`. Built-in `set_fact` was
insufficient because non-native mode coerced numbers and strings such as `false`.

## Registered loop-result convention

For ordinary per-member render/copy operations with downstream changed-member
tracking, use the standard Ansible loop variable `item`. Registered results then
retain member identity in `result.item.id`; a tracking loop reads `item.item.id`.
Templates may use a descriptive task-local alias (for example,
`vault_member: "{{ item }}"`) without changing the registered result contract.
Product loops retain their declared tuple shape (for example `item.item[0].id`).
Do not introduce service-specific result extraction into the generic lifecycle.
Explicit custom loop variables remain appropriate where nesting requires them,
but their result consumers must match that explicitly declared contract.

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
