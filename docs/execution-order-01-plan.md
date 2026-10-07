# Execution Order 01 — Service priorities and apply/verify sequencing

## Status

Implementation in progress. On 2026-10-07
the owner clarified equal-priority ordering and decided that base HAProxy and
BIND Apply must not consume endpoints belonging to later services. Endpoint
integration and its health proof belong to the source service's own Apply.
This is a prerequisite
change to the current Ansible/Core lifecycle, not permission to remove a Core
dependency before the role behavior is changed and tested. No execution-order
production change is currently in effect.

## Design review (2026-10-07)

1. **Equal-priority rule resolved by owner clarification.** For different
   service types with the same numeric priority, use their written order in
   `config/application.yml`. Therefore `serviceExecutionPriorities` must be
   an ordered sequence of unique service-type entries, not a YAML mapping or
   Go map. Multiple deployments of the same type have the same list position;
   use deployment ID ascending as the deterministic final tie-break. No
   baseline plan projection or second topological ordering is needed. Core
   still validates every declared dependency and blocks a conflicting order.
2. **HAProxy lifecycle split required by owner decision.**
   `_service_dependencies` requires an HAProxy provider deployment to apply
   after any source deployment explicitly related to it through `haproxy`.
   The proposed table puts HAProxy at priority 3 and Vault/ClickHouse at 4.
   An endpoint relation between them would therefore make the default order
   fail Core's mandatory dependency check. The owner asked to check whether
   this edge is obsolete. It is not: HAProxy `prepare.yml` selects the full
   managed backend model, probes each backend's actual TLS identity and fails
   if a backend is unavailable; `activate.yml` then publishes that full graph.
   Simply deleting the Core edge today would allow HAProxy Apply before a
   fresh Vault/ClickHouse backend is ready and break installation. The owner
   instead requires base HAProxy Apply to install/activate HAProxy atomically
   without consuming service backend definitions. Each endpoint source must
   integrate and verify its own endpoint during its Apply. The old
   provider-after-source dependency can be removed only in the same verified
   change that establishes this new lifecycle.
3. **BIND serial, recovery and deletion policy resolved by owner.** Before an
   explicit full reconcile replaces a dynamically updated zone, synchronize
   the journal and use the SOA serial actually served as the lower bound for a
   validly newer candidate. A per-zone machine-runtime marker plus guaranteed
   thaw/recovery checks covers interruption; the marker is removed only after
   authority and update ability are proven. Point updates never delete a
   service record when its endpoint is removed or unlinked; deletion remains
   exclusively part of the existing explicit full reconcile.

## Endpoint lifecycle prerequisite to execution ordering

- Base HAProxy Apply owns package, TLS material, base listeners and atomic
  publication of its own configuration, including endpoint-group/domain ACLs
  and the existing generic Host-to-backend rule. Derive these shared rules
  directly from the configured `endpointGroups`, not from service endpoints
  or a provider's currently installed backends. The current `10-public.cfg.j2` derives the
  groups from `endpoints.endpoints.values()`; that input must change before
  HAProxy can safely Apply ahead of the services. There is no Vault-specific
  public routing rule. Base Apply must not select/probe/render all
  application backends from the project. It must preserve already installed
  backend fragments when updating the base provider; a later source-service
  Apply must not require rerunning base HAProxy Apply.
- Base BIND Apply owns package, authoritative zone configuration, SOA,
  required project-host records and configured endpoint-group wildcard records.
  A wildcard belongs to the provider/group and is created during BIND base
  Apply only when the existing `endpointGroups.<id>.address.wildcard` option
  is `true`; a source-service Apply never publishes or changes a wildcard.
  It must not render or publish exact endpoint records for services that have
  not reached their own Apply. Its Verify checks base authority/host/wildcard
  records, not future exact service records. Base Apply preserves existing
  service records and does not reset their serial/fingerprint history. A later
  source Apply must not rerun base BIND Apply. Removing or unlinking a service
  endpoint does not issue a point-delete: the DNS record remains until an
  operator explicitly invokes the existing full `reconcile.yml` operation.
- A service with an endpoint invokes one generic integration path after its
  service process becomes healthy. That path resolves the *current source
  deployment's* authoritative DNS/backend projection, publishes only its
  owned records/fragments, and then tests the actual endpoint. It cannot
  activate or probe backends of later, not-yet-installed services. Failures
  stop that service's Apply, so the next deployment cannot start. No
  service-specific branches belong in Core, Go or React. The selection key is
  the existing `platform_execution_service_deployment` provided by the
  controller; direct standalone callers provide the documented deployment ID
  through ordinary Ansible variables. Filtering only by `serviceType` is
  insufficient when multiple deployments share a package. The generic path
  uses the existing Core endpoint/provider resolution, not a second endpoint
  model or a hardcoded service-type list.
- The service's Verify remains read-only and checks its endpoint again. A
  source without an endpoint does not trigger provider integration. Standalone
  Ansible Apply/Verify must work through the same path without Installer.
- PostgreSQL is endpoint-free in the supported service workflow. Its normal
  Apply/Verify must not invoke BIND/HAProxy provider updates or require an
  endpoint relation. The legacy integration import is removed from PostgreSQL
  Apply; provider full reconciliation remains explicit and opt-in.
- The existing explicit full provider `reconcile.yml` remains a separate
  complete-model operation for drift restoration; it is not silently invoked
  by base HAProxy Apply or by each partial endpoint integration. Its prior
  ownership and archive safeguards remain in force.
- Only after the base and source paths pass first-install, repeat `changed=0`,
  unrelated-backend preservation, TLS failure and standalone tests may Core
  remove the `haproxy.deploymentRef` source-before-provider Apply edge. Do not
  drop other capability dependencies or relax fail-closed plan validation.

The current BIND `apply.yml` resolves the complete DNS zone and persists its
serial before activating the service. It must be split so the base path does
not publish future service records, while the source path uses the same Core
DNS projection and generated-state ownership to update one record safely.
The existing `services/integrations/playbooks/reconcile.yml` currently calls
full BIND/HAProxy reconcile and is imported only by PostgreSQL Apply; it does
not yet satisfy this per-source path for Vault/ClickHouse or sequential plans.
The separate `EXEC-PLAN-SCOPE-01` milestone is still NOT STARTED. This
prerequisite must be reviewed as a material change in provider/source lifecycle
before the ordering implementation can claim completion.

Implementation checkpoint (2026-10-07): the ordered request/configuration,
Core sequence projection, DNS projection selection and HAProxy single-source
candidate entrypoint are in progress. Core still retains the existing
source-before-HAProxy dependency until the end-to-end source path is implemented;
do not treat a priority-derived plan with endpoint relations as executable yet.
The BIND dynamic-update lifecycle and automatic invocation of both provider
integrations from the source Apply path are not implemented. No service plan
was run and no target host was modified. Required independent FULL DIFF review
and real React/Wails acceptance remain pending.

### Per-source publication and failure boundary

The source Apply first proves its own service listener healthy and resolves its
own endpoint/provider targets from Core. The generic integration path then:

1. Builds, validates and atomically publishes only this source's HAProxy
   backend fragment; preserves all other provider files and the last valid
   candidate on failure. A TLS backend identity probe occurs before this
   publication when TLS is selected.
2. Sends an idempotent BIND dynamic update for only this source's exact A
  record to the zone primary using the local BIND update key. The primary
  zone replaces `allow-update { none; };` with BIND's `update-policy local;`.
  The host-local key is root-readable only. `nsupdate` constructs only the
  resolved zone and exact source owner update, while the key's BIND authority
  is zone-wide; this is a host-local privileged trust boundary, not a per-source
  ACL. Key material is never emitted in events/output. No new secret or
  network update credential is introduced. Compare the
  current exact A RRset first and issue
   `nsupdate` only when it differs. BIND owns update serialization, its journal,
   and SOA serial advancement; do not edit the zone file or maintain a competing
   Installer serial counter for a source update. The group wildcard remains
   provider-owned and is never part of this source projection. The update is
   verified by querying the primary after submission; an unchanged retry is
  `changed=0`. The explicit full reconcile path first synchronizes the live
  dynamic journal and reads the SOA serial actually served by the primary.
  That live serial is the lower bound for the replacement serial; the candidate
  must be validly newer under DNS serial arithmetic, otherwise reconciliation
  fails closed. The complete canonical candidate is validated before
  activation. Full reconcile retains its current whole-model semantics,
  including removal of no-longer-desired managed records, and remains disabled
  by default. Before freezing, it writes a machine-runtime per-zone recovery
  marker. An Ansible `always` cleanup attempts to thaw after every post-freeze
  failure; the marker remains until the primary is authoritative and the zone
  is verified writable again. A later BIND operation that finds the marker
  runs this bounded recovery first and removes the marker only after successful
  authority/update checks. The marker is machine-owned runtime state, not
  project desired state or a second database. Fault-injection QA must prove
  recovery when interruption happens immediately before or after freeze,
  during replacement, and before thaw.
   HAProxy precedes DNS so a
   failed backend publication cannot publish a new DNS name pointing at it.
3. Probes the actual externally addressed endpoint through DNS/VIP/HAProxy
   when those providers are selected. Apply succeeds only after this probe;
   Verify repeats it read-only. If no provider is selected, probe the
   source's declared endpoint directly instead of inventing one.

There is no cross-host or cross-provider atomic transaction. If publication
fails after one provider changed, or the final probe fails, the source Apply
fails, later deployments do not start, the successfully published fragment
remains for diagnosis, and a retry with the same desired state safely
converges it. Do not run an automatic full reconcile or delete unrelated
records as rollback. Report which bounded step failed without secret values.
First-install, interruption after HAProxy publication, DNS failure, final
probe failure, strict repeat `changed=0`, and preservation of pre-existing
unrelated endpoints are required acceptance cases.
Two competing updates to the same zone must serialize and preserve both owned
records using BIND's dynamic-update/journal behavior. An interrupted update
must leave the zone authoritative and a retry must converge to the expected
exact A RRset with `changed=0` afterward.
An endpoint removed from the project remains published in point-update mode;
only explicit full reconcile removes no-longer-desired managed records. Full
reconcile must derive its candidate serial from the actually served SOA and
prove recovery after injected interruption at each freeze/replace/thaw boundary.

## Goal

Run each selected service deployment as `Apply → Verify`, and do not proceed
to the next deployment until that Verify succeeds. This localizes failures and
prevents later services from being applied after an earlier deployment is
already unhealthy.

## Owner decisions

- Service order is derived from developer-provided service priorities in the
  Installer's `config/application.yml`.
- An operator may edit `application.yml`; the edited values then govern order,
  and the operator accepts responsibility for the operational consequences.
- Lower numeric priority means earlier execution; `0` is the highest priority.
- If service types have equal priorities, use their written order in
  `application.yml`. Multiple deployments of one type use deployment ID
  ascending. Core still rejects an order that violates a declared dependency.
- The UI uses the configured priorities to submit one ordered list of the
  selected deployment IDs to Core. Core does not assign service priorities,
  assign priorities to service types or silently reorder the list.
- The requested order must respect dependencies already declared by Core. If
  the priority-derived order would put a dependent deployment before its
  provider, plan construction fails closed and identifies the conflicting
  dependency; priorities never override `dependsOn`.
- The selected list contains only deployments already selected for the plan;
  absent services are not synthesized.
- Once a deployment Apply succeeds, its Verify runs immediately. The next
  deployment starts only after Verify succeeds. A failed Apply or Verify
  prevents all later deployments from starting.
- Existing PKI actions remain before service actions.
- Core is service-priority-agnostic, but it must validate the supplied order
  against the existing dependency edges. It does not calculate priorities or
  repair an incompatible sequence.

## Proposed configuration and request contract

The revised Installer configuration uses `schemaVersion: 2`. Its
`config/application.yml` contains a developer-default ordered sequence named
`serviceExecutionPriorities`, with unique service-type IDs and non-negative integer
priority. It is Installer application
configuration, not project desired state. Operators may edit the file; the
effective values are used as written, and the operator owns the consequences of
that ordering. Every service type selected in a plan must have a configured
priority; a missing or malformed entry blocks plan construction with a safe
configuration error rather than silently assigning a priority. Duplicate
service-type entries are invalid. YAML sequence order is part of the tie-break
contract and must be preserved by the application-config reader.
The new binary does not silently assign priorities to an old `schemaVersion: 1`
file or rewrite it. It reports `APPLICATION_CONFIG_UPGRADE_REQUIRED` with
instructions to retain the operator's server types and add the ordered
priorities under version 2. A new distribution ships a complete version-2
file. An old binary continues to use its old version-1 file; the two formats
are not misinterpreted as each other.

Example of the ordered format (the complete initial list follows below):

```yaml
serviceExecutionPriorities:
  - serviceType: bind
    priority: 0
  - serviceType: dns-client
    priority: 1
```

The initial configuration should encode the currently agreed infrastructure
prelude declaratively with this complete ordered sequence for the currently packaged
service types:

| Service type | Initial priority |
|---|---:|
| `bind` | 0 |
| `dns-client` | 1 |
| `keepalived` | 2 |
| `haproxy` | 3 |
| `clickhouse` | 4 |
| `docker` | 4 |
| `kafka` | 4 |
| `postgresql` | 4 |
| `redis` | 4 |
| `vault` | 4 |

No service-name conditional or special-case ordering code is added to React,
Go or Core. Values live only in `application.yml`; UI obtains them through the
existing application-configuration API. A newly packaged service requires a
new developer-default entry before plans containing it can be built. An
operator may add or change entries in `application.yml` and accepts the
resulting order, but Core's dependency checks remain mandatory.

The existing execution-runtime JSON request for operation `BuildDeploymentPlan`
has top-level `project` and `runtimeRelease` fields. The ordered-plan request
uses `platform.installer/execution-runtime/v1alpha2` and adds a required
top-level `deploymentOrder: string[]` to that operation. Other runtime
operations retain their existing versions. `GetCapabilities` advertises
ordered-plan support; Go checks it before Plan or Start and reports a safe
runtime-upgrade requirement when the selected bundle/Execution Node is older.
The new Core rejects a v1alpha1 `BuildDeploymentPlan` request with a specific
upgrade-required error rather than silently applying new sequencing to an
old client's request. An old Core rejects the unfamiliar v1alpha2 request;
the workstation checks capabilities before sending it. An old client can
continue to use its matching old bundle, but cannot build a new plan through
an upgraded incompatible Core until the client is upgraded. No old approved
plan is reused: fresh plan fingerprint, approval and Start binding are
required. For Wails, Go passes the
list received from the UI in this field. The UI sorts the selected deployments
by ascending configured priority, then YAML entry position, then deployment ID.
For standalone Core, the operator supplies the
same ordered list through the existing `deployment-plan-machine.yml` input
variable `platform_execution_deployment_order`; no alternate planning path is
added. Both routes must deliver the same exact list to the same Core builder.

`deploymentOrder` must list every selected service deployment exactly once;
it may be `[]` only when the plan contains no service deployments. Missing or
null field, a non-array, empty list with selected deployments, duplicate,
unknown or omitted ID blocks plan construction. Core validates membership and
checks each existing cross-deployment dependency: its provider must appear
earlier than the dependent deployment. Core neither reads application.yml nor
calculates priorities, chooses a service order or repairs an incompatible
list. It rejects conflicts with a structured, secret-safe finding. The
accepted order is part of the immutable public plan and its fingerprint.

Keep existing action IDs, action types, targets, runtime projections, plan
approval and Start binding. Keep the existing `plan/v1alpha2` schema if its
generic phase IDs and ordered action representation express the result. After
the optional PKI phase, emit one deterministic phase per deployment, with its
Apply followed immediately by its Verify. Each Verify depends on its own
Apply; existing inter-deployment dependencies remain represented and must be
consistent with the phase order. The sequential controller already executes
manifest operations in order and fails fast; do not add a scheduler.

The plan review UI must show deployment identity and the actual Apply/Verify
order, not raw internal phase IDs. It must not display developer priorities as
user-editable controls. Events retain the phase/action IDs from the approved
plan.

UI design discrepancy checked before implementation: the current Installation
mockup groups all Apply actions before Verify actions. The approved flow is
instead a visible per-deployment Apply row immediately followed by its Verify
row; update the affected plan mockup and screen documentation with the UI
implementation. This is an owner-approved flow change, not a Core behavior
inferred from the mockup.

## Scope and non-goals

In scope, as a required first slice: HAProxy base Apply/Verify without service
backends; BIND base Apply/Verify without future service endpoint records; one
generic per-source endpoint integration/health path used by
standalone Ansible and Installer service Apply/Verify; preservation of existing
provider state and partial-failure evidence; removing only the now-obsolete
source-before-HAProxy dependency after those gates pass. In scope, as a second
slice: developer-maintained service-type priorities in version-2 application
configuration; projecting them to one ordered deployment list in the UI;
versioned request/capability validation; immediate per-deployment Apply then
Verify; dependency conflict findings; plan-review presentation; focused tests
for ordering and fail-fast behavior.

Out of scope: project-level priority persistence, service-priority fields in
service manifests, Core-owned service priorities, a new
dependency graph, parallel scheduling, service-specific execution branches,
selective deployment plans, Start/lease or Execution Node
lifecycle changes. Standalone Core
callers may supply an explicit order through the same plan input; Core does
not infer the UI's developer-configured priorities.

## Acceptance criteria

1. Installer application configuration supplies developer-default priorities
   for every currently packaged service type; an operator-edited
   `application.yml` is honored.
2. Lower priorities execute first, with `0` highest. Equal priorities follow
   service-type entry order in `application.yml`, then deployment ID ascending.
3. Initial priorities are exactly the complete ordered sequence in this plan: BIND 0,
   DNS-client 1, Keepalived 2, HAProxy 3, and ClickHouse/Docker/Kafka/
   PostgreSQL/Redis/Vault 4.
4. UI submits each selected deployment ID exactly once in the priority-derived
   order; it does not add unselected deployments.
5. Missing/malformed priority configuration, missing/null `deploymentOrder`,
   invalid membership, or an order contradicting an existing dependency fails
   plan construction closed, with a finding identifying the actionable cause.
6. Core preserves a valid supplied order and does not reorder it or contain
   service-type priority rules; it checks only contract completeness and
   existing dependency constraints.
7. Every deployment's Apply immediately precedes its Verify, and the next
   deployment does not start until Verify succeeds.
8. A failed Apply or Verify prevents all later deployment actions; the
   original failed operation and terminal failure remain visible.
9. PKI actions remain before service actions; plan, fingerprint, approval,
   manifest, events and displayed sequence agree. `plan/v1alpha2` remains
   unchanged unless implementation evidence proves it cannot express this.
10. UI and standalone Core callers pass the same `deploymentOrder` field/value
    to the same Core builder and produce identical plan order and validation.
11. Real React/Wails acceptance demonstrates the displayed order and a
    controlled early failure demonstrates that later deployments were not
    applied.
12. HAProxy base Apply succeeds before a linked source exists and updates its
    own files atomically without selecting or probing that source's backend;
    unrelated existing backend files remain intact.
13. BIND base Apply succeeds before a linked source exists, establishes its
     zone/SOA, project-host records and wildcard only for endpoint groups
     whose existing `address.wildcard` option is `true`, without
     rendering future exact service records, and preserves existing records
     and BIND-owned serial history. BIND base Verify does not require a
     not-yet-installed source's exact record.
14. Every source with an endpoint uses the same generic integration path in
    standalone Ansible and Installer execution; its Apply proves the source
    listener, publishes only its endpoint, probes the actual route, and fails
    before the next deployment if any step fails. Verify is read-only.
    PostgreSQL has no endpoint relation and does not invoke provider integration.
15. Partial HAProxy/DNS/probe failure is explicit and retryable; unrelated
    endpoints are preserved, BIND SOA serial advances only for changed dynamic
    updates, and an unchanged repeat reports `changed=0`. The ordinary BIND
    apply defaults to point updates; explicit full `reconcile.yml` retains its
    prior complete-model behavior and is opt-in. Removed endpoint records are
    retained in point-update mode and removed only by explicit full reconcile.
    Full reconcile uses the actually served SOA as the serial lower bound and
    recovers from interruption through a machine-runtime marker plus guaranteed
    thaw and authority/update checks.
16. Version-1 application config and old/new runtime-client combinations
    produce the specified upgrade-required or unsupported-version outcome,
    never a silent default order. Plan fingerprints and approval bind the
    revised order.

## Test Scope

The prerequisite scope covers HAProxy and BIND base Apply, source-owned endpoint
integration, BIND/HAProxy bounded publication, standalone role Apply/Verify,
explicit full reconcile and partial-failure recovery. The ordering scope
covers versioned request/configuration validation, dependency/phase projection,
controller fail-fast and affected UI presentation. Kafka acceptance and a
full infrastructure install are not part of the unit/contract gate.

## Required Scenarios

- Read configured priorities and sort multiple service deployments by ascending
  value.
- Equal priorities follow YAML entry order; multiple deployments of one
  service type follow deployment ID ascending.
- Default infrastructure priority groups produce BIND, DNS-client, Keepalived,
  HAProxy first, then other services in the listed YAML order after the
  prerequisite base/provider split and dependency correction pass their gates.
- The `BuildDeploymentPlan` request carries required top-level
  `deploymentOrder`; `[]` succeeds only for zero service deployments, while
  missing, null, incomplete or extra IDs fail closed.
- Two plans with different effective ordered actions have different
  fingerprints and require fresh approval.
- A valid order passes unchanged from UI request through public plan and
  private manifest.
- Base BIND and HAProxy Apply before Vault/ClickHouse exists, followed by each source's
  own endpoint publication and read-only Verify, works through standalone
  Ansible as well as the Execution Node controller.
- Existing unrelated DNS/backend artifacts survive base BIND/HAProxy updates and
  per-source publication; explicit full reconcile still restores drift.
- Removing an endpoint does not delete its DNS record in point-update mode;
  explicit full reconcile is the only planned deletion path.
- Full BIND reconcile synchronizes and reads the live SOA before assigning a
  candidate serial; fault injection proves recovery to authoritative writable
  state after interruption at freeze, replacement and thaw boundaries.
- DNS wildcard is emitted by base BIND only when the existing endpoint-group
  `address.wildcard` option is true; source-specific integration never changes it.
- The managed primary's dynamic-update policy is scoped to BIND's host-local
  update key; the key is root-readable only and never appears in task output.
- An interruption after HAProxy fragment publication but before DNS, a DNS
  publication failure and an endpoint probe failure all stop the current
  source Apply and converge safely on retry without deleting unrelated state.
- Version-1 config and old/new runtime request combinations produce explicit
  compatibility outcomes; no implicit priority or old approval is reused.
- Apply failure and Verify failure each stop execution before the next
  deployment starts.
- Real React/Wails plan review displays the same order Core approved.

## Negative Scenarios

- Missing config entry or non-integer/negative priority for a selected service
  type.
- A priority-derived order contradicts an existing dependency edge: fail closed,
  name the dependent and required provider, and do not silently reorder.
- Unknown, duplicated or omitted deployment IDs in the ordered list.
- Dependency points to a deployment absent from the plan: preserve current
  Core dependency semantics and block if that dependency is required.
- Failed Apply or Verify: no subsequent service operation starts.

## Contract Scenarios

- One required top-level `deploymentOrder` field in the versioned v1alpha2
  `BuildDeploymentPlan` runtime request is shared by Wails and standalone Core
  callers; standalone maps it to `platform_execution_deployment_order` for the
  same Core plan builder.
- Core validates exact membership, uniqueness and current `dependsOn` order,
  without reading `application.yml` or calculating priorities.
- The resulting ordered plan is immutable and fingerprint-bound; approval and
  Start cannot reuse an order from another plan revision.
- Existing plan schema, action identity, target projection, artifact authority,
  secret boundary and event identity remain unchanged. The runtime request
  version/capability is intentionally extended; Start/lease behavior is not.

## Regression Risks

- A developer-maintained priority table can omit a newly packaged service; make
  this an explicit plan-time error with a safe actionable message.
- Sorting must honor written YAML order for equal-priority service types and
  deployment ID order within one type; this intentionally replaces the old
  Core topological tie order, subject to dependency validation.
- Priority ordering must not bypass Core's declared provider dependencies.
- Consumers that assume only `pki`/`apply`/`verify` phases need targeted
  updates if the existing generic plan representation is used differently.
- This changes plan semantics and fingerprints; stale plans must not remain
  approvable.
- It improves failure localization but does not itself repair the separate
  previously observed HAProxy `/run/haproxy/admin.sock` service failure.

## Environment Requirements

- Focused UI tests for configuration consumption and stable sort.
- RED OS standalone Ansible first-install/repeat checks for BIND and HAProxy base,
  service-owned endpoint integration, selected-provider TLS failure and
  explicit full reconcile; run one source at a time on authorized QA targets.
- Negative fault-injection checks at HAProxy publication, DNS publication and
  endpoint probe boundaries, including safe retry and unrelated-state proof.
- Compatibility tests for application config v1/v2 and runtime request
  v1alpha1/v1alpha2 against old/new capability responses.
- Focused Core tests on RED OS for exact ordered-list validation, dependency
  conflict rejection and per-deployment phase/action projection.
- Controller fail-fast regression test using a controlled synthetic manifest;
  no target host required.
- Existing real React/Wails automation seam for final integration acceptance.

## Not Testable Locally

- Real Wails/Core/Execution Node integration is not proven by mocked frontend
  bindings or direct Go harnesses alone. If the supported automation seam is
  unavailable, report that acceptance gate as blocked rather than substituting
  mocks.
- Synthetic controller tests prove ordering and fail-fast without targets, but
  they do not replace the separately authorized RED OS prerequisite checks.
  Do not use the failed SI11 plan as an implicit authorization to reset hosts
  or run another full installation.

## Review and implementation gates

Before implementation, obtain the required independent plan review of this
exact revision and owner approval of any blocking corrections. After
implementation, run focused UI/Core/controller tests, full Core and Go tests,
frontend lint/build and `git diff --check`. Real React/Wails acceptance is
required before claiming end-to-end completion. No production implementation
or installation run is authorized by this planning document alone.
