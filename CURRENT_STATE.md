# Current state

Updated 2026-10-08. This file is the sole current milestone/status source.
Detailed historical checkpoints are archived under [docs/history](docs/history/si11-state-20261008.md).
Read the applicable plan and evidence for the task; an implementation or direct
Ansible PASS does not imply complete UI acceptance. A next gated milestone or
new destructive operation still requires explicit owner authorization.

## Active work and acceptance

| Work | Current status | Evidence and next step |
| --- | --- | --- |
| SERVICE-INSTALL-11 | IN PROGRESS; overall acceptance remains open | I05 PASSED by explicit owner confirmation on 2026-10-08. Close remaining cases and strict repeat evidence separately; see [journal](docs/service-install-11-test-journal.md). |
| SERVICE-UNIT-NAMING-01 | Implementation and focused QA complete; real naming acceptance pending | [Plan](docs/service-unit-naming-plan.md). Requires separately approved S11-00 baseline and real full-service UI naming checks. Prior I05 success does not prove new names. |
| SESSION-RUN-CREDENTIAL-01 | Implemented; real expiry-boundary acceptance pending | [Plan](docs/session-active-run-credential-plan.md). Go tests/vet passed; exercise the real React/Wails flow at the lease-expiry boundary. Owner declined another review. |
| EXECUTION-ORDER-01 | Implemented with focused standalone evidence; remaining acceptance pending | [Plan](docs/execution-order-01-plan.md), ADR-030. Keep source/provider dependency fail-closed; close interruption/recovery, stale-record deletion and real UI gaps. |
| SERVICE-INSTALL-09 ClickHouse | PARTIAL ACCEPTANCE, NOT DONE | [Plan](docs/service-install-09-clickhouse-architecture.md). Direct 1/1, 3/1, 3/3 and endpoint evidence passed; formal terminal real-bridge PASS and strict repeat remain unclosed. Owner previously declined another cumulative SI09 run. |
| EXEC-PLAN-SCOPE-01 | NOT STARTED / deferred by owner | [Acceptance sequence](docs/service-install-acceptance.md), [roadmap](docs/roadmap.md). Separate request required; current full plans are not selective provider reconcile. |
| BROWSER-REMOTE-01/02 | HTTP restricted to explicit dev; HTTPS deferred to version 1.0 | [Remote plan](docs/browser-mode-remote-plan.md), ADR-028. Production transport/credential acceptance is not complete. |

## SI11 current evidence and open cases

I05 is **PASSED**. The owner explicitly confirmed this in the current chat on
2026-10-08; the journal also records successful full-plan completion observed
in the UI. The successful run ID was not supplied in that confirmation.
Do not attach an older failed run ID to the success or downgrade I05 because
of an earlier failure. This confirmation does not mark overall SI11 DONE.

The current journal records:

- I01 and I04: PASSED.
- I05: PASSED by owner confirmation; exact successful run identity remains
  an evidence detail to correlate when available, not a reason to reverse PASS.
- H06/H07, S06 and I02: IN PROGRESS.
- I03: NOT STARTED; isolated rehearsal/cleanup prerequisites still apply.
- L01: FAILED; catalog labels for Keepalived, Kafka and Vault still contain
  English, and remaining screens have incomplete coverage. Translate service
  manifest metadata and regenerate catalog/bundle; do not hardcode service
  translations in React.
- I05-R1 retains its historical Redis failure. The later owner-confirmed
  successful full plan is recorded in I05; do not replace either evidence.

The [UI test cases](docs/service-install-11-ui-test-cases.md) and
[test journal](docs/service-install-11-test-journal.md) define detailed coverage.
The journal is evidence, not permission to perform a new run or reset.
S11-00 (2026-10-01) proved an Installer-free QA baseline, not a pristine OS;
a new cleanup for naming acceptance is separately pending.

## SI11 source corrections and recorded runtime checkpoint

Historical run `installer-90f2d8f56b6b4cf447c630d04bc56fd6` failed during Vault
endpoint integration at events 2922–2926 after earlier service actions passed.
The source used `(record_matches | first).values`, selecting a mapping method;
it now uses `(record_matches | first)['values']`. The production-task test
proves list/address types. Six endpoint, eight HAProxy and 15 BIND tests and
endpoint playbook syntax passed on RED OS. This historical failed run is not
the owner-confirmed successful I05 run.

HAProxy hook phases use the resolved source ID, including standalone inputs.
At that diagnostic checkpoint, `qa-vault-consumer` had no
`haproxy.deploymentRef`, so Core selected no provider and skipped that hook.
Review the current saved relation before claiming external Vault routing.

The last runtime checkpoint recorded in the former state file was bundle
`si11-full-service-20261008-03`, built on node2 and validated/published with
digest `sha256:e77842ff140d641ea80c4b131bb87a0b042e1c4c1985d3dd87fa7b3968e4d99f`.
The former project import and prior active digest were preserved as QA copies.
The project lock was observed changed without an identified rebind actor.
These are recorded checkpoints, **not a live cache/READY assertion**: confirm
the current project, published digest and selected-node preparation before
any newly authorized plan. I05 success does not identify its runtime digest.

After that historical failed run, owner-authorized Vault clear removed owned
member data on node1–node3 while preserving ownership markers, config, PKI
and audit directories. Old bootstrap shares/token became obsolete and must
not be reused. Read the [SI11 history](docs/history/si11-state-20261008.md)
for exact reset evidence; do not infer present target state from that reset.

Earlier controller-preparation failure diagnostics now expose only sanitized
tokens. The lifecycle suite passed 59 tests and independent DIFF approved;
see [diagnostics](docs/execution-failure-diagnostics.md). Redis quoted-path
comparison, ClickHouse stock-unit and Keepalived participant corrections have
focused evidence in the SI11 archive; no new product QA was run for this
documentation reorganization.

## Execution ordering and active-run credential boundaries

EXECUTION-ORDER-01 implements the application priority list, ordered
BuildDeploymentPlan input and Core per-deployment Apply/Verify projection.
Recorded regression: RED OS Core 487 tests (19 skipped), Go test/vet,
frontend typecheck/lint/build and 128 tests passed.

ADR-030: ordinary BIND Apply preserves the existing zone and updates only
base-owned A records; source point updates do not delete records. Explicit
full reconcile is the sole deletion path and uses live SOA serial plus a
machine-runtime freeze/thaw recovery marker. Focused BIND tests (17/17),
node1/node2 Apply/Verify/reconcile and final repeat `changed=0` passed.
Injected interruption/recovery, stale-record deletion and complete source-hook
failure boundaries remain unproven. The earlier checkpoint prohibits a new
service plan under this ordering until those gates close; owner-confirmed
I05 completion alone does not establish which ordering was exercised.

The endpoint hook is wired for Vault, Redis and ClickHouse based on manifest
capability and saved assignment. Kafka/Docker have no endpoint hook;
PostgreSQL is excluded by owner decision. No assignment is synthesized.

SESSION-RUN-CREDENTIAL-01 reserves one Broker slot `STARTING -> RUNNING(runId)`
for approved SSH identity metadata; it survives ordinary lease expiry and
releases only on authoritative terminal state or proven non-dispatch.
Uncertain retries use the same pending plan/attempt. The observer repairs
accepted remote Starts whose local persistence failed. Credential replacement,
clear and host-key trust changes are blocked while the slot is occupied.
Real React/Wails expiry-boundary acceptance remains pending.

## Other retained decisions and accepted baselines

- Remote Linux Browser HTTP requires `-browser-allow-insecure-dev-http` and
  is prohibited for production systems/data. HTTPS/external origin and secure
  credential/secret transfer are deferred to version 1.0. Local Windows
  Browser and Wails are outside this specific HTTP restriction.
- RUNTIME-BUNDLE-UX-01A has local real-UI rebind evidence; see
  [rebind plan](docs/runtime-bundle-project-rebind-plan.md) and
  [workflow history](docs/history/workflow-state-20261008.md). It does not
  prove a clean-node bootstrap or close overall SI11 acceptance.
- Service settings use ordinary Ansible defaults/desired overrides. UI/Core
  previews are derived; PostgreSQL TLS usages retain the explicit PKI plan
  boundary. See [defaults plan](docs/si11-ansible-role-defaults-plan.md).
- Managed Kafka/PKI projections are runtime-only. Local structural Save is
  node-free; Project Verify is revision/runtime-bound, target-free and does
  not authorize execution. Every execution needs a fresh authoritative plan.
- Application server-type IDs are metadata with no service/placement/source
  authority; unknown valid IDs are preserved without automatic backfill.
- At most one Redis deployment per project was owner-approved; cumulative
  QA uses Sentinel HA, while standalone QA uses an isolated project.

Accepted baselines include CORE-01–07/07A, EXEC-01/01A, PKI-01,
SERVICE-01A–01D/02A, POSTGRES-01, NET-01–04.2, UI-BE-01–04,
EXEC-OBS-01, UI-01 overall and UI-02 overall. Their dated evidence is in
[milestone history](docs/history/milestones-state-20261008.md) and linked
milestone documents. These baselines do not close later regression gates.
SI08-F Vault endpoint HA technical acceptance and SI10 Docker rootless/Compose
are DONE with real initial/repeat UI runs and `changed=0` evidence; see
[Vault history](docs/history/vault-state-20261008.md) and
[Docker evidence](docs/service-docker-rootless-architecture.md).

## Next authorized work and maintenance

The owner authorized this documentation/context optimization and explicitly
confirmed I05 PASS. This does not authorize new service runs, S11-00 cleanup,
next gated milestones, credential/trust replacement or architecture changes.
Continue an existing product task only within its established authorization
and fresh prerequisites; consult the relevant plan/journal first.

Keep this file compact: update these entries, put detailed run evidence in
the relevant journal, and link it. Do not prepend execution narratives or
copy historical DONE/NEXT lists. Before gated work, verify the exact checkout,
saved revision and current runtime rather than treating archived facts as live.
Use [agent index](docs/agent-index.md) to choose the required reading and
[maintenance record](docs/agent-context-maintenance.md) for archive provenance
and documentation verification.
