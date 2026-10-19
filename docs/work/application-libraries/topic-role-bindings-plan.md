# Kafka resource defaults and application topic roles

Owner accepted the design on2026-10-19: Kafka templates belong in existing
resource_defaults; resources select instances/providers; named application roles
select resource IDs; environment computes ENV from resolved role names. No
application deployment, Kafka mutation, manual grants, new lock or Python script.
Existing dirty SDKU ENV/HTTP-port work is preserved and outside this extension.

## Desired state and compatibility

Library defaults extend resource_defaults.kafka.topics, keyed by stable resource
ID. Entries have the existing Kafka parameter fields: name, partitions,
replication_factor, config. No kind/provider/creation flag is duplicated there.
Templates may be partial; the selected resource must resolve a valid name.
SDKU uses logical IDs main/main_compact/alarms/alarms_compact; their name fields
contain sdku-main*/sdku-alarms*. Shared application packages contain no library
prefix in their topic bindings and can consume the same IDs in a CSPA library.
Selection remains resources.<id>={kind:kafka.topic,binding:messaging,parameters:{}}.
No implicit resource creation from defaults. Matching uses that resource's ID;
there is no defaultsRef, separate catalog, new store or template inheritance tree.

Precedence: package resource_defaults -> library instance resource_defaults ->
resources.<id>.parameters. Recursive config merge, lists replaced as elsewhere.
Existing resources with explicit parameters keep their behavior. Resolved values
are derived, never saved as authored inputs. Existing RF/minISR calculation runs
after this merge against the selected Kafka deployment, independently per resource.
Defaults never bake a broker count or replication setting into application ENV.

New topicBindings shape per connection alias:

```yaml
topicBindings:
  kafka:
    main: main
    main_compact: main_compact
    alarms: alarms
    alarms_compact: alarms_compact
environment:
  MAIN_TOPIC: '{{ application_topics.kafka.main_compact.name }}'
  ALARM_TOPIC: '{{ application_topics.kafka.alarms_compact.name }}'
```

Values are resource IDs, never physical names or list indexes. Role keys come
from application defaults; no SDKU role names are hardcoded in Core/UI. Each
declared selected role must point to an existing Kafka resource on the same
provider as that connection. Multiple roles/apps may share a resource. Empty
selection is a locally saveable incomplete draft, rejected by Core before a plan
can execute. Reset removes the authored role override and restores its default;
it never copies a calculated name. A role cleared explicitly must not fall back
to a different resource silently. Preserve legacy alias->list bindings and their
snapshot/runtime representation for packages that do not use named roles. Do
not infer named roles by position/name or silently migrate saved projects.

## Core

Use existing resolve_application_libraries/instance.yml. Before parameters/ENV
expand, use built-in tasks/filters to merge resource defaults and effective topic
bindings, validate references with safe identity-only diagnostics, and bind
application_topics for that placement. Construct this context from raw job
descriptors, not application_effective or already-rendered ENV; this avoids a
self-reference. Expose resourceId/name for roles; topology/RF/minISR remain in
the existing pure provider projection. Namespace/reset context per placement.

Carry the same normalized resources into the existing resolved row. Existing
resolve_topics/project_application_libraries validates the authoritative complete
projection and supports named maps alongside legacy lists. Runtime templates
receive the corresponding projection under existing application_runtime.topics;
ENV is already resolved from application_topics. Use one merged name for ENV,
resource Apply/Verify, diagnostics and plan fingerprints. No topic lookup at
container start or UI-side name resolution. Missing/wrong-provider references
must stop resolution before ENV rendering or execution, with safe alias/role/ID.
No relaxation of secret, plan-integrity, PKI or source-selection guards.

Extend existing schemas/settings and existing snapshot projections, without a
new public endpoint or duplicate DTO. Retain generic legacy identity compatibility
and the existing file-only ClickHouse schema behavior.

## Go and UI

Go guarded writer accepts Kafka resources inheriting a name and named role maps;
it validates shape/paths, not Ansible precedence, Kafka topology or effective name.
Existing local Save remains node-free. Missing effective configuration is checked
by optional Project Verify and fresh authoritative deployment plan.

Use existing library Resources form: add a Kafka resource from a declared default
ID, choose its existing provider binding, persist parameters only for explicit
differences. Do not save the inherited name on an unchanged form. Allow explicit
name override/reset through the same form. Show resolved name/settings from Core,
with unresolved/stale status when no fresh projection exists. UI may display
declarative default IDs exposed through the existing package view; it does not
parse YAML or calculate effective defaults. No general resource_defaults editor
or ClickHouse-table schema UI is introduced.

Named application roles use select controls filtered to same-provider Kafka
resources, explicit/inherited labels and per-role reset. Legacy list packages
retain the existing checkbox view. Resource labels show ID and Core-resolved
physical name when available. Update current design doc/mockup for these controls;
the old checkbox-only control explicitly said it did not affect ENV, so it cannot
be reused unchanged for named roles. Shared Save/Verify/plan ownership unchanged.

## SDKU and acceptance

Add the four standard Kafka defaults under library resource_defaults; partitions
defaults to1, delete/compact policies preserved. SDKU apps declare only required
roles and derive topic ENV through application_topics; remove literal/redundant
topic parameters. Preserve images, commands, client/group IDs, TLS and port rules.
Document saved-project migration; never rewrite the live project automatically.

Focused tests: defaults/instance/resource precedence and nested config merge;
standalone/cluster RF/minISR; no selection=no creation; rename selected resource
and switch role to another resource; different providers; missing/empty references;
multiple apps/hosts without stale context; explicit ENV override/reset; legacy
lists and existing CH tables; matching names in ENV, resource jobs and plan digest.
Use current-tree RED OS Ansible/Core, relevant Go/vet and frontend tests/build/lint.
Real React/Wails Save/reopen/reset, target-free Verify and fresh plan; no Start.
Updated verified runtime publication/preparation may be needed for changed Core,
through the standard bundle workflow only, with no application installation.

Public/versioned contract extension is HIGH-RISK: one independent FULL PLAN review
before implementation/presentation, and one FULL DIFF review after implementation,
under docs/agent-procedures/review.md. BLOCK stops for owner disposition; any
TARGETED_RECHECK requires owner approval. Reviews do not authorize target mutation.
