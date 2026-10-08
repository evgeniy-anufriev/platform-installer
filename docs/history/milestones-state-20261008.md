# Historical state snapshot — 2026-10-08

Historical evidence only. Statements such as NEXT, NOT STARTED and DONE below
describe their original checkpoint and may be superseded. Read
[CURRENT_STATE.md](../../CURRENT_STATE.md) for current status and authorization.
Original section text is preserved; relative Markdown destinations are relocated.

## SERVICE-INSTALL-10 Docker rootless + Compose DONE (2026-10-01)

Owner reassigned SI10 to Docker rootless + Compose; the all-services single-plan
cycle is SI11, now in progress. [SI10 architecture and evidence](../service-docker-rootless-architecture.md).
Autonomous RED OS Ansible existing-user/create-user apply, verify and strict
repeat passed (`changed=0`). The two owner-approved DIFF blockers were
corrected and the single targeted recheck passed with zero blockers. Docker's
rootless-extras RPM is `noarch`; its exact manifest requirement was corrected
without weakening the generic source policy. The immutable QA runtime digest
is `sha256:46fbb7be6578c5e5c004188e7ad6b8b4945ab8519365a820374d4d61e8770165`.
Real nonvisual React/Wails -> Go -> READY Execution Node plan/start produced
`installer-b37382a3d07ccc3ce4472f2d251274db` SUCCEEDED and a strict repeat
`installer-5c5f5df7fa464a1f7ace36eae87209dc` SUCCEEDED. The repeat had
PKI/Docker apply/verify SUCCESS, zero CHANGED/FAILED tasks and terminal state
observed through the Wails binding. The selected rootless systemd target,
bridge and user service stopped on LXC stop, rejected manual start before
readiness, restored on late LXC start and recovered automatically after QA
reboot. Compose and mutual-TLS API positive/negative probes passed; rootful
Docker service/socket stayed inactive. Full RED OS Core suite passed 419 tests
(19 skipped), focused Docker tests 2/2 and playbook syntax passed. Go full
test/vet, affected RED OS race tests, frontend lint/67 tests/build, Wails
production build, catalog/schema reproducibility, focused secret audit and
`git diff --check` passed. This is completed SI10 Docker evidence, not proof
that Docker has been installed in the current SI11 all-services cycle.

## SERVICE-INSTALL-09 ClickHouse PARTIAL ACCEPTANCE, NOT DONE (2026-09-29)

Owner requested the next service: ClickHouse 1/1 standalone without Keeper,
then 3/1 and 3/3 with one paired server+Keeper member per replica, TLS on all
enabled protocols and an HTTPS endpoint. The all-services one-plan final
acceptance was subsequently assigned to SI11. Architecture plan:
[SI09](../service-install-09-clickhouse-architecture.md). The first FULL
PLAN review identified source-authenticity and HTTPS-authentication gaps; the
owner approved signed upstream repository metadata plus exact RPM checksums,
and the standard ClickHouse `default` password supplied through Installer
Secrets. The single allowed targeted recheck APPROVED both findings with zero
blockers. Four exact `26.8.14.3` LTS RPMs were acquired through the signed
official repository metadata and rehashed after copy into ignored DEV import.
The temporary RED OS acquisition workspace was removed. The ClickHouse service
manifest, generated configuration schema/catalog, and TLS-only Ansible role
were implemented. A RED OS target-free topology/secret
contract test passed for standalone 1/1 and paired HA 3/1; read-only package,
path, unit and listener preflight passed on node1. Apply/verify syntax-check
passed. Direct standalone 1/1 Ansible apply and authenticated HTTPS verify now
PASS on node1; repeat apply PASS with `changed=0`. The standalone run neither
installed the Keeper RPM nor created a Keeper unit; its server unit is active.
The first apply exposed non-traversable shared Execution Node directories, so
the role now uses dedicated ClickHouse roots. A service-start race and a
systemd template newline defect were corrected before the passing repeat.
An immutable ClickHouse runtime is published. The terminal real-bridge
acceptance remains incomplete as detailed below.
The first direct HA 3/1 attempt stopped during package installation: the
official Keeper RPM conflicts with the official server RPM on the same host.
The installed pinned server RPM already owns a working Keeper executable.
The service package closure was narrowed to common-static,
server and client; HA now checks the Keeper binary's RPM owner before
starting distinct Keeper units.
Direct Ansible HA 3/1 now PASS on node3: three server plus three Keeper units,
one row replicated across all three authenticated HTTPS members, and repeat
apply `changed=0`. Direct Ansible HA 3/3 also PASS on nodes1–3: one paired
member per host, a row written on node1 visible from all three, and per-host
repeat apply `changed=0`. With only the owned node3 server+Keeper units stopped,
nodes1–2 committed and read a second row; after restoring those exact units,
node3 read both rows. A strict `interserver_https_host` value from each member
address was required for verified interserver TLS. This is direct-Ansible
evidence. The corrected immutable QA release
`sha256:e0665a237c99ae18c3501ec088abaafcdc12a033e0d7b17dabee9983c01d76b1`
is activated READY on node1. The cumulative saved project revision is
`sha256:5afa228cea02912cc07351e1864fce9a89fea435dbc6bfa40785c0deb2a002b5`.
Real nonvisual React/Wails built and approved plan
`plan-4a9a1b6e6ede9da9d358a8ce`, then started
`installer-f1c76b8b08a861e5cd10257ddc679809`. This cumulative full-plan
run terminated FAILED at `apply:service-install-04-haproxy`, after ClickHouse
apply SUCCEEDED. The HAProxy TLS probe had supplied empty stdin to
`openssl s_client`, which could wait until timeout despite valid TLS. The
bounded fix supplies `Q`; focused RED OS tests and syntax-check pass. The
corrected HAProxy direct apply passed on all three nodes after an exact
active-to-temporary-candidate recovery of the failed prior attempt. This
manual QA recovery is not a general production recovery fix.
The earlier full-plan run `installer-f477972a2d8afd831e67e2f07f119963`
FAILED at Vault audit-space preflight: node1 had ~0.8 GiB free against its
1.6 GiB requirement. Twelve old inactive QA runtime releases were removed
after checking active release and terminal run state; node1 then had ~3.1 GiB
free. This failed run is not acceptance. The SI09-DIFF-01 targeted recheck
APPROVED the bounded ClickHouse path-safety correction, zero blockers.
ClickHouse direct 3/3 verify passed on immutable release
`sha256:4c87562e21981f4cc5ec742dacf1d6f010ea89cf8da2175665aa5c55d48fcec0`
(READY on node1), saved revision
`sha256:4f969e072089c76579be1c22be2193ff287516559f13f1158cdf6d7a74b82536`:
node1/node2/node3 each `ok=67 changed=0 failed=0`. A strict direct repeat
ClickHouse apply passed with `changed=0` on all three nodes (156 OK per host).
The canonical server and Keeper units are active on each node. BIND on all
three nodes resolves the ClickHouse name to VIP `192.168.56.121`; each HAProxy
has the ClickHouse 3-member backend with CA and hostname verification, and an
HTTPS `/ping` through DNS/VIP/HAProxy returned 200. This is isolated service
and endpoint evidence, not a terminal PASS of the full UI lifecycle.

The owner explicitly declined another cumulative full-plan run and requested
partial acceptance. Therefore the required real React/Wails -> Go -> Execution
Node terminal PASS is absent: SI09 remains NOT DONE. The next formal gate is a
new terminal PASS and strict repeat through the real bridge, if later
authorized. SI10 is Docker acceptance as recorded above; SI11 is now in
progress, with no all-services installation run yet.
Owner deferred generic scoped endpoint-provider execution to the separate
NOT STARTED `EXEC-PLAN-SCOPE-01` milestone after SI09 functional QA. Current
full-plan execution must not be misreported as selective provider reconcile.

## Dev-only path selection seam: real encrypted import PASS (2026-09-27)

Owner approved nonvisual React/Wails selection substitution. A private picker
function defaults to native OpenFileDialog; dev-only startup configuration
accepts a bounded finite queue of absolute paths. Production !dev ignores it.
No new Wails method, plaintext/payload transport or alternate import path.
Descriptor authorization, bounded handle reader, age parsing/decryption, final
binding recheck and session broker remain the existing implementation.
Real React Services/Secrets -> existing Wails method: admin-token.age STORED,
unseal-shares.age STORED; REAL_REACT_WAILS_SECRET_IMPORT=PASS, READY PASS.
No native dialog/Computer Use, new Start or Vault mutation in this focused probe.
Known dev ipc.js renderer exception remains; this is not clean UI/full Vault
acceptance. SI08-E apply/verify/repeat/HA gates still pending.
Focused production/dev tests, full normal-build Go suite and vet normal/dev PASS.
Wails production build PASS (8.592s) after owned dev server stopped.
Temporary QA RSA admission removed with confirmation. Independent scoped DIFF
review APPROVE_WITH_CHANGES, 0 blocking; NFS-01 nonblocking production isolation
test strengthened with callable sentinel for valid/malformed env, focused PASS.
RED OS normal-build CGO race PASS (1.119s). RED OS dev-build race UNAVAILABLE:
GTK3/WebKit2GTK development packages absent; no host packages installed to bypass
this prerequisite. Windows dev unit tests and real bridge import PASS are separate.
Earlier unrelated dirty work retained; SI08-E not DONE and no clean-worktree claim.

## Continued Vault import blocked by Computer Use input (2026-09-27)

Real React/Wails retry: credential PRESENT, READY PASS; native secret picker
opened as a separate returned Window with the headless-owner helper. No Wails
focus crash occurred. Computer Use set_value failed with UIA cache-property error
(0x80070057). Fresh focus observations after activation, Alt+n, Ctrl+l and Tab
did not change from the search field. No filename was typed blindly and no
encrypted-file import success or new Start was observed. This is an automation
input blocker, not Vault execution or secret validation. The initialized Vault,
ciphertext custody files and committed journals remain untouched.
Harness and owned dev servers stopped; temporary RSA removal confirmed
QA_KEY_REMOVED. Dev-server output also contains WebView2 ProcessFailed kind 6
and the existing ipc.js renderer exception; do not claim clean WebView acceptance.
SI08-E remains BLOCKED pending reliable native-dialog input; no DONE claim.

## Native dialog headless-owner workaround verified (2026-09-27)

QA helper scripts/qa-native-dialog.cjs uses supported Wails WindowHide before
the real native action and WindowShow in finally. This exposes an actual
independently targetable dialog without changing production Go, dependencies,
native import validation or credential semantics. Three helper tests PASS.
Real secret-free ChooseProject cancellation returns NO_PROJECT; a subsequent
real GetApplicationConfig returns READY. No WebView2 process exit in this probe.
The previous missing-modal limitation is therefore avoidable in headless QA.
Vault harness now wraps its real React file-selection handler in this helper.
First continued acceptance attempt timed out waiting for rendered READY; fresh
SSH probe succeeded and real CheckExecutionNode returned READY. Retry in progress;
no new import/Start or overall SI08-E success claimed at this point.

## Native dialog targeting cannot be completed through current CUA API (2026-09-27)

Owner-authorized QA-only correction: refuse native-dialog input unless exactly
one actual returned Window matches both Installer app identity and dialog title;
never fall back to its disabled main-window owner or fabricate a modal handle.
Runtime-only helper and two focused tests exercise this guard.
A real Wails ChooseProject folder-dialog probe, without secrets or targets,
confirmed both list_windows and list_apps expose only the main Installer window.
Accessibility confirms that owner is disabled and the folder modal is a nested
element, not a returned independently targetable Window. No activation/input was
sent to that disabled owner. Native import acceptance remains BLOCKED by this
Computer Use targeting limitation; the guard prevents repeating the unsafe
automation action but is not a completed file-import fix. No production or
dependency change, no secret import, no Start or Vault mutation.

## Secrets descriptor wire correction verified (2026-09-27)

Owner-authorized bounded correction adds explicit lower-camel JSON tags to
RuntimeSecretDescriptorOperation/View, preserving existing descriptor semantics.
Generated Wails models refreshed/formatted; two focused wire tests prove exact
field names, round-trip data and safe unavailable response.
Actual React Services -> vault-qa-standalone -> Secrets, through real Wails Go
methods, returns READY with two descriptors and renders two file-input controls.
No secret file import, new Start, init/reset/unseal or target deployment was
performed by this focused probe. This closes the descriptor wire blocker only;
SI08-E full Vault acceptance remains pending, not DONE.
Focused Go tests PASS; go test ./... and go vet ./... PASS; frontend lint,
67 tests and build PASS; wails build -nopackage -clean PASS (11.257s).
RED OS CGO race tests for descriptors, pending-output list and concurrent
binding guards PASS (1.080s), using current qa-sync source.
SSH recovered; exact temporary QA RSA key removal confirmed QA_KEY_REMOVED.
Previous pending workspace cleanup completed via qa-sync. Earlier unrelated
uncommitted changes remain preserved; no clean-worktree or milestone claim.

## Output list guard fixed; real delivery PASS; Secrets DTO blocker (2026-09-27)

Cleanup caveat: after local dev servers stopped, RED OS race SSH connection
closed; a fresh bounded SSH probe timed out during banner exchange. Race is NOT
PASS. Removal of this attempt's temporary RSA admission was issued but completion
was not confirmed; do not report the key removed. qa-sync workspace
/var/tmp/platform-installer-qa-fa6f3340b14d40e69747697502478238 remains pending cleanup.
Restore SSH access before confirming exact-key removal and workspace cleanup;
do not reboot targets or delete custody as a workaround.

Owner-authorized ListPendingSecretOutputs guard now re-resolves the existing
private binding and checks binding/node/runtime/READY plus project/generation.
External selection remains free of a synthetic SelectedHostID. Existing positive
test uses real external context; 9 deterministic concurrent-change cases reject
the response. Focused Go, full Go tests/vet and diff check PASS.
Real React/Wails Result recovery: READY package
805b1d37fb4b8c901369d2901dc8f41d from run
installer-6989b0f2fb6c2609515170ece9c9eeb7 delivered/encrypted successfully.
Local secrets/vault-qa-standalone contains admin-token.age, unseal-shares.age and
complete receipt; no plaintext file/content exposed.
Subsequent real Services/Secrets import blocked before native picker: Wails
GetPendingRuntimeSecretDescriptors returns uppercase Status/Descriptors while
React expects lowercase status/descriptors. RuntimeSecretDescriptorOperation
and RuntimeSecretDescriptorView lack JSON tags (app.go). No new Start/init/reset.
This separate wire-shape correction is proposed, not implemented here.
SI08-E remains BLOCKED; earlier changes preserved; no overall DONE claim.

## Seed identity ordering correction implemented (2026-09-27)

Owner authorized bounded fix of the SI08-E unseal blocker. unseal_member.yml
now captures seed cluster_id only from confirmed initialized/unsealed health,
after requiring a nonempty string identity. Followers still compare their own
post-unseal identity to the seed; no pre-unseal cluster_id is required.
No init/custody/protocol change; no_log retained. No target reset or unseal run.
Current-source RED OS: 4 new real-Ansible synthetic boundary tests PASS (9.358s),
in both native modes; Vault contract 15 PASS (0.425s); apply/verify syntax and
catalog/schema reproducibility PASS. Full Go tests/vet/diff check PASS.
QA workspace cleaned. Correction remains uncommitted/unpublished; real
React/Wails acceptance remains pending and SI08-E is not DONE. Next run must
use retained admin-token/unseal-shares through the supported secret-input flow,
not reinitialize the now-initialized seed. Previous dirty changes preserved.

## Bounded failure diagnostics implemented; runtime acceptance pending (2026-09-27)

Owner-authorized isolated audit-directory task PASS changed=false (5.724s),
with mountpoint identity, inactive Vault unit and committed journal unchanged.
Original failure did not reproduce; removed temporary QA key was not reinstated.
Controller now derives a closed coarse diagnostic class from the final ordinary
Ansible failure record when no explicit Core error_code exists. Raw output stays
bounded/in-memory; no_log/censored results stay opaque. No service/retry semantics
or public protocol change. Details: docs/execution-failure-diagnostics.md.
Current-source RED OS: 6 new tests PASS, observability 21 PASS / 4 opt-in SKIP,
lifecycle 39 PASS. Full Go tests/vet and diff check PASS; qa-sync workspace cleaned.
New runtime publication and real React/Wails acceptance remain pending; no full
Apply or bootstrap was run. SI08-E remains BLOCKED; earlier dirty work preserved.

## Vault explicit clear corrections complete; targeted DIFF PASS (2026-09-27)

Owner authorized exact SI08-CLEAR-DIFF-02/03 corrections. Process guard now
matches both exact config forms independently of argv[0]. Vault-only no-follow
fd traversal checks opened inode identity and Linux mnt_id before each descent;
missing/malformed mount evidence blocks clear. No generic framework or normal
Apply/Verify change.
Focused RED OS clear 18 PASS (1.839s), Vault contract 15 PASS (0.515s), syntax
PASS; independent full Core 387 total / 383 PASS / 4 opt-in SKIP / 0 errors
(174.730s), catalog/schema, full Go tests/vet and diff check PASS. Tested source
hashes match the reviewed revision.
One independent targeted recheck APPROVE: DIFF-01 remains RESOLVED, DIFF-02/03
OPEN -> RESOLVED, zero blocking/overengineering findings. Reviewed ordinal
fingerprint `1f30018aa7b9db71f591dfe54b28117608b38e73bc50bb359163301a7baead5a`.
QA source workspace was cleaned. Actual reset and SI08-E acceptance are still
not claimed; subsequent reset requires fresh exact identity/no-active-run proof.
Evidence: docs/service-install-08e-clear-evidence.md. Earlier unrelated
uncommitted work is preserved; clear is a separate focused implementation.

## Vault clear resumed FULL DIFF: two safety blockers (2026-09-27)

Owner authorized commit/continuation. Resumed SAME incomplete FULL DIFF on
unchanged fingerprint `86df9179819d462aaa11813072c70ec9645be9a643a522b7e8e7ef3a872f37e3`.
SI08-CLEAR-DIFF-01 envelope mismatch is reviewer-verified RESOLVED. Review now
completed with BLOCK: SI08-CLEAR-DIFF-02 process admission relies on argv[0],
and SI08-CLEAR-DIFF-03 one-shot mount admission does not exclude later movement
of a directory containing an inherited mount into the deletion subtree.
The second finding is a static counterexample, not an experimentally reproduced
deletion. Smallest corrections: exact config-argument guard independent of
argv[0], and descriptor mount-identity checks before each directory descent,
with focused real-process and synchronized mount-movement tests.
No automatic correction/re-review, commit or destructive execution. Owner
decision on these two bounded safety corrections is required. Existing tests
remain regression PASS but do not prove the missing cases. QA identity chain
project/run/operation/member/unit/config/data was read-only rechecked PASS;
active Installer runs and Vault lock holders were zero at inspection.

## Vault explicit clear implemented; DIFF revision-envelope blocker (2026-09-27)

Owner approved the concrete clear plan. Added standalone clear playbook,
clear_entry/clear tasks, exact confirmation default and narrow held-descriptor
Vault member helper. Apply/Verify are unchanged; actual Raft data has not been
cleared and no service was stopped. Current owned unit passed read-only helper
inspection (`inspect_only=true`, changed=false).

RED OS focused clear 15 PASS, Vault contract 15 PASS, standalone clear syntax
PASS; independent full Core 384 total / 380 PASS / 4 opt-in SKIP / 0 errors,
177.032s; catalog/schema reproducibility PASS; full Go tests/vet and diff check
PASS. Seven tested source file hashes match the local implementation.

FULL DIFF reviewer returned BLOCK, SI08-CLEAR-DIFF-01: supplied fingerprint
used PowerShell cultural sorting instead of the stated ordinal sorting.
Read-only reconciliation confirms unchanged file hashes; corrected ordinal
fingerprint matches reviewer exactly:
`86df9179819d462aaa11813072c70ec9645be9a643a522b7e8e7ef3a872f37e3`.
No automatic review rerun or destructive execution. The safety review is not
complete; owner authorization is needed for review continuation/recheck with
the corrected identity. Evidence: docs/service-install-08e-clear-evidence.md.
No commit; unrelated existing worktree changes are preserved. SI08-E acceptance
remains BLOCKED.

## Application config and server type foundation (2026-09-14)

`OWNER-APP-CONFIG-01/02` is implemented. Repository development configuration
is the versioned `config/application.yml`; it currently declares `infra`,
`app` and `db`. New Installer sessions emit additive
`project-edit/v1alpha3`, whose `CreateServer` requires one grammar-valid type;
absence from the local configured list is warning-only.
Published v1alpha2 remains unchanged and both versions use the same Go
`EditCommand` model.

Canonical projects store only the grammar-valid ID as optional-on-legacy-read
`platform_host.type`. Core projects it through the existing
`ProjectSnapshot.hosts` object. Missing legacy and locally unknown valid types
are preserved without backfill; unknown configured types produce only a
nonblocking Installer diagnostic and do not alter Core status, validation or
fingerprint. Type has no service, topology, placement, Execution Node or source
selection semantics. UI-01E1 through UI-01E6 and UI-01F1 through UI-01F3 are
DONE; UI-01F4, UI-01F5 and UI-01F6 are DONE. UI-01F overall is DONE; UI-NET-01 is DONE (evidence: `docs/ui-net-01.md`), UI-01G1 through UI-01G4 are DONE (evidence: `docs/ui-01g1.md`, `docs/ui-01g2.md`, `docs/ui-01g3.md`, `docs/ui-01g4.md`), UI-01G overall is DONE, and UI-01H overall is DONE (evidence: `docs/ui-01h4.md`); UI-01I is DONE (evidence: `docs/ui-01i.md`); UI-01J is DONE (evidence: `docs/ui-01j.md`); UI-01 overall is DONE.

## UI-01 implementation status (2026-09-07)

UI-01A through UI-01D are DONE. UI-01D was accepted by the owner without a
final revision-bound review. UI-01 overall is DONE; UI-01E1 through
UI-01E6 and UI-01F1 through UI-01F6 are DONE; UI-01F overall is DONE and UI-NET-01 is DONE while UI-01G overall and UI-01H overall are DONE; UI-01I and UI-01J are DONE, and UI-01 overall is DONE. UI-01B adds only the Wails/React read-only
shell and fixed `BuildProjectSnapshot` protocol operation; it adds no writer,
edit/session, candidate, save or apply path.

ADR-027 is implemented pre-UI-01E5 without changing milestone statuses. New
Installer sessions use local structural review and the existing guarded writer;
Save requires no Execution Node/Core call and returns a locally projected saved
revision. Reopen without a node reads only directly Installer-owned canonical
server fields. Explicit Project Verify runs the existing target-free
`BuildProjectSnapshot` operation, binds derived in-memory evidence to the saved
revision/attested active-runtime identity, and never mutates project files. A semantic Save
makes the new revision `UNVERIFIED`. Fresh `BuildDeploymentPlan` remains mandatory
before execution. UI-01E5 is DONE: readiness/preparation and navigation gating
use only the startup trusted binding, with explicit Prepare confirmation and
fresh post-Prepare Verify evidence. UI-01E6 is DONE: real Wails creation,
READY/navigation acceptance, target-free Core proof and RED OS regression
passed without service or target mutation; see `docs/ui-01e6.md`.

The 2026-09-05 accepted freeze is `docs/ui-01a-contract-freeze.md`; toolchain, mockup
reconciliation, reviews and QA are recorded in the adjacent `ui-01a-*`
documents. It fixed the one-file empty project (`project.yml` only), exact lock
provenance, first-save ownership, then-current complete-candidate Core proof,
project-edit v1alpha2 evolution, missing server/topology/PKI commands, and
runtime-only session credentials. ADR-027 supersedes only its Core-before-Save
requirement; its ownership and transaction protections remain. Historical
Core-contract and safety reviews reported 0 blocking findings.

The implementation sequence remains `docs/ui-01.md` (UI-01B through UI-01J).
Every milestone requires pre-start and acceptance mockup/contract checks.
Editor order is Servers → Topology → Certificates (PKI intent) → Service
settings. UI-02 execution/task-stream UI and target secret lease transport
remain separate.

## UI-02 installation workflow (2026-09-22)

UI-02A is DONE. It adds the closed local `InstallationState` Wails projection
and the read-only Summary → Plan → Execution → Result Installation surface.
It performs no Core, Execution Node or target call and has no plan creation,
approval, Start, cancellation or secret path. UI-02B is DONE: it adds fresh
target-free planning, closed plan projection and exact acknowledgement approval
for the current saved revision/runtime binding, with no Start, cancellation,
secret or target-contact path. UI-02C is DONE: `ExecutionService` uses only
the closed v1alpha2 credential-lease/Start lifecycle, while the Execution Node
creates the authoritative run ID and durably binds attempt, run and lease
before controller launch. Focused Windows and RED OS gates passed without a UI
Start path, runtime activation or target contact. UI-02D is DONE: the App
wires the runtime-only broker to the existing credentialed Start seam, projects
only closed execution event/result DTOs, and owns bounded local observer
subscriptions that detach without remote cancellation. Its generation-bound
publication prevents an old asynchronous Start/Subscribe result from binding
to a replacement project or Execution Node. UI-02E is DONE: the immutable
release `sha256:6d85afb53c6994f2f1b152e29b39a329ed35a9af7ed3e9c802be0e888993dca0`
completed two production-shaped one-host/three-member Kafka lifecycle cycles
through `CreatePlan -> ApprovePlan -> Start`. Runs
`installer-a21c3eed1d053ac7ef073e13214349a6` (12m16s) and
`installer-a3a4bba6fb97f41b21080ae22c00bcbb` (12m42s) both returned
`SUCCEEDED`; the repeat apply returned `changed=0`. PKI/Kafka apply and verify,
local Go/frontend/Wails gates, RED OS Core/race gates, reproducibility and
hygiene passed. UI-02F is DONE: it adds bounded Core-derived service-secret
descriptors, descriptor-bound session-only values, v1alpha3 lease admission
and the generic Services-page Secrets dialog without secret persistence or
projection. RED OS Core full suite (292 PASS, 4 skipped), lifecycle suite
(31 PASS), Go/frontend/Wails gates and catalog reproducibility passed. UI-02
overall is DONE. Evidence: `docs/ui-02a.md`,
`docs/ui-02b.md`, `docs/ui-02c.md`, `docs/ui-02d.md`,
`docs/ui-02e-pki-runtime-secret-transport.md` and
`docs/ui-02-architecture.md`.

## Next acceptance sequence (2026-09-23)

SERVICE-INSTALL-01 Keepalived is DONE: two production-shaped lifecycle runs
through the cumulative QA project completed `SUCCEEDED`; the repeat applied
`changed=0`. The current VIP owner is node2. SERVICE-INSTALL-02 BIND is DONE:
two production-shaped lifecycle runs completed `SUCCEEDED`; the first wrote
machine-owned generated state once and the fresh repeat applied `changed=0`
after reading the same project-identity-bound state outside its run workspace.
SERVICE-INSTALL-03 dns-client is DONE: two fresh production-shaped lifecycle
runs completed `SUCCEEDED` through the cumulative project; both recorded
`changed=0` after the corrected DNS-client verify task. SERVICE-INSTALL-04
HAProxy is DONE: two fresh Go-mediated lifecycle runs completed `SUCCEEDED`;
the second full cumulative plan recorded `changed=0`, and `haproxy.service`
is active on node1, node2 and node3. SERVICE-INSTALL-05 Kafka is DONE: the
canonical three-member deployment was accepted on three distinct target hosts;
the historical one-target QA deployment is not current deployment evidence.
SERVICE-INSTALL-06 PostgreSQL/pg_auto_failover is DONE (2026-09-24): the
isolated three-host Go lifecycle accepted a monitor on node1 and database
members on node2/node3. First run
`installer-45943379628ebee4a28716d85b571916` reached `SUCCEEDED` in 17m45s
with 65 changes; repeat run `installer-4fcc0cd5afc8689509aea2e2a49935e6`
reached `SUCCEEDED` in 17m9s with `changed=0`; both PostgreSQL verify actions
passed. By owner decision, SERVICE-INSTALL-07 is active: implement and accept
Redis `standalone` on one host and Redis/Sentinel HA with three paired members
on one host by default, with distributed three-host placement also required;
both use mandatory TLS through standalone Ansible, Core, Go
and Wails/React. Its plan is
`docs/service-install-07-redis-sentinel-architecture.md`; implementation and
acceptance are in progress. The standalone Go lifecycle passed twice:
`installer-a641eec3e9ac20867bde45bccd36dec9` succeeded with 17 changes and
`installer-679e49f37f791802b19fe3b1b07025ca` succeeded with `changed=0`.
The Sentinel 3-member/1-host deployment was added to the cumulative project;
its first full plan, `installer-8d2639ea1adaca620772383631a8a534`, failed before
Redis apply in PostgreSQL TLS resolution because several deployments shared a
TLS profile and the role selected only by host/profile. The working-tree fix
passes focused selector/lifecycle tests, all 307 Core tests, and syntax checks
for PostgreSQL, Redis, HAProxy and Kafka playbooks. A fresh immutable runtime
release must be activated before retrying the cumulative plan; Sentinel
3-member/3-host acceptance remains pending. Owner decision: at most one Redis deployment per project;
standalone QA uses an isolated project and Sentinel HA is the sole Redis
deployment in the cumulative project. Owner-approved Secrets UX for SI07:
the service dialog accepts bounded runtime-only passwords from a trusted local
catalog without Execution Node readiness; Core reconciles requirements and
the mandatory fresh plan at the installation gate, before Start. Local format
checks run immediately. The architecture-only Secrets review returned
APPROVE_WITH_CHANGES with no blocking findings; its two wording/lifecycle
clarifications are incorporated in the SI07 plan. SERVICE-INSTALL-08 is the
subsequent one-plan acceptance for all
seven services from one shared project and one approved plan, followed by
verify and a fresh repeat plan proving `changed=0`. Deployment-scoped cleanup
and before/after isolation checks must preserve other QA deployments. Exact
target addresses and resource ownership must be established before execution.
Ordered milestones: SERVICE-INSTALL-01 Keepalived, 02 BIND, 03 dns-client,
04 HAProxy, 05 Kafka (three targets), 06 PostgreSQL/pg_auto_failover DONE, 07
Redis standalone plus Sentinel HA ACTIVE, 08 one plan for all seven NEXT. Conditions: `docs/service-install-acceptance.md` and
`docs/roadmap.md`, "Post-UI-02 service installation acceptance".

## EXEC-OBS-01 completion (2026-09-05)

EXEC-OBS-01A through 01D are DONE. Managed Ansible task events use the existing
ExecutionEvent contract and authoritative Execution Node journal. Go
RunObserver provides pagination, replay, bounded typed subscriptions and the
derived Installer-side `.runtime/executions/<runId>/events.jsonl` mirror.
CLI `-command execution-watch -run-id <id>` prints the exact node/run/path,
follows until terminal and detaches on Ctrl+C without cancelling execution.

Real three-node Kafka runs `installer-1788591717613836600` (11m56s) and
`installer-1788592474776987100` (9m07s) both completed SUCCEEDED with PKI apply,
Kafka apply/verify, repeat changed=0, and 1,723 events each. Local mirror,
typed subscriber and remote stream matched. Live client/CLI restart and
Get-Content -Wait were proven. Real no_log/failure/degradation tests, Core,
Kafka/PKI, Go/race/vet, reproducibility, offline validation and secret audits
passed; both reviews have 0 blocking findings. See `docs/exec-obs-01.md` for
exact commands, test counts, durations and performance measurement limits.

UI-01A is the completed documentation freeze. UI-01B is DONE: its native
Windows Wails shell opens an existing project read-only through a READY
Execution Node and Core's fixed target-free ProjectSnapshot operation. UI-01C is
DONE: metadata-only local creation publishes one managed `project.yml`, and
empty-project reopen remains local without a Core snapshot. UI-01D is DONE by
owner acceptance without final revision-bound review: the Go-owned bounded
transient session, negotiated remote complete-candidate Core proof, guarded
first write and narrow Wails review/save shell passed Windows and RED OS
acceptance. UI-01E1 is DONE: new sessions use v1alpha4 server CRUD intents;
Core projects desired hostname, normalized SSH port and generic host references;
the staged Core-backed review/commit lifecycle is retained as historical
acceptance evidence, while ADR-027 defines the new local Save target. UI-01E2
Servers UI, UI-01E3 shared runtime session credentials, UI-01E4 Execution Node selection, UI-01E5 readiness/preparation and UI-01E6 cross-platform acceptance are DONE. UI-01F1 is DONE: lock-bound catalog and managed local topology reads passed. UI-01F2 is DONE: additive v1alpha5 topology intents, both placement forms, the final-state reducer and existing guarded local Save/reopen path passed Windows and RED OS gates with zero blocking review findings. UI-01F3 is DONE: the catalog-driven deployment editor, shared structural draft, local Review/Save and node-free reopen passed Windows and regression gates. UI-01F4 is DONE: shared member- and host-scoped placement editors use the existing session/review/local Save lifecycle; deterministic Wails frontend acceptance covers Save/reopen/clear without Core, Execution Node or target contact. UI-01F5 is DONE: Entry points reuses the five v1alpha5 endpoint intents; strict typed/bounded Go projection keeps raw Core endpoint/provider maps out of React, and INVALID exposes findings only. UI-01F6 is DONE: built Windows desktop, deterministic web-view, RED OS target-free/race and reproducibility acceptance passed. UI-01F overall is DONE; evidence is `docs/ui-01f6.md`. UI-NET-01 is DONE: v1alpha6 provider intent, guarded Save/reopen, Entry points editor and Core-preview freshness passed Windows/RED OS acceptance; evidence is `docs/ui-net-01.md`. UI-01G overall is DONE (evidence: `docs/ui-01g4.md`); UI-01H1 is DONE (evidence: `docs/ui-01h1.md`) and UI-01H2 is DONE (evidence: `docs/ui-01h2.md`); UI-01H3 is NEXT.

Status correction (2026-09-21): UI-01H overall is DONE; evidence is
`docs/ui-01h4.md`. UI-01I is DONE; evidence is `docs/ui-01i.md`. UI-01J is
DONE; evidence is `docs/ui-01j.md`. UI-01 overall is DONE. This supersedes the
preceding historical H3-next sentence.

## Phase

CORE-07, CORE-06, EXEC-01, SERVICE-01A through SERVICE-01D centralized
acceptance and the focused generic Kafka role lifecycle refactor are complete.
Ansible-native desired-state ownership and deterministic managed Kafka/PKI
projection are proven through the standalone execution path without requiring
`project.yml`.

SERVICE-02A is DONE. Named Kafka listeners, service-wide TLS profile
consumption, PKI-01 read-only verify reconstruction and SSL consumer
prerequisites are accepted through the standalone Ansible path.

NET-01 is DONE. Endpoint groups own one client-facing DNS domain and wildcard
intent; an endpoint-capable deployment assigns its group directly and Core
derives a read-only deterministic FQDN projection. Keepalived provider
deployments own virtual addresses; transport ports and routing remain deferred
to a future HAProxy milestone.

NET-02 is DONE. One host-scoped Keepalived deployment owns one unicast VRRP
instance, VRID, endpoint-group reference and one-or-more virtual addresses.
Three-node RED OS acceptance proved all-or-none VIP ownership, automatic
failover, rejoin without failback and idempotent apply/verify.

NET-03 is DONE. Authoritative BIND primary-secondary DNS derives canonical
host, endpoint and wildcard records from the Ansible-native desired state.
Three-node RED OS acceptance proved complete candidate/activation barriers,
native zone transfer, exact-once fingerprint/serial lifecycle, primary outage
continuity, recovery and idempotent verify/repeat apply.

NET-03.1 is DONE. The separate host-scoped dns-client package derives split
DNS inputs from one logical BIND deployment reference. Three-node RED OS
acceptance proved systemd-resolved route-only DNS, safe resolv.conf ownership,
normal resolver redundancy and post-recovery idempotence.

NET-04 is DONE. Host-scoped HAProxy provides HTTPS `public` routing on `*:443`,
deployment and opt-in host endpoints, normalized Host routing, and package-owned
stats backends. Three-node RED OS acceptance proved TLS endpoint verification,
runtime multi-node pooling, non-VIP-owner HAProxy failure isolation, recovery,
and idempotent verify/repeat apply.

NET-04.1 is DONE. Opt-in Keepalived HAProxy tracking uses a root-owned bounded
admin-socket helper and cluster-wide candidate/active barriers. Three-node RED
OS acceptance proved owner failure causes atomic configured-VIP migration,
natural recovery without failback, non-owner failure isolation, and idempotent
verify/repeat apply.

NET-04.2 is DONE. Successful source lifecycles run one read-only,
deduplicated integration projection, then full-model BIND before HAProxy even
when the source is already `changed=0`. Three-node acceptance proved provider
drift repair, desired-state-only add/remove, serial `4 → 5`, clean repeats,
shared PKI stability and final Keepalived health/idempotence.

UI-BE-01 is DONE. The accepted Installer boundary is a versioned query,
semantic-command and execution facade over the same canonical Ansible project.
ProjectSnapshot and other rich UI models are derived and read-only; normal
writes require EditPlan review, project/document revision checks and an
Ansible-native writer boundary. Arbitrary existing projects remain read-only
by default, while Installer-owned standard Ansible files are the recommended
write target. No production Go/Wails/React code, YAML writer or second
desired-state store was added.

UI-BE-02 is DONE. The controller-only `ProjectSnapshot/v1alpha1` query opens
the same standard Ansible project with Ansible-resolved inventory variables
and composes deterministic catalog, topology, configuration, endpoint, DNS,
HAProxy, PKI, validation and readiness views without target contact or writes.
Raw-byte project/document revisions, honest physical provenance, partial
results and secret exclusion are accepted against a three-host six-service
fixture, including offline RED OS execution.

UI-BE-03 is DONE. The Go Installer backend accepts a bounded semantic
`EditCommand`, produces an opaque reviewable `EditPlan`, proves staged native
Ansible documents through the authoritative controller-only ProjectSnapshot,
and commits only Installer-owned documents with revision/digest checks and a
journaled rollback-capable transaction. Go owns edit/session/transaction
semantics; Python/Ansible retains project loading, precedence and all
infrastructure authority. No Wails/React, apply/runtime execution, events or
second desired-state store was added.

DEVX-01 is DONE. The repository now has scoped Go/Core engineering rules,
repository-local Codex Skills for backend, adapter, writer and QA work,
documented implementer/reviewer prompt templates and a standardized final QA
workflow. Future Wails remains a thin deferred transport concern.

EXEC-01A is DONE. A trusted Linux acquisition environment builds the exact
Python/Ansible runtime closure, Go verifies and atomically publishes the
immutable bundle, and Prepare transfers, stages, proves and activates it
without requiring Python or Platform Core on Windows. Repeated Prepare returns
`READY` with `Changed:false`.

The production service entrypoint now performs one target repository probe per
requirement, calls the single existing resolver, supplies an ephemeral
target-filtered `ResolvedArtifactSource` projection to Ansible and stops before
transport when any result is `BLOCKED`. Real RED OS acceptance proved Kafka
`NOT_FOUND -> OFFLINE_BUNDLE -> artifact_delivery -> SHA-256 -> apply/verify`
with repeat `changed=0`, and three-node Keepalived
`AVAILABLE_COMPATIBLE -> REPOSITORY -> apply/verify` with repeat `changed=0`
and no artifact delivery. A separate shared-gate test proved a blocked source
cannot reach a mutation sentinel.

Operational offline bundles use only the current project-root
`bundle/<digest>/` cache entry; replacement prunes the prior local digest.
Kafka and future service payloads exist only inside a verified bundle
under `runtime/artifacts/<service>/`; `.runtime/` remains the runtime-only DEV
input and QA state.

UI-BE-04A is DONE. The actual execution implementation and published
plan/event/result contracts were audited without adding production execution
code. `docs/ui-be-04.md` freezes Core ownership of deterministic
`DeploymentPlan`, private `ExecutionManifest`, ordering and trusted execution
semantics; EXEC-01A remains the source-resolution and delivery foundation.
Future execution uses only fixed semantic Execution Node operations, a detached
Core controller, durable non-PID-only ownership, bounded journal/event replay,
reconnect, cancellation and one mutating run per project. The synchronous
Kafka/Keepalived `ExecuteService` is retained only for EXEC-01A regression.

UI-BE-04B is DONE. Core now builds the authoritative target-free public
`DeploymentPlan/v1alpha2` from its own ProjectSnapshot/validation graph and
the same full service catalog, with a private Core-only ExecutionManifest bound
to the identical plan fingerprint. `project.yml.metadata.id` is required for
Installer-managed mutation; a fallback path identity returns
`PROJECT_IDENTITY_REQUIRED` and no executable manifest. Artifact requirements,
not repository/bundle source selection, are planned. The immutable runtime
release digest is semantic; `runtime/current`, timestamps, paths, facts and
secrets are not.

UI-BE-04C is DONE. The Execution Node exposes fixed semantic lifecycle
operations, stages private digest-bound manifests, dispatches only Core-owned
trusted operation identities, and runs them through a detached transient
systemd controller. Durable journal/event replay, reconnect, exactly-once
terminal results, whole-cgroup cancellation, interrupted recovery,
foreign-unit safety and bounded retention passed RED OS acceptance. UI-BE-04D
is DONE. Go now owns only public plan approval and session lifecycle over the
typed Execution Node protocol. UI-BE-04E is DONE: the production-shaped UI
lifecycle completed two serial Kafka runs successfully under an explicit
30-minute test timeout, and the direct Kafka regression proved repeat apply
`changed=0, failed=0`. UI-BE-04 overall is DONE; documentation-only UI-01A is
DONE and UI-01B remains separately gated.

## Established direction

- V2 is an independent Git repository next to V1.
- Ansible Core is the first deliverable and must operate without Installer.
- Standard inventory, `group_vars`, `host_vars` and role defaults are the
  canonical user-owned desired-state source.
- Topology remains a first-class part of desired state.
- Service deployments, placements, direct endpoint-group assignments and certificate scopes are explicit.
- Go backend and UI are deferred until the standalone contract is proven by a production service.
- Standard `ansible-playbook` with normal inventory, `group_vars` and `host_vars` is the initial standalone interface.
- Kafka KRaft is split into single-node `SERVICE-01A`, same-host distributed
  `SERVICE-01B` and real multi-host distributed `SERVICE-01C`.
- Execution Node is a selectable logical role and may be the local Installer,
  a project target or an external Linux host; dedicated host and
  local/target-host execution are supported profiles; WSL2 is development-only.
- Initial placement is explicit only.
- Role defaults remain the canonical default source for standalone Ansible;
  schema `default` values are not semantic defaults.
- Service packages declare explicit logical-setting to role-variable mappings;
  generic Core does not infer names.
- `ResolvedTopology` and `ResolvedServiceConfiguration` are derived,
  read-only projections and never persistent sources of truth.
- Unknown Ansible variables outside service mappings remain opaque,
  pass-through values with physical origin metadata.
- Production Kafka SERVICE-01A is implemented as a standalone service package;
  Kafka-specific playbooks remain inside `services/kafka`.
- The production Kafka role is topology-profile agnostic after input
  normalization; SERVICE-01A/01B/01C names are fixture and acceptance concerns,
  not role lifecycle branches.
- `platform_desired_state` in ordinary Ansible variables owns logical
  deployment intent; inventory `platform_deployments` owns physical member
  placement, roles and member configuration.
- `platform_generated_state` is machine-owned and limited to generated
  identities, fingerprints, locks and metadata. `project.yml.desiredState` and
  legacy `platform_project` are bounded compatibility readers, not new-writer
  targets or required Ansible user input.
- Managed service projections are runtime-only. Kafka continues to consume its
  public manual `platform_kafka_instances` input in standalone mode.
- QA state invariant: stable PKI identities and fingerprints persist, while PKI
  materialization plans remain derived; every independent Ansible execution
  reconstructs those plans through read-only resolution.
- TLS-capable service apply playbooks run a service-scoped `pki-apply` stage
  before service mutation. It selects only that service type's effective
  `tlsProfile` consumers; an empty selection is a PKI no-op. The standalone
  Core PKI playbook remains intentionally project-wide.
- Kafka `clientPort` and `controllerPort` remain bounded PLAINTEXT compatibility
  inputs. SERVICE-02A introduces Kafka-package-owned named listeners; their
  default model supplies PLAINTEXT and SSL endpoints, while SASL remains out of
  scope. A Kafka deployment/member selects one `tlsProfile` for all of its SSL
  listeners; no listener owns a separate certificate profile.
- EndpointGroup owns only a client-facing domain/wildcard namespace.
  `ResolvedServiceEndpoints` is derived-only, DNS-only and is not persisted to
  generated state. A provider deployment owns virtual addresses; PKI adds them
  to SAN only through `includeEndpointVip`. Kafka has no generic NET-01
  endpoint.
- DNS logical content fingerprint and serial are machine-owned generated state.
  Each apply materializes them once, then provides the same runtime projection
  to all BIND role tasks.  Primary zones are Ansible-managed; secondary zones
  arrive only through native BIND transfer.
- DNS clients are a separate host-scoped service package. `dnsServerRef` is
  the sole logical client-to-BIND link; server addresses and managed route
  domains are derived at runtime and NET-03.1 has no generated state.
- HAProxy publication is a typed relationship from a target service deployment
  to one HAProxy deployment. Its reusable backend settings are normalized after
  layered merge; deployment and explicit `hostEndpoint: true` routes share the
  existing DNS/VIP namespace. Keepalived HAProxy tracking is explicit and
  opt-in per Keepalived deployment; a referenced HAProxy deployment must share
  its endpoint group and placement.

## Implemented

- Repository initialized.
- Architecture documentation skeleton created.
- Owner decisions OQ-001 through OQ-007 incorporated; `ARCH-01` is complete.
- Published alpha schemas for project parts, catalog, service manifest, findings,
  validation, plan, event, result and resolved service configuration.
- Standard `platform.core` validation playbook and controller-side module.
- Pure deterministic topology resolver producing canonical `ResolvedTopology`
  and a topology fingerprint from only used service-definition digests.
- Explicit placement/reference resolution with stable ordering and structured
  placement diagnostics; `host_vars` are not resolver inputs.
- Versioned `ResolvedServiceConfiguration/v1alpha1` contract.
- Deterministic deployment-level configuration resolver combining literal role
  defaults with `serviceDeployments[*].configuration` overrides.
- Deployment/member scoped configuration with
  `ROLE_DEFAULT -> DEPLOYMENT_OVERRIDE -> MEMBER_OVERRIDE` precedence and
  `VariableContext(deploymentId, memberId, hostId)` projections.
- Non-literal Ansible/Jinja defaults are represented as `DEFERRED`; exact
  static references resolve deterministically, with `UNRESOLVED` and `CYCLIC`
  findings where applicable.
- Explicit service-package configuration mappings and Kafka role defaults.
- Canonical service-manifest metadata for managed and advanced settings, with
  generated tracked configuration schemas and defaults conformance checks.
- Structured findings for unsupported member-scoped settings.
- Opaque/pass-through variables retain physical origin and redact secret-like
  values without becoming managed settings; their deterministic fingerprint is
  separate from managed configuration fingerprints.
- Independent deterministic member projections and configuration fingerprints.
- Portable valid/invalid fixtures, including Kafka and PostgreSQL topology cases.
- Kafka 4.3.1 single-node combined broker/controller role with offline artifact,
  Java 21 prerequisite, KRaft storage initialization, configuration and
  systemd apply/verify playbooks.
- Generic Kafka member lifecycle with a legacy single-member compatibility
  adapter, deterministic full/local/controller/broker member sets, controller-
  only quorum projections, role-aware listener requirements, host-scoped
  listener/path collision validation, host-once preparation and deterministic
  application of zero or more local logical members.
- Explicit mutually exclusive dynamic/static quorum modes, stable dynamic
  controller directory IDs and role-derived `process.roles`; broker-only,
  controller-only and combined internal members are no longer prohibited by
  production role assumptions.
- SERVICE-01C real three-host fixture for `192.168.56.101` through `.103`,
  dynamic KRaft quorum, with centralized Kafka acceptance completed.
- EXEC-01 execution selection contract with separate candidate eligibility and
  post-preparation readiness, generic execution-environment preparation,
  target bootstrap, local self-target transport and runtime credential boundary.
- EXEC-01 execution identity hardening: persistent runtime SSH identity and
  known-hosts state outside per-run QA workspaces, idempotent preparation and
  generic ensure-access composition for self-target and remote targets.
- CORE-06 canonical state selection with bounded legacy `platform_project`
  compatibility, inventory-owned member normalization and blocking duplicate,
  unknown-deployment and conflicting-source diagnostics.
- Deterministic Kafka runtime projection containing effective member identity,
  roles, node IDs, quorum, addresses and target paths, with a separate
  `runtimeProjectionFingerprint` over final service-relevant values.
- Kafka identity discovery and pure generate/recover/validate decisions,
  transaction-safe project/inventory persistence, disk reload and second
  validation before any Kafka mutation. Verify remains read-only.
- CORE-07 Ansible-native canonical state selection, optional project metadata,
  inventory-owned member composition and isolated generated-state schema.
  Managed Kafka identity materialization writes only
  `platform-state.yml`, reloads from disk and validates again before service
  mutation; unrelated inventory/group/host variables remain byte-preserved.
- CORE-07A authoring safety baseline: managed Kafka apply validates desired
  state before identity discovery/materialization; Kafka managed configuration
  is closed while explicit `advancedConfig` remains the controlled native
  property namespace. `hash_behaviour = merge` remains required Ansible policy.
- Managed PKI request resolution now consumes the same Ansible-native topology
  without requiring `project.yml`; standalone manual Kafka and PKI inputs remain
  supported public contracts.
- Explicit deployment-scoped Kafka clean-install and separately acknowledged
  administrative/QA host reset operations; neither is an automatic reconcile
  or identity-mismatch fallback.
- PKI-01 standalone foundation: canonical MANAGED certificate authority,
  certificate and TLS profiles; topology-derived HOST/MEMBER/DEPLOYMENT
  requests; Execution Node PEM and dedicated PKCS12 materialization; atomic
  target deployment; read-only verification; deterministic request and
  materialization fingerprints. Changed initialized identity is blocked with
  `CERTIFICATE_REISSUE_REQUIRED`.
- PKI explicit leaf reissue: `pki-reissue.yml` requires a non-empty runtime
  selection of exact request IDs. Ordinary apply still blocks changed request
  identity; the explicit operation preserves prior request material in
  protected Execution Node state, rekeys and reissues selected leaves, supports
  marker-based recovery and keeps CA identity changes blocked.
- NET-01 endpoint foundation: the rejected `endpointBindings` alpha entity was
  removed; endpoint-capable service deployments select one endpoint group;
  PostgreSQL opts in through its service manifest; pure resolution yields a
  deterministic FQDN projection and feeds PKI-01 SAN derivation without
  generated-state writes, target contact or certificate lifecycle changes.
- NET-02 Keepalived: host-scoped inventory priority, one deployment per VRRP
  election domain, deployment-owned multi-VIP addresses, native candidate
  validation and read-only all-or-none ownership verification. Three RED OS
  nodes proved failover/rejoin/no-failback; NET-04.1 later adds an explicit
  opt-in HAProxy `vrrp_script`/`track_script` dependency.
- NET-03 BIND: deterministic authoritative primary-secondary DNS with complete
  candidate and activation barriers, native secondary transfer, read-only
  verification and a generated fingerprint/serial lifecycle.  The bounded
  native configuration surface is `advancedConfig.options.minimal-responses`.
- NET-03.1 DNS client: systemd-resolved is selected whenever its unit exists;
  otherwise NetworkManager is considered only with a proven split-DNS backend.
  The role owns a resolved drop-in only, never replaces `/etc/resolv.conf`, and
  blocks unsafe ownership or global-DNS fallback.
- NET-04 HAProxy: complete candidate/activation barriers preserve the exact
  validated graph. The package provides fixed HTTPS `public` routing and
  local TLS stats backends, reloads on active-graph or TLS-bundle changes, and
  treats candidate workspace assembly as ephemeral rather than desired-state
  change.
- NET-04.1 Keepalived HAProxy tracking: the package playbook owns explicit
  prepare, activate and reconcile phases. Barrier A requires every native
  candidate validation; Barrier B requires exact candidate-to-active SHA-256
  equality and every native active validation before any reload. The helper is
  root-owned `0750`, checks active HAProxy plus its local admin socket, and has
  no `weight`; tracking failure makes the local VRRP participant ineligible.

## Completed

- POSTGRES-01 is DONE. PostgreSQL standalone and pg_auto_failover runtime
  acceptance passed, including TLS, automatic failover, natural rejoin,
  post-rejoin verify and repeat apply with `changed=0` and `failed=0` on all
  participating hosts.
- NET-03 is DONE. Three-node BIND acceptance proved host, endpoint and
  wildcard authoritative answers, native secondary transfer, exact-once serial
  increment on logical zone change, service continuity during primary outage,
  recovery, and post-recovery `changed=0 failed=0` verify/repeat apply.
- NET-03.1 is DONE. Three-node DNS-client acceptance proved the derived
  primary-plus-secondary route-only server list, normal system resolution of
  host/endpoint/wildcard records, unrelated resolution preservation, fallback
  with one remaining BIND server, recovery and `changed=0 failed=0`.

## Validation evidence

- RED OS controller VM: targeted CORE-04 suite - 15 tests passed.
- RED OS controller VM: `python3 -m unittest discover -s ansible-core/tests` -
  43 tests passed.
- RED OS controller VM: `python3 ansible-core/tools/build_fixture_catalog.py
  --check` - fixture catalog reproducibility passed.
- RED OS controller VM: Ansible validation smoke passed with `changed=0`,
  `failed=0`, and validation status `PASS` on `localhost` only.
- RED OS controller VM: privileged `unshare -n` offline check passed.
- RED OS controller VM: Kafka 4.3.1 apply and verify passed; repeat apply and
  verify passed with `changed=0` and no storage re-format.
- RED OS controller VM: offline apply through `sudo unshare -n` passed with
  `changed=0`.
- RED OS controller VM: CORE-05 contract/resolver suite, full Core regression,
  generated-schema check, catalog check and offline `unshare -n` check passed.
- RED OS controller VM: Kafka SERVICE-01A apply, verify and repeat apply passed
  with `changed=0` after the metadata migration.
- No temporary remote QA workspace or artifact copy remained after QA.
- EXEC-01 centralized RED OS acceptance: node1 as local Execution Node and
  target, node2/node3 as SSH targets; Phase A preparation, Phase B bootstrap,
  key-based ping, elevated unified playbook and repeat bootstrap all passed.
- EXEC-01 regression: 60 Core tests and 4 contract tests passed; preparation,
  bootstrap and centralized connectivity playbooks passed syntax-check; unified
  PLAY RECAP contained node1, node2 and node3 with `changed=0`.
- EXEC-01 hardening focused validation: 14 focused identity/persistence tests,
  full Core (90) and Kafka contract (16) suites passed; repeated preparation
  and centralized ensure-access passed on RED OS with node1/node2/node3 recap
  and `changed=0`. Persistent key permissions were verified as `0600` private,
  `0644` public and `0600` known-hosts.
- Centralized SERVICE-01C acceptance through node1 Execution Node passed:
  apply/repeat/verify all returned `failed=0`; repeat and verify returned
  `changed=0` for node1, node2 and node3. Stopping node3 preserved a passing
  node1/node2 quorum verify; full verify reported node3 failed; recovery and
  final verify returned all three members healthy.
- Centralized SERVICE-01A replay passed after completing its fixture inputs:
  apply, repeat and verify passed; repeat and verify returned `changed=0`.
- SERVICE-01B focused diagnosis: a fresh canonical dynamic same-host run and a
  separate `127.0.0.1` endpoint experiment both formed a three-voter quorum;
  apply/repeat/verify passed after all controller listeners were ready. The
  earlier verify failure was an immediate post-start convergence race, not a
  dynamic-quorum, identity, storage-format or endpoint incompatibility.
- Focused Kafka lifecycle refactor regression on RED OS / Ansible Core 2.18.15:
  9 Kafka contract tests and 60 Core tests passed; fixture catalog check and
  SERVICE-01A/01B/01C apply/verify syntax checks passed.
- Final real lifecycle replay passed through the centralized Execution Node:
  SERVICE-01A repeat/verify, SERVICE-01B repeat/verify and SERVICE-01C
  repeat/verify all returned `changed=0`, `failed=0`. With node3 stopped,
  node1/node2 quorum verify passed while full desired-state verify failed on
  node3; node3 recovery and final three-host verify returned `changed=0`,
  `failed=0`. Runtime QA SSH key material was removed from node2/node3.
- Centralized SERVICE-01D acceptance through node1 Execution Node passed:
  split broker/controller deployment applied and verified with six members;
  repeat apply and final verify returned `changed=0`, `failed=0`. Broker stop
  preserved controller quorum and produced the expected degraded full-state
  verification; broker recovery restored all members. Controller stop likewise
  preserved the two-controller quorum, and controller recovery restored the
  full healthy state. Readiness polling closed the bounded post-start race.
- SERVICE-01D runner lifecycle evidence is persisted under the Execution Node
  QA directory. The runner records PID/stage/status, rejects a live duplicate,
  converts an orphaned `RUNNING` state to `STALE`, and records terminal PASS or
  FAILED states without secrets.
- CORE-06 RED OS regression passed: 90 Core tests, 20 Kafka tests, 14 focused
  Kafka cleanup/contract tests and 7 privileged offline tests. Catalog and
  configuration schemas were reproducible; apply/reset syntax and diff checks
  passed.
- CORE-06 centralized FAST acceptance passed for SERVICE-01A, SERVICE-01B,
  SERVICE-01C and SERVICE-01D: apply and verify passed, and repeat apply plus
  verify returned `changed=0`. Standalone manual Kafka input remained valid.
- PKI-01 RED OS acceptance: topology-derived managed PKI apply created a
  managed CA, PEM and dedicated PKCS12 key/trust stores on node1; target verify
  and repeat apply returned `changed=0`. A changed standalone request was
  blocked with `CERTIFICATE_REISSUE_REQUIRED` before certificate mutation.
- CORE-07 RED OS regression: 104 Core tests and 22 Kafka tests passed; generated
  configuration schemas and catalog are reproducible; Core, Kafka and PKI
  syntax checks passed; privileged network-isolated validation passed with
  `localhost changed=0` and no target contact.
- CORE-07 centralized Kafka FAST acceptance passed for SERVICE-01A through
  SERVICE-01D with managed `project.yml` deliberately absent. Every apply and
  verify passed; every repeat apply returned `changed=0` on all participating
  hosts. Failure/recovery scenarios were not repeated.
- CORE-07 managed PKI no-project acceptance passed. Apply, repeat apply and
  verify returned `failed=0`; repeat apply and verify returned `changed=0`.
- CORE-07A focused RED OS validation: Core suite (107), Kafka contract suite
  (22), managed-configuration tests and catalog reproducibility passed.
- SERVICE-02A focused RED OS validation: 11 focused listener/PKI tests,
  generated configuration schema and fixture catalog reproducibility, and
  Kafka apply syntax check passed. The isolated fixture bound PLAINTEXT, SSL
  and controller listeners and completed an SSL handshake with CA verification.
- SERVICE-02A FAST regression completed on RED OS with deterministic
  profile-lifetime roots: SERVICE-01A, 01B, 01C and 01D initial apply passed;
  separate verify returned `changed=0 failed=0`; repeat apply returned
  `changed=0 failed=0` for every profile. Core suite (113) and Kafka focused
  suite (22) passed, catalog and syntax checks were reproducible, and
  `sudo unshare -n true` passed. The regression also fixed the real SSL
  handshake EOF/timeout defect and split KRaft broker/controller listener
  projection contract without changing identity or PKI lifecycle semantics.
- NET-03.1 RED OS acceptance: systemd-resolved apply configured the derived
  `~scada.local` route on node1/node2/node3; separate verify, repeat apply,
  primary failure, one-secondary-remaining failure, recovery, post-recovery
  verify and post-recovery apply all passed. Core (137), focused service
  contracts (63), generated catalog/schema, target-free validation and
  privileged offline checks passed.
- NET-04 RED OS acceptance: Barrier A/B and candidate-to-active graph equality
  passed on node1/node2/node3. TLS hostname verification passed for deployment
  and all configured host endpoints; normalized Host with and without `:443`
  selected the same backend and unknown Host returned `503`. Runtime socket
  counters proved all three pooled HAProxy participants served requests. A
  non-VIP-owner HAProxy stop returned `503` only for its host endpoint while
  pooled and other host endpoints remained healthy; recovery restored all.
  Separate verify, repeat apply, post-recovery verify and post-recovery repeat
  apply all returned `changed=0 failed=0` on localhost and every target.
  An explicit selected leaf reissue added the endpoint wildcard SAN, deployed
  it to all HAProxy participants and returned to a clean ordinary repeat apply.
- NET-04.1 RED OS acceptance: opt-in tracking candidate and active barriers
  passed on all three nodes with exact per-node candidate/active checksums.
  Stopping HAProxy on the semantic owner produced helper failure and VRRP
  FAULT, then moved all configured VIPs to one healthy backup while the
  deployment endpoint remained available. Recovery returned the former owner
  to BACKUP without failback. A non-owner HAProxy failure became FAULT without
  moving the VIP. Final Keepalived/HAProxy verify and repeat apply returned
  `changed=0 failed=0` on localhost and all targets.

## Not implemented

- Dependency DAG, endpoint/certificate resolution, runtime role variables and
  deployment plan.
- Generic Core mutation roles.
- Production services beyond the accepted service slices.
- Production UI editor beyond the accepted UI-01B read-only, UI-01C
  metadata-only creation and UI-01D first-write/review slices.
- Generic backend/project persistence beyond the scoped Kafka identity
  transaction primitive.
- UI-01E4 Execution Node panel, later UI editor slices and UI-02 transport.
- Stateful listener-transition workflows; these remain deferred.
- Imported/external CA materialization, JKS, mTLS, global JVM cacerts,
  renewal and rotation.

## Next gate

CORE-01 through CORE-07, CORE-07A, PKI-01, SERVICE-01A through SERVICE-01D,
EXEC-01, the generic Kafka role lifecycle refactor, SERVICE-02A,
UI-DESIGN-01, UI-BE-01, UI-BE-02 and UI-BE-03 are complete. UI-BE-03 adds the
bounded safe writer but no Wails/React, UI persistence, execution or second
desired-state model.

POSTGRES-01, NET-01, NET-02, NET-03, NET-03.1, NET-04, NET-04.1, UI-BE-03,
DEVX-01, EXEC-01A, UI-BE-04B, UI-BE-04C, UI-BE-04D and UI-BE-04E are DONE.
UI-BE-04 overall, EXEC-OBS-01, documentation-only UI-01A, UI-01B, UI-01C and
UI-01D are DONE. UI-01D was owner-accepted without final revision-bound
review. UI-01E is decomposed into E1-E6; UI-01E1 server CRUD integration is
DONE; UI-01E2 through UI-01E6 and UI-01F1 through UI-01F6 are DONE. UI-01F
overall is DONE; UI-NET-01 is DONE, UI-01G overall and UI-01H overall are DONE, UI-01I and UI-01J
are DONE, and UI-01 overall is DONE.
