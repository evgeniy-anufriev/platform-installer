# SDKU: corrections after Data Manager deployment

2026-10-17. Owner requested seven corrections after DM deployment. This is a
owner-approved implementation plan after one independent FULL PLAN review;
implementation authorized; no bundle publication, activation or target installation.
Baseline: master 4314e0b7ff1b9186199502d259f2ee4f668710ed. CURRENT_STATE.md
remains the sole status source. Existing SDKU runtime07 stays active.

## Verified causes

1. SDKU base template includes only common static ENV. Each application compose
   template explicitly renders Kafka/Redis target lists. The role's current
   library_runtime.connections actually comes from the current application
   instance, not a library-wide projection. Merely moving those expressions to
   base would make its bytes depend on the consumer. apply_library.yml correctly
   requires identical libraryPath/envContent/baseContent for all consumers.
2. DM's SPRING_KAFKA_SCHEMA_REGISTRY_URL comes from application source_variables.
   Core resolve_connection has no Schema Registry purpose; it cannot supply all
   registries. kafka_schema_registry.registry_projection already projects their
   actual per-member ports and should be reused, not copied.
3. Original image remains unchanged in SDKU defaults and source-inventory.json:
   evoscada-docker.artifacts.tn.tngrp.ru/data-manager:1.5.0-SNAPSHOT-7a795dc1-redos.
   Runtime preflight substitutes authority.requirement.localReference, generated
   as platform-application:sha256-<imageId>. image_delivery tags it deliberately.
4. Generated ENV uses quoted keys for its generic loop and unquoted keys for
   explicit connection/port entries; the base uses to_nice_yaml. YAML semantics
   are equivalent, but source formatting is inconsistent.
5. Role defaults force .local/share/platform-installer, and Core placements force
   applications/<project>/<library>/<app>/<host>. Verify separately rebuilds
   the old path for Vault checks, so changing only Apply would be incomplete.
6. Callback treats only the tagged, successful docker-inspect/state predicate
   failure as APPLICATION_ONLY. HTTP publication belongs to applications:apply,
   but is classified UNKNOWN; _revoke_library_failure then clears the index.
7. Current library-only plan automatically inserts SERVICE_VERIFY when evidence
   is not PASS. assert_admission requires either the approved Verify prefix or
   exact saved evidence. No explicit bypass exists in Core, Go or UI.

## 1. Shared connections and base compose

Add an optional library connections declaration using the same connection
shape as application.schema.json (reuse its schema reference). Declare Kafka,
Redis and Schema Registry once in SDKU library defaults, bound through the
existing library bindings and connection_defaults. No IP/port duplicates in
application defaults or source_variables.

Core resolves those declarations once into the library snapshot using existing
resolve_connection. Extend Kafka connection purpose for schema-registry HTTPS
by consuming the existing pure Registry projection, including enabled state,
all broker members, per-member port overrides and TLS profile. Broker listener
selection must not accidentally filter the separate Registry REST targets.
Stable member ordering; all configured eligible targets, no first-target slice.
No registry enabled means no invented Registry URL; applications requiring it
receive the existing unresolved-connection finding behavior.

Render one host/library base from library common defaults and shared connections.
Expose shared connections as library_runtime.connections; explicit per-application
connection differences remain in application_runtime.connections. Existing
libraries without the optional library declaration retain their current template
context compatibility. Application account/provider declarations retain their
existing role; no second connection resolver in Go/UI.

SDKU backend base environment includes the five owner-listed variables:
KAFKA_BOOTSTRAP_SERVERS, SPRING_KAFKA_BOOTSTRAP_SERVERS, REDIS_ADDRESS,
TN_SCADA_REDIS_ADDRESS and SPRING_KAFKA_SCHEMA_REGISTRY_URL. Registry URLs are
comma-separated HTTPS endpoints, all three nodes for the current deployment.
Confluent documents schema.registry.url as a comma-separated list:
https://docs.confluent.io/platform/current/schema-registry/sr-client-configs.html
This documents the standard client format; actual DM property forwarding remains
an explicit runtime acceptance check, not inferred from that documentation.

Per-application compose emits only application-specific ENV and actual explicit
overrides of common values. Existing library defaults/application defaults/
group_vars precedence and Reset remain authoritative. Frontends keep their
existing native startup and do not inherit backend environment.

## 2. Original image reference and consistent YAML

Keep image-lock's immutable imageId/platform/archive/source authority and the
internal digest alias used for verified delivery. After verified acquisition,
use builtin Docker tasks to tag that exact imageId with settings.image; emit
settings.image unchanged into Compose (including uppercase SNAPSHOT). Check
that the original reference resolves to the locked imageId before compose up;
readiness/Verify continue to check actual container.Image against that imageId.
The private alias is internal and does not replace the operator-visible image.
Repository-first/offline fallback, no-pull behavior and trust remain unchanged.
Test pre-existing wrong tag, acquisition failure, repeated execution and exact
Config.Image spelling. No image or container recreation in this planning step.

Render ENV mapping keys and values consistently with double quotes using existing
Jinja to_json filters, both base and application templates. Do not add a YAML
rewriter, custom serializer or Python helper. Refresh package digests with the
existing validator; preserve typed desired-state values and runtime string ENV.

## 3. Library runtime directory

Add optional typed runtime_directory to the library definition and its deployment
in group_vars. Effective default: ~/<library deployment ID>, e.g. ~/sdku-dm.
Ansible supplies the library ID context for the package default expression;
expand ~ on the target using the discovered Docker service account HOME, never
the workstation HOME or SSH user's home. Overrides accept ~/... and absolute
paths, for example /data/scada/sdku-dm. User-defined directory is the library root.

Layout: <library root>/.base_compose.yml, optional .env, and
<library root>/<application instance ID>/{compose.yml,config,vault,pki}.
Keep existing project/library/container ownership labels and directory guards.
Detect foreign ownership, symlinks, traversal and conflicting library roots
before writes with existing preflight/identity mechanisms; no new path manager.
Use the same resolved placement paths for Apply, Verify, Vault, diagnostics and
cleanup. Add one library directory field to existing library General UI with
Default/override/Reset through the existing guarded writer. No app-level copy.

Existing old paths are not moved or deleted automatically. Changing desired
path is explicit and visible in the next reviewed plan; target migration and
redeployment require a separately approved execution plan. No migration service.

## 4. Verify evidence follows infrastructure stages

Use actual authoritative operation types and phase/action IDs, not a growing
allowlist of individual Ansible task failures. APPLICATION_LIBRARIES_APPLY and
APPLICATION_LIBRARIES_VERIFY failure/cancel/crash never revoke a completed
infrastructure Verify by themselves, including HTTP publication/provider errors.
Remove the application-only/UNKNOWN failure taxonomy and its runtime marker
where it is no longer needed. No replacement persistent failure-domain store.

Retain existing invalidation before infrastructure Apply and before a new
infrastructure Verify attempt, current model/runtime/host-key matching, partial
coverage and crash recovery. Infrastructure-stage failure must not retain
superseded success. No restored proof fabricated from a failed historical run.
Actual provider changes can still be caught by the next explicit Infra Verify;
application-stage failure alone is not authority to erase its old observation.

## 5. Explicit skip of Infra Verify

Add boolean skipInfrastructureVerify, default false, only for the existing
APPLICATION_LIBRARIES_ONLY mode. It is per-plan execution intent, not portable
infrastructure desired state, and is not remembered as a global safe default.

Core is authoritative: true omits SERVICE_APPLY and SERVICE_VERIFY even without
valid prior evidence, and relaxes only the saved-Verify admission condition for
that exact approved plan. It retains target/runtime identity, saved revision,
plan approval/fingerprint, SSH trust, artifact authority, PKI/secret availability,
provider ownership, application preflight and application Apply/Verify.
No PASS is invented; no new saved infrastructure proof is written. Preserve the
real UNKNOWN/STALE/etc observation and expose the explicit skip separately in
plan/result/audit. Turning the flag on/off invalidates the reviewed plan.

Negotiate the changed semantics explicitly through execution-runtime/v1alpha5
Build, plan/v1alpha6, execution-manifest/v1alpha4 and capabilities/v1alpha9,
reusing existing types/lifecycle and shared schema references where possible.
Existing requests retain their default behavior; old runtimes cannot silently
ignore a requested skip. No new execution mode, scheduler or parallel plan store.
Bind the flag into the plan fingerprint and retained Go request; Start rebuilds
that exact request and Core validates the same approved flag before dispatch.

UI: one unchecked checkbox below Infrastructure in the existing Installation
summary: "Пропустить проверку инфраструктуры — принимаю риски". Available only
for library-only mode and capable runtime; disabled during active execution.
Show the selected skip in Review/Approve and Result alongside the real Verify
observation. Changing mode/project resets the choice; never a cached local grant.
Normal existing Approve is the operator's explicit acceptance, no extra modal.

## UI/design discrepancies and acceptance

Existing UI design, mockup and B plan describe mandatory saved PASS or Verify
prefix and do not include an operator skip; owner request7 explicitly proposes
changing this rule. Existing library General lacks runtime_directory. Update
those affected sections and ADR/project/execution contracts with the approved
amendment before implementation. UI remains a projection/editor; no YAML parsing
or infrastructure-policy computation in React/Go.

Focused tests, current sources on configured RED OS via qa-sync:
- Native library render: all shared connection ENV in one identical base across
  apps; only own values/differences in child Compose, frontend opt-out, Reset;
  Registry three members, disabled state, custom ports and TLS projections.
- Native Docker original tag/locked imageId/source fallback and byte-preserving
  tag spelling. Default/custom runtime dirs, traversal/foreign-owner refusal,
  consistent Apply/Verify/Agent paths and path-change evidence.
- Evidence regression: infrastructure Apply/Verify failure invalidates correct
  proof; application publication/readiness/provider failure/cancel/crash preserves
  prior proof; successful fresh verification is still published correctly.
- Explicit skip false/PASS/UNKNOWN/STALE, true with no proof, malformed/unsupported
  mode/runtime, flag tamper/rebuild mismatch, no fabricated evidence, new fresh
  plan required, unchanged secrets/artifacts/preflight behavior.
- Affected Go/frontend checks and real React/Wails library path edit/reset and
  Build/Review flag on/off against real Go/Core; normal bindings only. No target
  Start/installation for acceptance without separate execution approval.

One independent FULL DIFF after implementation. No blanket regressions repeated
without a changed boundary; no new production Python file when tasks suffice.
No deployment/publication or new bundle activation authorized by this plan.

## Owner decision after FULL PLAN review

SDKU-PC-P01 is REJECTED by the owner: sequential execution is a supported
scenario guarantee. No additional daemon/tag lock, guard or concurrency framework
is to be added. Owner explicitly authorizes all seven corrections and prioritizes
standard Ansible tasks; edit Python only for existing target-free resolver and
execution protocol/evidence semantics that cannot be implemented in role tasks.
No target installation or activation. Existing FULL PLAN review findings in
other boundaries remain applicable; final FULL DIFF must use this owner decision.

Implementation compatibility clarification: preserve the original tagged reference
for SDKU (all source images are tagged references). Docker cannot assign an
@sha256 reference using docker tag. Existing digest-pinned operator inputs retain
the prior immutable local delivery/startup alias, particularly for offline loads;
no new network requirement, denylist or source-policy relaxation is introduced.

## Owner-authorized D02/D03 closure

2026-10-17: owner authorizes D02 correction with standard Ansible tasks and D03
positive acceptance on a QA runtime. Build/validate/publish/prepare that runtime
only for target-free plans in an isolated QA project. No application installation
or StartExecution; no additional lock. D02 compares resolved absolute library roots
on each host before provider/materialization stages, rejecting equal/nested roots
of different libraries while allowing sibling roots and placements of one library.
After focused checks, one TARGETED_RECHECK covers D02/D03 and their immediate
boundaries; the rejected P01 stays superseded.
