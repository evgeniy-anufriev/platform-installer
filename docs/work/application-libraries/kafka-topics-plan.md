# Kafka topics as library resources — implementation plan

Status: owner approved implementation on 2026-10-17; implementation and bounded
Kafka/Core/UI QA complete; TARGETED_RECHECK APPROVE, zero blockers.
FULL PLAN APPROVE_WITH_CHANGES, no blockers; KTP-P01 clarified below.
Owner's per-deployment standalone/cluster calculation clarification included.
Application installation on servers is explicitly excluded.
Owner request: create topics at the library-resource stage, calculate replication
factor/minISR automatically, default partitions to 1, allow custom settings, and
select topic bindings for application instances using existing Core/UI flows.

## Existing paths and bounded extension

Extend `resources` in the application-library deployment contract with
`kind: kafka.topic`. Keep `binding`, `parameters` and `mode: managed|existing`.
The current provider projection and libraryJobs/instanceJobs stages cover
PostgreSQL/ClickHouse resources and Redis accounts; add Kafka library jobs there,
not a second execution pipeline. Extend the existing Kafka package capabilities.
Reuse resolved Kafka broker/listener/PKI projections and the existing Kafka CLI
connection/configuration patterns (`kafka_kraft/tasks/resolve_cli_connection.yml`,
`run_cli_command.yml`, `schema_registry_topic.yml`). The generic CLI runner is
read-only; creation must remain an explicitly mutating task.

Core owns effective values, provider selection, validation and execution. Go
extends the current guarded application-library writer/adapter only. React edits
the portable contract and shows Core calculations; it does not count brokers or
implement Ansible precedence. No new database, ownership registry, scheduler,
lock or production Python script is planned. Small edits to existing Python
projections are necessary for target-free snapshot/plan semantics; target work
uses ordinary Ansible tasks and bundled Kafka CLI tools.

## Portable desired state

```yaml
platform_desired_state:
  applicationLibraryDeployments:
    sdku:
      bindings:
        messaging:
          deploymentRef: kafka-main
      resources:
        telemetry:
          kind: kafka.topic
          binding: messaging
          mode: managed
          parameters:
            name: sdku.telemetry
            # partitions omitted => 1
            # replication_factor omitted => automatic
            config:
              retention.ms: "604800000"
              # min.insync.replicas omitted => automatic
      applications:
        data-manager:
          overrides:
            topicBindings:
              kafka: [telemetry]
```

Here `kafka` is the application's existing declared connection alias, whose
`library_binding` points to `messaging`. `telemetry` is a resource ID within
this library, not a topic name or a second connection definition.

Resource parameters:

- `name`: Kafka topic name, using Kafka naming rules rather than SQL identifiers.
- `partitions`: optional positive integer, default 1.
- `replication_factor`: optional positive integer; absence means automatic.
- `config`: ordinary topic-property map; `min.insync.replicas` is the single
  persisted key for minISR. Other Kafka topic properties are passed unchanged
  as values, without an Installer allowlist. UI converts scalar input to the
  Kafka property representation; no duplicate `minISR` field is persisted.

Library resources stay in ordinary group_vars. The fixed partitions default and
automatic policy are documented service defaults, resolved through the existing
Ansible/Core path. Explicit resource parameters override these defaults; resolved
numbers are never saved back as authored values. Do not put instance selections
in library slots or shared ENV. Optional application-package topicBindings defaults
follow existing application-default/instance-override semantics. Per-connection
lists replace inherited lists; `[]` explicitly selects none, removing an override
restores defaults. Reset removes a value rather than copying the current default.

## Automatic values

Resolve the Kafka deployment independently for every resource through its library
binding. Automatic values depend on that deployment's mode and resolved topology,
never on all Kafka deployments in the project or on the application's placement.
For `kraft-standalone`, automatic RF=1 and minISR=1. For `kraft-distributed`, let B be the count of
resolved members with the broker role in this deployment. Controller-only members
and the number of physical hosts do not count. Use the same resolved mode and
broker membership as Kafka itself; never recount or infer mode in Go/UI.

`effective RF = explicit replication_factor, otherwise 1 for standalone or min(3, B) for a cluster`.
`effective minISR = explicit config.min.insync.replicas, otherwise min(2, effective RF)`.

| Selected Kafka deployment | Partitions default | Automatic RF | Automatic minISR |
| --- | --- | --- | --- |
| standalone | 1 | 1 | 1 |
| cluster, 1 broker | 1 | 1 | 1 |
| cluster, 2 brokers | 1 | 2 | 2 |
| cluster, 3 or more brokers | 1 | 3 | 2 |

This follows the existing Registry policy for automatic values while basing
minISR on the effective, possibly overridden RF. For example RF=1 gives minISR=1.
With two replicas, minISR=2 favors acknowledgement durability; an operator can
explicitly choose 1. minISR's producer acknowledgement protection requires
`acks=all`; do not silently change producer ENV or application settings.

Values come from desired/resolved topology, not the transient number of reachable
brokers. Missing members never silently weaken replication. Snapshot/plan remain
target-free; apply preflight checks actual Kafka connectivity/capability. Validate
types, positive counts, valid names, provider compatibility and satisfiable RF.
Do not invent topic-config deny policies; version-specific config validity is
checked by Kafka, with safe diagnostics. A manually chosen minISR above RF should
be shown as an ineffective configuration warning, not a new Installer deny rule.

## Instance binding and UI

Add `topicBindings` to existing application settings/override schema, writer keys
and typed projections. Resolve IDs only inside the instance's library and require
the resource's Kafka provider to match the selected declared Kafka connection.
The same topic can be selected by several instances; create it once per library
resource, not per placement/container. Empty selections do not delete topics.

Project resolved topic names under `application_runtime.topics`, grouped by
connection alias, with resourceId/name/deploymentRef. Snapshot exposes equivalent
read-only resolved binding data. Package templates can use this projection in
their existing ENV/config templates; do not guess application ENV variable names
or silently rewrite SDKU topic settings. Bindings select resources; they do not
grant Kafka ACLs or subscribe a running consumer.

Library screen: extend `ApplicationLibraryResources` in its existing grouped
resources section. Add Kafka topic, Kafka binding, name, partitions, automatic/
explicit RF and minISR, and a compact key/value editor for other topic properties.
Show actual Core-resolved RF/minISR and their source; distinguish an unresolved
preview from a calculated value. Reuse draft → Review → Save and Reset.

Instance Startup: add a small topic selector grouped by declared Kafka connection.
Reuse the resource-ID selection pattern of databaseAccess and existing override
commands; no new tab, account type or alternate Save path. Show only compatible
resources, selected topic names and inheritance/reset state. UI calculations and
infrastructure policy remain in Core. Existing design has no topic editor: record
these bounded additions in the production mockup/design before implementation.

## Ansible apply and verify

1. Existing projection prepares one resource batch per library/Kafka deployment,
   independent of the number of application replicas. Include these resources,
   resolved settings and bindings in the existing plan/fingerprint path.
   Reuse the existing provider `claim` check for physical `(deploymentRef, topic name)`
   identity across resource IDs/libraries. Resolve conflicting declarations before
   mutations, especially different partitions/RF/config for the same physical topic;
   do not create one declaration and only then discover the conflict in another.
   Preserve the existing managed/existing conflict semantics without a new registry.
2. Before provider mutations, discover the projected Kafka CLI execution candidate,
   installed CLI path and matching listener/security context. Use existing runtime
   PKI/credential custody; no guessed address, port or plaintext fallback.
3. Describe requested topics and effective requested configs. Reuse native filters
   and CLI patterns; match a literal topic name, including dots, exactly. Distinguish
   a missing topic from authorization, TLS, timeout or broker errors.
4. `managed`: create missing topics using `ansible.builtin.command` with `argv`,
   explicit partitions/RF and repeated `--config` arguments. Execute on one selected
   candidate per provider, after resource preflight and before instance provisioning
   and containers. Re-describe after create, including concurrent already-exists
   responses, and compare actual state rather than trusting a successful return code.
5. `existing`: never create or modify; require the requested topic/properties.
   A matching pre-existing topic may be reused in either mode. This first milestone
   only creates missing topics and verifies requested state; it does not claim
   ownership or alter/delete existing topics. Mismatching existing state produces
   a precise drift finding before further provider mutations. No reassignment,
   partition decrease/increase, config reconciliation or delete/recreate engine.
6. Add topic checks to `application-libraries-provider-verify-stage.yml`, sharing
   the same resolved projection and comparisons. Verify is read-only. Compare
   partition count, every partition's replica count and requested effective configs;
   unrelated broker defaults are not drift. Report unavailable replicas distinctly
   from a different configured RF. Apply reruns are unchanged for matching topics.

Use file mode 0600 and existing bounded cleanup for temporary CLI configuration.
Keep credentials and private material under established runtime custody. Diagnostics
show provider/topic, operation, expected/observed values and sanitized failure code;
never passwords, command-config content, record payloads or unfiltered CLI output.
Resource failures remain application-stage failures and do not revoke saved Infra
Verify. The explicit Infra Verify skip never skips topic preflight or verification.

## Implementation sequence and acceptance

1. Extend canonical schemas, Kafka capability metadata and existing Core projections;
   add resolved topic settings/bindings to snapshot, runtime and plan fingerprints.
   Old projects without topics retain their behavior; unsupported runtimes must
   refuse the feature through existing capability/contract negotiation rather than
   silently omit resource jobs. Confirm the smallest necessary version changes.
2. Add the small Kafka application_provider task sequence and wire existing apply/
   provider-verify stages. Reuse Kafka package variables/projections and installed
   distribution tools; no artifact downloads or separate Kafka client runtime.
3. Extend current Go writer/adapter/Wails models, resource form and Startup selector.
   Update affected design/mockup, project contract, Kafka/Core docs and roadmap.
4. Test standalone and cluster 1/2/3/4+ broker cases, controller exclusion, same-host broker members,
   manual RF/minISR/partitions/config, inheritance/reset, wrong/missing resource refs,
   multiple providers and multiple apps selecting one topic, and absence of topics.
   Include two resource IDs with one provider/topic name, matching and conflicting
   parameters, and assert conflicts are found before any topic creation.
   In one project/library bind separate topics to standalone and clustered Kafka
   deployments and assert independent RF/minISR; changing a topic's binding must
   recalculate only against its selected deployment and change the plan fingerprint.
5. Native Kafka QA: create + repeated unchanged apply; matching pre-existing/existing
   mode; missing existing topic; name/config/partition/RF drift without alteration;
   custom topic properties; literal dotted names; TLS/error diagnostics and secret
   exclusion. Verify changes no resources; failures preserve infrastructure evidence.
6. Real React/Wails acceptance: resource CRUD and binding Save/reopen/reset, Core
   calculated values, fresh Build/Review fingerprints and runtime compatibility.
   Actual topic creation/Verify needs separately authorized bounded Kafka QA;
   no application installation is required to test resource creation. No servers,
   bundle publication/preparation or applications are changed during this planning step.

Risk classification: HIGH-RISK DIFF because provider mutations and the public
application contract change. One independent FULL PLAN review before owner approval;
one FULL DIFF review after implementation; existing BLOCK/targeted recheck budget.
No implementation starts until the owner approves the plan. No new milestone or
target operation is inferred from this document.

Reference: [Apache Kafka 4.3 topic configs](https://kafka.apache.org/43/configuration/topic-configs/)
documents per-topic properties and min.insync.replicas/acks=all behavior.
