# Historical roadmap checkpoints — source snapshot 2026-10-12

Extracted from [the roadmap](../roadmap.md), preserving original recorded
statuses, reviews, run IDs and historical scope. Dates inside the excerpts
remain their original dates; 2026-10-12 is the extraction date.
These excerpts are not current status or authorization. In particular, old SI11
NOT STARTED statements are retained as history; the owner-closed stage is
recorded in [CURRENT_STATE](../../CURRENT_STATE.md).

## CORE-01: Repository and contract skeleton

Status: DONE. Contract documents, standard playbook validation, the offline
Draft 2020-12 schema engine, service-package skeletons and fixture conformance
execution are implemented and tested.

## CORE-02: Deterministic topology resolution

Status: DONE. The topology-only slice was implemented and validated on the
RED OS controller in an offline network namespace.

## CORE-04: Scoped configuration and variable context

Status: DONE. Scoped configuration, variable contexts, opaque pass-through
preservation, deterministic references and independent member projections were
implemented and validated on the RED OS QA VM.

## CORE-05: Canonical service metadata and variable preservation

Status: DONE. Service packages now author canonical managed/advanced setting
metadata in `service.yml`; tracked `configuration.schema.json` files are
deterministically generated and checked for reproducibility. Role defaults
remain standalone Ansible's canonical default/Jinja source.

## SERVICE-01A: Kafka KRaft standalone

Status: DONE. Kafka 4.3.1 single-node KRaft apply and verify were implemented
inside the Kafka service package and validated on RED OS with offline artifact,
idempotent storage initialization and `changed=0` repeat execution.

## SERVICE-01B: Kafka KRaft distributed

Status: DONE for same-host multi-member deployment and SERVICE-01C real
multi-host extension.

## EXEC-01: Execution Node and target bootstrap

Status: DONE. This milestone establishes selectable execution-node
semantics, separates candidate eligibility from post-preparation readiness,
and provides generic preparation/bootstrap phases. The selected Execution Node
may be local, a project target, or external; a dedicated host is optional.

## SERVICE-01C: Kafka KRaft real multi-host deployment

Status: DONE. Centralized EXEC-01 acceptance was applied through one Execution
Node invocation.

## SERVICE-01D: Kafka split broker/controller deployment

Status: DONE. The generic Kafka lifecycle accepts split broker-only and
controller-only members without topology-profile branches. Centralized
acceptance uses node1 as the selectable Execution Node and node1/node2/node3 as
the three physical targets.

## CORE-06: Canonical project state and runtime projection

Status: DONE under its original contract. Deployment-level desired state was
canonical in `project.yml.desiredState`; physical member ownership and
placement were inventory-owned. CORE-07 supersedes the desired-state ownership
boundary while preserving CORE-06 projections and compatibility readers.
Managed Kafka projects normalized inputs into the existing
runtime-only standalone role contract and records a deterministic
`runtimeProjectionFingerprint` from final service-relevant values.

## PKI-01: Certificate and Java-store materialization

Status: IMPLEMENTED. PKI-01 adds topology-derived managed certificate requests
with default HOST scope, MANAGED CA materialization on the Execution Node, PEM
and dedicated PKCS12 deployment to targets, and read-only verification.
Certificate/private-key/password values remain runtime state; canonical
projects retain only intent and secret references. Ordinary reconcile blocks
changed request or authority identity with `CERTIFICATE_REISSUE_REQUIRED`.
An explicit selected leaf reissue preserves prior request material in protected
Execution Node state; authority rotation remains deferred.

## CORE-07: Ansible-native canonical desired state

Status: DONE. Standard inventory, `group_vars`, `host_vars` and role defaults
are canonical user-owned desired state. `platform_desired_state` declares
logical deployments; inventory `platform_deployments` declares members and
placement. Machine-owned identities, fingerprints and locks are isolated in
`platform_generated_state`. Managed Kafka and PKI work without `project.yml`;
legacy project inputs and standalone role variables remain bounded
compatibility paths. The Installer must edit these same files and invoke the
same standalone playbooks.

## SERVICE-02A: Kafka named listeners and SSL consumer prerequisites

Status: DONE. Kafka now uses explicit named `PLAINTEXT`, `SSL` and
role-appropriate `CONTROLLER` listeners with one service-wide TLS profile.
Legacy `clientPort` and `controllerPort` settings were removed. Kafka consumes
PKI-01 materialization read-only and copies required material into its
Kafka-owned directory without persisting passwords.

## UI-DESIGN-01: Installer interaction architecture

Status: DONE. This documentation/design milestone defines Platform Installer
as a visual editor and orchestrator for the same Ansible-native project used by
standalone operators. It adds no Wails/React production code, persistence
model, Core topology model or UI-owned desired state.

## POSTGRES-01: PostgreSQL standalone and pg_auto_failover

Status: DONE. PostgreSQL standalone and two-data-member
pg_auto_failover deployments use include-based dynamic configuration,
topology-scoped TLS/HBA policy and runtime-only credentials. RED OS acceptance
proved initial apply, separate verify, repeat apply, TLS enforcement,
automatic failover, data preservation, natural rejoin and post-rejoin
idempotence. Final focused/Core, generated-artifact, syntax, offline and
security audits passed.

## NET-01: Endpoint Groups and Resolved Service Endpoints

Status: DONE. NET-01 establishes the Ansible-native endpoint group contract,
direct `serviceDeployment.endpointGroup` assignment, and read-only FQDN
resolution. It deliberately excludes transport ports and all routing semantics;
those belong to a future HAProxy milestone. PostgreSQL is the first opt-in package, Kafka
remains outside generic endpoint semantics, and PKI-01 consumes the projection
only according to existing SAN policy.

## NET-02: Keepalived / VRRP / Stable VIP Ownership

Status: DONE. One host-scoped Keepalived deployment owns one VRRP instance,
one VRID, one endpoint group reference and one-or-more virtual addresses.
Three-node RED OS acceptance proved native validation, all-or-none multi-VIP
ownership, automatic failover, natural rejoin with `nopreempt`, and repeat
apply/verify idempotence. The NET-02 baseline has no active HAProxy dependency;
NET-04.1 later adds explicit opt-in `vrrp_script`/`track_script` semantics.

## NET-03: Authoritative BIND DNS

Status: DONE. NET-03 derives deterministic project-host, endpoint and wildcard
DNS records, and maintains machine-owned per-zone fingerprint/serial state.
Three-node RED OS acceptance proved complete candidate and active barriers,
native primary-to-secondary BIND transfer, authoritative responses from all
nodes, exact-once serial increment on a logical zone change, primary outage
continuity, natural primary restoration, and post-recovery verify/repeat
idempotence.  DNS routing and HAProxy are deliberately deferred.

## NET-03.1: DNS Client / Split DNS Runtime Adapters

Status: DONE. A separate host-scoped `dns-client` package consumes one logical
`dnsServerRef` and derives its primary-plus-secondary addresses and route-only
zone from the existing Core DNS projection.  Three-node RED OS acceptance
proved systemd-resolved split DNS, safe resolv.conf ownership, normal resolver
host/endpoint/wildcard lookups, unrelated DNS preservation, primary and
single-remaining-server fallback, recovery, and idempotent apply/verify.
NetworkManager fallback has focused coverage and blocks safely unless a
supported per-domain DNS backend is present.

## NET-04: HAProxy

Status: DONE. The host-scoped HAProxy package provides fixed HTTPS `public`
routing on `*:443`, deployment and explicit host endpoints, normalized Host
routing and package-owned TLS stats backends. Three-node RED OS acceptance
proved candidate/activation barriers, hostname-verified TLS, real pooled
multi-node backend use, non-VIP-owner failure isolation, recovery, and clean
verify/repeat apply.

## NET-04.1: Keepalived HAProxy health tracking

Status: DONE. Opt-in Keepalived tracking references one colocated HAProxy
deployment and renders a root-owned bounded admin-socket readiness helper with
one `vrrp_script` and `track_script`, without weight. A cluster-wide candidate
and active-validation barrier prevents any service reconcile until every
participant has validated the exact SHA-256-matched configuration. Three-node
RED OS acceptance proved owner failure causes atomic configured-VIP migration,
endpoint continuity, natural backup recovery without failback, non-owner
failure isolation, and clean final verify/repeat apply.

## NET-04.2: Service-driven provider reconciliation

Status: DONE. A successful service lifecycle invokes one deterministic,
read-only provider projection; BIND reconciles before HAProxy from complete
canonical desired state. Acceptance proved deduplication, full-model drift
repair, desired-state add/remove cleanup, serial `4 → 5`, clean repeats and
shared-PKI stability.

## UI-BE-01: Installer UI / backend boundary

Status: DONE. The versioned query/semantic-command/execution boundary is
defined in `docs/work/ui-backend/ui-be-01.md`. UI read models remain derived projections over
the same canonical Ansible project. Normal writes use reviewed EditPlans,
optimistic project/document revisions and a safe Ansible-native writer;
arbitrary existing projects are read-only by default and Installer-owned
standard Ansible files are the preferred write target. No production backend,
UI, YAML writer or speculative contract family was added.

- UI-BE-02: DONE — read-only ProjectSnapshot and controller query adapter;
- UI-BE-03: DONE — safe Ansible-native writer and EditPlan/commit boundary;
- DEVX-01: DONE — Go/Core scoped guidance, Codex Skills, reviewer templates and reusable QA workflow;
- EXEC-01A: DONE — bootstrap a READY Execution Node before Platform Core exists, with node-scoped repository-first/offline-bundle fallback;
- UI-BE-04A: DONE — actual execution audit and boundary freeze;
- UI-BE-04B: DONE — target-free Core DeploymentPlan and private ExecutionManifest;
- UI-BE-04C: DONE — fixed Execution Node runtime protocol and durable lifecycle;
- UI-BE-04D: DONE — Go ExecutionService, approval, sessions and reconnect;
- UI-BE-04E: DONE — production Kafka E2E and final regression;
- UI-BE-04 overall: DONE — validation, plan, execution and events;
- UI-01: production Wails/React UI over those accepted contracts.

## UI-BE-02: Read-only ProjectSnapshot

Status: DONE. `platform.core.project_snapshot` and the standalone
`project-snapshot.yml` entrypoint compose a versioned deterministic read model
from the Ansible-loaded project without writes or target contact. The accepted
contract includes separate raw-byte project/document revisions and catalog/Core
versions, six-service catalog and deployment views, effective configuration
with honest provenance, heterogeneous topology, endpoint/provider/DNS/HAProxy
relations, shared PKI identities, partial validation and static readiness.
Offline RED OS acceptance and the architecture review have zero blockers.
UI-BE-03, DEVX-01 and EXEC-01A are complete. UI-BE-04A is DONE and
UI-BE-04B, UI-BE-04C, UI-BE-04D and UI-BE-04E are DONE. UI-BE-04 overall is
complete; later UI milestones remain separately gated.

## UI-BE-04A: Execution architecture audit

Status: DONE. `docs/work/ui-backend/ui-be-04.md` records the actual EXEC-01A reuse matrix and
freezes Core ownership of deterministic deployment planning, private execution
manifests and trusted ordering. The future Execution Node API is a fixed
semantic protocol with detached controller ownership, bounded journal/events,
replay, reconnect, cancel and recovery. The current synchronous Kafka and
Keepalived `ExecuteService` remains only an EXEC-01A regression path. No
production planning, runtime protocol, session or frontend code was added.

## UI-BE-04B: Core deployment planning

Status: DONE. Core builds a deterministic public `DeploymentPlan/v1alpha2`
and private execution manifest from the target-free validated project graph,
full catalog and immutable runtime-release identity. Project identity is
canonical `project.yml.metadata.id`; a path fallback is blocked for
Installer-managed mutation. Source selection remains EXEC-01A execution-time
behavior. Core planning passed normal and network-isolated RED OS acceptance.

UI-BE-04C, UI-BE-04D and UI-BE-04E are complete. UI-BE-04 overall is DONE.

## UI-BE-04C: Execution Node runtime protocol

Status: DONE. The activated runtime now exposes only fixed semantic operations
and runs trusted Core-owned manifest operations through a detached transient
systemd controller. Run journals are private, digest-bound, replayable and
bounded; ownership includes run, project, plan, manifest, release and unit
identity. RED OS acceptance proved disconnect/reconnect, exactly-one terminal
results, whole-control-group cancellation, interrupted recovery, foreign-unit
safety and retention. UI-BE-04E completed production Kafka E2E and final
regression; UI-BE-04 overall is DONE.

## EXEC-OBS-01: Ansible task observability and Installer-side event mirror

Status: DONE (2026-09-05). Internal gates 01A through 01D implement the managed
callback, safe shared journal writer, controller integration, paginated
GetEvents, complete typed event model, RunObserver and CLI watch. The remote
journal stays authoritative; local files are runtime-only mirrors and future
UI consumes typed subscriptions.

Two production Kafka lifecycle runs completed SUCCEEDED, with PKI/apply/verify,
repeat changed=0, 1,713 task events per run and identical remote/subscriber/local
streams. Live reconnect and CLI restart, real no_log/failure/degradation,
Core/service/race/offline/security gates passed; reviews have 0 blocking
findings. Commands and counts: `docs/work/execution/exec-obs-01.md`.

UI-01A, UI-01B and UI-01C are DONE. UI-01B provides the production Wails/React
read-only existing-project shell and its one fixed target-free Core snapshot
operation. UI-01C adds local metadata-only project creation and empty-project
reopen; UI-01D implementation/acceptance is complete and owner-accepted
without final revision-bound review. The separately authorized application
config/server-type foundation adds a versioned local type catalog and additive
`CreateServer` v1alpha3 contract without starting full server CRUD. UI-01E is
decomposed into E1 server CRUD integration, E2 Servers UI, E3 shared runtime
credentials, E4 Execution Node selection panel, E5 readiness/navigation gating
and E6 final Windows/RED OS acceptance. UI-01E1 is DONE: v1alpha4 server CRUD
intents use the existing edit/session/guarded-transaction lifecycle, Core projects desired
hostname/normalized port and generic references, and focused Windows/RED OS
gates passed. UI-01E2 through UI-01E6 and UI-01F1 through UI-01F6 are DONE;
UI-01F overall is DONE. F6 evidence is recorded in `docs/work/ui-01/ui-01f6.md`.

## DEVX-01: Codex engineering harness

Status: DONE. Repository-local Skills now guide Go backend work, Go-to-Core
adapter changes, safe project-writer changes and milestone QA. Scoped
instructions preserve the `internal/` application boundary and `ansible-core/`
infrastructure boundary. Implementer/reviewer roles are documented prompt
templates because this repository has no executable role-definition mechanism.
Wails/React guidance is intentionally deferred until concrete UI contracts
exist.

## BACKEND-01: Core process adapter

Status: SUPERSEDED by the explicit UI-BE-04B through UI-BE-04E gates. This
heading remains as historical roadmap context; `docs/work/ui-backend/ui-be-04.md` is the
accepted execution boundary.

## UI-01: Project, hosts and topology editor

UI-01A is DONE (documentation only): [contract preflight](../work/ui-01/ui-01a.md),
[accepted freeze](../work/ui-01/ui-01a-contract-freeze.md), [reviews](../work/ui-01/reviews/ui-01a-review.md) and
[QA](../work/ui-01/evidence/ui-01a-qa.md). Empty-project, first-write/inventory ownership, typed
command, selected Execution Node validation and frontend toolchain decisions are
closed. UI-01B is DONE: native folder selection, a verified immutable runtime,
READY Execution Node handshake and Core-authoritative read-only snapshot were
accepted without canonical-project mutation. UI-01C is DONE: local
metadata-only creation, no-replace publication and empty-project reopen were
accepted without Core/Execution Node contact. UI-01D implementation and
acceptance are complete: the bounded transient session, complete-candidate
remote Core proof, guarded first write and narrow Windows review/save shell
passed its executable gates and was owner-accepted without final
revision-bound review. The application config/server-type foundation is
independent of UI-01E and does not advance its implementation. UI-01E1 through UI-01E4 are DONE;
the pre-E5 ADR-027 Save/Verify separation is implemented without advancing E5.
UI-01E5 is DONE: the application-owned trusted Execution Node binding now
supports read-only readiness, explicit-confirmation preparation and fresh
post-Prepare Verify, while candidates remain transport-free. UI-01E6 is DONE;
UI-01F1 through UI-01F6 are DONE; UI-01F overall is DONE. UI-NET-01 is DONE:
provider tuples are edited through v1alpha6, the existing guarded local
Save/reopen lifecycle and the Topology → Entry points UI. Its Core-derived
preview never infers PKI/SAN impact locally; see `docs/work/ui-network/ui-net-01.md`.
UI-01G1 is DONE: additive v1alpha7 PKI intents, direct bounded managed-state
reopen, generic final-state references and guarded local Save passed Go and
RED OS gates; see `docs/work/ui-01/ui-01g1.md`. UI-01G2 is DONE: the Certificates page
uses the shared draft and typed intents with no local PKI derivation; see
`docs/work/ui-01/ui-01g2.md`. UI-01G3 is DONE: revision/node/runtime-bound Core PKI
evidence is projected to Certificates without local SAN/VIP calculation; see
`docs/work/ui-01/ui-01g3.md`. UI-01G4 is DONE: Windows/RED OS target-free acceptance,
race gates and hygiene passed; see `docs/work/ui-01/ui-01g4.md`. UI-01G overall is DONE.
UI-01H1 is DONE: v1alpha8 safe configuration intents, bounded catalog and
managed projections, local Save/reopen and descriptor-driven TLS reference
integrity passed; see `docs/work/ui-01/ui-01h1.md`. UI-01H2 is DONE: the one Services
list/detail route, Topology hand-off and descriptor-gated deployment forms use
the existing shared edit lifecycle without Core or target changes; see
`docs/work/ui-01/ui-01h2.md`. UI-01H3 is DONE: member-scoped configuration and trusted
TLS-profile selection use the shared v1alpha8 session and contextual
Certificates return without Core or target changes; see `docs/work/ui-01/ui-01h3.md`.
UI-01H4 is DONE: Windows desktop, RED OS target-free/race and regression gates
passed with no target contact; see `docs/work/ui-01/ui-01h4.md`. UI-01H overall is DONE.
UI-01I is DONE: guarded portable export/reopen, Windows/Wails and RED OS
target-free evidence, plus the one permitted DIFF targeted recheck, passed with
zero blocking findings; see `docs/work/ui-01/ui-01i.md`. UI-01J is DONE: final native,
RED OS, Core-contract and safety acceptance passed; see `docs/work/ui-01/ui-01j.md`.
UI-01 overall is DONE. UI-02 remains separately authorized work.

## UI-02: Installation workflow

UI-02A is DONE: it reconciles the Installation mockup, exposes a closed local
read-only state and shows Summary, Plan, Execution and Result without a plan,
Core call, node/target contact, secret or Start path. UI-02B is NEXT and alone
may create and approve a fresh plan.

UI-02B is DONE: the Installer invokes the existing target-free Core planning
operation through `ExecutionService`, projects a bounded plan, and accepts
only the exact acknowledgements for its saved revision/runtime binding. It has
no Start, cancellation, secret or target-contact path. UI-02C is DONE: its
single `ExecutionService` Start path uses v1alpha2, while the node owns the
durable attempt-to-run binding, lease attachment and authoritative run ID
before controller launch. UI-02D is DONE: the App composes the runtime-only
credential broker with `ExecutionService`, uses closed Wails event/result DTOs
and bounded generation-bound observer subscriptions, and separates explicit
cancel from navigation/unsubscribe. Focused Windows and RED OS race gates and
the permitted targeted architecture recheck passed. UI-02E is DONE: the
immutable QA runtime completed two production-shaped one-host/three-member
Kafka cycles through the generic lifecycle, both `SUCCEEDED`, with repeat
apply `changed=0`; see
[UI-02E completion evidence](../work/ui-02/ui-02e-pki-runtime-secret-transport.md#8-completion-evidence).
UI-02F is DONE: bounded Core-derived service-secret descriptors,
session-only descriptor-bound values and v1alpha3 runtime transport are
complete. UI-02 overall is DONE.

## Post-UI-02 service installation acceptance

SERVICE-INSTALL-09 [ClickHouse](../work/clickhouse/service-install-09-clickhouse-architecture.md)
with standalone 1/1 (no Keeper), paired server+Keeper HA 3/1 and 3/3,
TLS-only enabled protocols and HTTPS endpoint. The corrected PLAN passed its
single targeted recheck with zero blockers. The all-services one-plan final
acceptance was later reassigned to SERVICE-INSTALL-11. Earlier
references to SI09 as the final eight-service test below are historical snapshots.
As of 2026-09-29 SI09 has partial acceptance, not DONE: direct 1/1, 3/1 and
3/3 service cycles, strict repeat and the ClickHouse HTTPS endpoint pass, but
the real React/Wails cumulative run ended FAILED at HAProxy apply. The bounded
HAProxy TLS-probe correction passed direct QA; the owner declined another full
plan run. A terminal real-bridge PASS remains a future SI09 gate, not inferred
from direct Ansible evidence. SERVICE-INSTALL-10 is now
[Docker rootless + Compose](../work/docker/service-docker-rootless-architecture.md), with
autonomous RED OS and real nonvisual React/Wails -> Go -> Execution Node
initial/repeat terminal SUCCEEDED, repeat `changed=0`, mutual-TLS API, Compose
and LXC systemd stop/start/reboot proof. Full regression gates passed; SI10 is
DONE (2026-10-01). SI11 all-services single-plan acceptance is NOT STARTED.

Owner-revised first SI11 stage, `S11-00 — Installer-free QA baseline`:
on the dedicated node1/node2/node3 VMs remove confirmed Installer,
Execution Node and QA-installed service units, configuration, data, packages
and temporary workspaces. Do not restore VM snapshots or reinstall the OS;
do not claim the result is a provably fresh OS. Preserve OS access/bootstrap
baseline (network, SSH technical account and approved repositories), and
never delete unknown or shared system data merely to satisfy a checklist.
Scope, pre-clean inventory, phased actions and final absence checks are in
the [S11-00 cleanup record](../work/services/service-install-11-cleanup.md). S11-00 is DONE
(2026-10-01); the all-services run has not begun.

Latest SI08-F status (2026-09-29): the fresh 3-host Keepalived/BIND/HAProxy/
Vault endpoint project and strict repeat are technically DONE through real
React/Wails → Go → Execution Node. Both full runs SUCCEEDED; repeat had
`changed=0`. DNS serial migration was explicit and evidence-bound, and
authenticated Vault KV remained reachable through DNS/VIP after leader
step-down and loss/restoration of the active Vault member. Full Core,
service, frontend/Wails, RED OS race and secret gates passed.
[SI08-F evidence](../work/vault/service-install-08f-vault-endpoint-ha.md). SI09 all-services
one-plan acceptance has not started. SI08-F source and QA are recorded in
focused commits; see `CURRENT_STATE.md` for the current milestone gate.

Latest SI08-E status (2026-09-28): Vault 1/1, HA 3/1 and HA 3/3 technical
acceptance is DONE, including real React/Wails lifecycle, strict `changed=0`
repeats, failover, explicit unseal, persistent KV marker and the full RED OS
race gate. [SI08-E evidence](../work/vault/service-install-08e.md). SI09 (all services in
one plan) has not started and requires a separate owner request. Earlier
shared-worktree changes still prevent a clean-repository claim; consult
`CURRENT_STATE.md` before treating the broader release as finalized.

Historical pre-SI08-E status snapshot: SERVICE-INSTALL-01 Keepalived DONE (2026-09-23); SERVICE-INSTALL-02
BIND DONE (2026-09-23); SERVICE-INSTALL-03 dns-client DONE (2026-09-23);
SERVICE-INSTALL-04 HAProxy DONE (2026-09-23); SERVICE-INSTALL-05 Kafka DONE
(2026-09-23); SERVICE-INSTALL-06 PostgreSQL/pg_auto_failover DONE (2026-09-24);
SERVICE-INSTALL-07 Redis standalone and Sentinel HA (three members on one host
by default, with three-host placement also required) is NEXT; SERVICE-INSTALL-08 is Vault,
with SI08-A contract foundation DONE, SI08-B DONE, SI08-C implementation and
QA PASS (commit pending), SI08-D implementation/correction QA PASS in the shared
worktree (DIFF-06 resolved by owner-authorized exact correction; no new review),
and SI08-E NOT STARTED. SERVICE-INSTALL-09
is the final one-plan acceptance for eight services. Redis implementation is in progress;
target acceptance has not started.
For SERVICE-INSTALL-07, the service Secrets dialog accepts bounded values
against the verified local catalog without a readiness check. The installation
flow obtains fresh Core requirements and a deployment plan before Start;
Execution Node readiness is an installation prerequisite, not a repeated
service-editor action. Passwords remain session-only.
The completed UI-02E one-host Kafka evidence remains historical evidence.
Milestones and individual acceptance criteria:
[SERVICE-INSTALL-01…07](../work/services/service-install-acceptance.md).

Order: 01 Keepalived → 02 BIND → 03 dns-client → 04 HAProxy → 05 Kafka
(replace the isolated one-target QA deployment with a three-target deployment)
→ 06 PostgreSQL/pg_auto_failover → 07 Redis standalone and Sentinel HA (3/1 and 3/3) with mandatory TLS
→ 08 Vault (1/1, 3/1, 3/3) → 09 all eight services from one shared plan.
SI08-A evidence: [contract foundation](../work/vault/service-install-08a.md).
SERVICE-INSTALL-07 architecture:
[Redis/Sentinel](../work/redis/service-install-07-redis-sentinel-architecture.md).
Before each service installation, identify and remove only its attributable
old QA installation through a proven narrow cleanup path. Record exact targets
and check ports, paths, unit names and neighboring deployment state first.
Core determines dependency ordering and permitted parallelism inside a plan;
one plan does not require simultaneous launch of every service.

SERVICE-INSTALL-06 accepted an isolated three-host PostgreSQL
`pg_auto_failover` deployment: node1 monitor, node2 and node3 database
members. The first Go-managed lifecycle run
`installer-45943379628ebee4a28716d85b571916` completed `SUCCEEDED` in 17m45s
with 65 changes; the fresh repeat
`installer-4fcc0cd5afc8689509aea2e2a49935e6` completed `SUCCEEDED` in 17m9s
with `changed=0`. PKI apply, PostgreSQL apply and verify passed in both cycles.

## EXEC-PLAN-SCOPE-01 recorded prerequisite

After SI09 functional acceptance, plan `EXEC-PLAN-SCOPE-01` separately; it is
NOT STARTED. The current `BuildDeploymentPlan` emits apply/verify actions for
every saved deployment.
Current status and separately authorized scope are recorded in CURRENT_STATE.
