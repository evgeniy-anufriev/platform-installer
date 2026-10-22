# Generated application passwords — implementation evidence

2026-10-21. Baseline `e2b965b4256e22185a4652ef0fb133444a228fd1`.
Owner approved implementation, preferring Ansible tasks. Scope: generated managed
application passwords, reconcile supplied passwords on explicit mismatch, no
infrastructure-password changes, no Verify feature, single project Apply at a
time. Later owner amendment removes project ID from managed KV paths and every
Agent reference. See [plan](../generated-password-plan.md),
[PLAN report](../generated-password-plan-review.md) and ADR-047.

## Implementation boundaries

Target-free Core projects account-specific opaque refs and ordinary persisted
Vault sources. Apply reads/checks document ownership before generating; its
existing private document action uses secrets.token_urlsafe(32), reuses an owned
saved password, and returns values through existing no_log facts. Ansible tasks
materialize protected invocation files, use existing provider stages, publish
after success through current KV CAS, and clean derived files in always.

PostgreSQL retains role ownership and changes only explicit password-auth errors;
Redis/Sentinel reconcile a mismatching hash only with a matching witness;
ClickHouse retains UUID/witness checks and accepts only auth code516; Kafka
requires explicit SASL invalid-credentials failure, exact managed principal and
existing administrative access. Infrastructure admin/default principals are
excluded. Matching passwords are not rewritten. Existing-mode and Verify checks
remain strict; no Verify playbook was edited.

One Core location builder supplies documents/sourceJobs/policy/readFields/Agent.
Managed documents are library/shared and library/instance/accounts/account;
Vault APIs and Agent use mount/data/document. Explicit external vault_ref is
unchanged. Old project-prefixed documents remain; no hidden fallback/adoption.
Project identity remains in ownership, not KV locations or Agent secret refs.
An old generated value at a legacy path may be replaced at the new path through
the approved application-password reconciliation.

## Passing checks

- Core/application/Vault regression: 126 tests, 125 PASS / one existing SKIP,
  7.905s, current-tree RED OS source. Includes distinct refs, generated scope,
  owned reuse, foreign/deleted rejection, exact shared/account paths, actual
  Agent renderer without project ID, external refs and existing runtime inputs.
- PostgreSQL isolated native Ansible: three scenarios PASS294.833s, create/repeat,
  manual password change/repeat, foreign ownership rejection and existing mode.
  An older QA fixture lacked serviceType; corrected only fixture metadata.
- Redis/Sentinel: four real local Redis engine scenarios PASS1.791s, including
  password-hash reconciliation, read-only preflight, repeat and ownership guards.
- ClickHouse: seven tests PASS359.375s, including isolated standalone and three
  servers/Keeper, managed password change, per-member login, repeat and grants.
- Native generated integration: one test PASS90.504s. Runs production
  application-libraries-vault-preflight/provider-stage playbooks with isolated
  real TLS Vault/PostgreSQL and manual documented inputs. Covers foreign document
  rejection before provider mutation; generate; unchanged published repeat;
  missing-publication retry with a new password and successful provider login;
  actual Agent-config file rendering; unchanged legacy document; no generated
  value/token in captured output; derived file cleanup. This exercises provider
  and publication stages, not a container/application startup acceptance.
- Frontend295 tests/26 files PASS, lint/typecheck/Vite build PASS. Real payload
  test confirms generated saves only kind without an inline value field.
- Existing Go typed-source/slot-shape writer tests PASS. An initial broader
  name filter matched no tests and is not counted as coverage.
- Full application Apply playbook syntax check PASS with no target mutation.
  The expected no-platform_targets warning is a parse-only fixture limitation.

- Final native Kafka Ansible11 PASS95.094s, with explicit SASL mismatch repair,
  transport-error refusal and existing-account/infrastructure-admin exclusion.
  These use the established bounded CLI fixture, not a live Kafka broker.
- Actual React/Wails/Go editor acceptance PASS on an isolated desired-project
  copy: select managed mode/generated, draft/Review/Save, reopen with no plaintext
  field, reset/Review/Save/reopen. Generated saved revision
  `sha256:863eb42a455c6a94d7f6b15e42259f9c6ffaa523f5fea8a9d8b7e8e1fcc50540`,
  reset revision `sha256:48430ae186766bff0fdef6cc2a3adc388ffeeea96b411584eeb17c6647d77ac9`.
  Driver/evidence `.runtime/qa/generated-password/acceptance.cjs`/`acceptance.json`.
  Native chooser alone uses the existing bounded OpenProject seam; all writes
  use actual React handlers and real Wails Go methods. No node/Apply/run in
  this editor flow. Failed driver attempts used the wrong row role, omitted
  explicit account mode, read the wrong slot field, or tried an unchanged Save;
  the final run used a fresh isolated copy and completed all three checks.

## Environment failures and open acceptance

Initial Kafka/ClickHouse native invocations lacked collection paths; corrected
environment, then passing runs above. Initial broader Core import invocation
lacked PYTHONPATH for sibling tests; corrected, then126-test PASS.

The full A4 container fixture cannot run: prepared local image
`platform-application-connection-probe:qa`, pinned image ID
`sha256:acd94e424cb685723e768de1e1b0a7f98ffe5b491f4666a6a89888a31bf64ebb`,
is absent from the configured platform-docker daemon. No Internet download,
automatic artifact fallback or baseline service mutation was performed. The
new native provider-stage test avoids that image prerequisite, and does not
replace full application/Agent startup or combined real Wails/Core acceptance.

No infrastructure Apply, baseline application password reset, visual acceptance,
commit or push is claimed. A current-source runtime build/publication/preparation
is in progress for a real Wails/Core target-free generated-source check. The
previous runtime53 was preserved through the standard publisher under
`.runtime/qa/generated-password/prior-cache/` before replacement. FULL DIFF and
full combined application acceptance remain OPEN at this checkpoint.

## Independent FULL DIFF gate and cleanup

Independent FULL DIFF returned BLOCK: AGP-D01 is the missing full production-flow
acceptance above, not an established code defect. See
[report](../reviews/generated-password-diff-review.md) for the exact frozen
40-file fingerprint and finding. No new blocking code/security or overengineering
finding was established. Further automatic implementation/acceptance stopped;
no second FULL review or infrastructure Apply was started. A target-free UI/Core
follow-up was not run after the BLOCK.

All five qa-sync remote source workspaces were cleaned through the standard
helper, including the last `/var/tmp/platform-installer-qa-80b12b8e10de4377ad7f64ff0cba10d5`.
Owned isolated Wails and Vite5194 were stopped by verified process/session;
the differently located user's Wails image was preserved. Runtime promotion
already in flight is allowed to settle and its result is recorded below.
Review/status/evidence updates after the frozen diff are documentation only;
the reviewed implementation is unchanged. No commit or push.

The already-running standard qa-runtime-promote finished successfully: current
source built on node2, verified/published to active cache and prepared on node1.
Bundle `sha256:9b25c6d4b56c7a4951064478fbce781d8392cd0dfb96e588bd33fed01492e650`,
catalog `sha256:0312ef6d691d72d2a9aca03b208632391045191dffaed8f83b76e0e6f95524ad`,
owned QA-copy revision
`sha256:57df7aeb3840c8114615568f75a9134cc6484c9cee5c97b8ccfafd6c8eb29079`.
Only the isolated QA project was rebound. Original project desired state and
user Wails process were not changed; prior bundle remains in prior-cache.
Safe result: `.runtime/qa/generated-password/promotion.json`. No subsequent
Project Verify, plan, Approve, Start or service Apply was performed.

## Owner-requested real project source editing

Owner then requested actual React/Wails edits of
`.runtime/qa/sdku-cspa-alarm-view-project`: all five account passwords of
`sdku-dm/alarm-view-service` generated, five `cspa/alarm-view-service` passwords
manual. Owner authorized random manual values held only as session secrets.
Actual Review/Save persisted all five generated sources and five runtime-secret
sources. SDKU accounts were set managed as required for generated; CSPA's inherited
managed account modes were made explicit for source editing. The SDKU history
database resource still had existing mode at this checkpoint. No password values
have been submitted at this checkpoint.

Standard published-bundle promotion rebound this project to the current bundle.
Its duplicate native lock remained old, causing APPLICATION_ARTIFACT_LOCK_CONFLICT
inside the generic snapshot error. With QA Wails stopped, exactly that old native
digest was synchronized to the manifest's new digest using a one-occurrence CAS;
image metadata was retained. The next actual UI/Core Verify reached INVALID at
revision `sha256:1b12f1c186e31a8d47c17ba366ec17ee850c593af02949efbd91e895caf0fbdd`:
15 SCHEMA_VALIDATION_FAILED findings at resolved password source descriptors
(five SDKU accounts across three placements). Ordinary recursive combine retained
the inherited runtime-secret ref alongside generated kind. No Verify behavior
change is proposed; the existing account-policy filter needs atomic source
replacement. A concrete small correction is prepared, not applied, under
`.runtime/qa/generated-password/atomic-source-fix.patch`; owner authorization
requested because the FULL DIFF gate remains BLOCK. Manual session input remains
blocked by the invalid projection. Safe evidence is in requested-project-edit.json;
no Apply or password change occurred. The isolated diagnostic source workspace
was cleaned with qa-sync. Original user Wails process remains untouched.

### Owner-approved atomic source correction

After the explanation, owner accepted the bounded correction, new QA bundle and
completion of the five CSPA session inputs; no Apply. Existing account_policies
now replaces an explicitly supplied credential source descriptor as a whole,
using the existing ordered layers; other credential fields and policy handling
are retained. No new function, source type, endpoint or Verify path was added.

Current-source RED OS tests:65 unit cases PASS1.230s (application_libraries,
application_providers, application_vault). New regression covers generated/vault
source replacement, reverse precedence, preserved username and no input mutation.
Standalone Ansible generated override plus unchanged manual neighbor PASS across
two SDKU placements. Its first ad-hoc fixture missed required account mode and
Kafka admin reference; only fixture inputs were corrected, then PASS. Source
identity verified and qa-sync workspace
`/var/tmp/platform-installer-qa-e612c98f8caf4d85bf62c85602383d7a` cleaned.
Current-source bundle build/promotion is in progress on trusted node2; prior
bundle9b25c6d4 is preserved by standard publisher in source-fix-prior-cache.

Original FULL DIFF report remains historical for its exact frozen fingerprint;
this owner-approved correction is subsequent code, not a newly reviewed diff.
AGP-D01 full application/Agent/live-Kafka acceptance remains OPEN. No automatic
second FULL review, application plan/Apply, infrastructure mutation or download.

### Requested project completed through real React/Wails

New current-source bundle built on node2 and standard-published/prepared on node1:
`sha256:d887ddc10acc46ba4a4026096093b851dc9f25cc624d37c52dfb23cd736b91a5`;
catalog unchanged0312ef6d. After the standard manifest rebind, the duplicate
native lock digest was aligned using a one-occurrence CAS while QA Wails was
stopped; image entries were retained. Actual UI/Core Project Verify VERIFIED at
saved revision
`sha256:7a14dd6ae842f5785f50d06e328a3fce430ff02888b771ce9f53b7af077d7bd7`.

Actual React password fields and save-in-session handlers accepted five separate
cryptographically random manual passwords for CSPA; every account's header showed
secret present and input values were cleared. SDKU's five password selectors
remained generated; CSPA's five remained runtime_secret_ref. Values were checked
absent from the public CurrentProject snapshot and public project files, then
discarded from the driver array. No plaintext value was printed or written to
evidence/project files. Safe evidence requested-project-edit.json reports PASS;
driver requested-project-session.cjs uses the bounded chooser seam only for Open,
all secret submissions use actual React handlers and Wails Go methods.

Earlier driver failures checked field enablement before the UI refreshed, or
waited for a transient field-local success message instead of the persistent
account-header availability status. Final corrected run passed all five saves
and both libraries' source checks. No production UI workaround was introduced.

Owned Wails bridge34129/parent29944, Vite5194 and the headed browser driver/session
were deliberately left running on CSPA Secrets to retain the requested manual
session inputs. Values remain subject to normal session expiry/clear. Other user
Wails process remains untouched. No application plan, Approve, Start, run ID,
service Apply or real Agent/container-start acceptance occurred; AGP-D01 is still
OPEN. No second FULL review, commit or push. This completes only the owner's
bounded source/session editing request and the atomic-source correction.

## Owner-approved SQLSTATE correction (2026-10-22)

Owner explicitly requested SQLSTATE 28P01 recognition, a fresh real UI run, and
proof that selected passwords are accepted and delivered to the application;
infrastructure passwords and Verify remain excluded. The earlier localized
PostgreSQL failure was reproduced read-only with an unrelated random wrong
password. Installed libpq returned 28P01 in PQERRORS_SQLSTATE mode before initial
authentication, including the server's localized/transliterated severity.
Changing client LC_ALL or startup lc_messages options did not change that error.
The prepared translated-message patch was not applied.

A bounded platform.postgresql.application_password_probe module now uses the
installed libpq through Python stdlib ctypes: explicit connection parameters,
verify-full TLS, deadline, SQLSTATE-only error formatting, private password input,
and connection cleanup. It returns only authenticated/sqlstate/changed metadata;
no raw connection message or credential is emitted. Only Apply preflight for
catalog-confirmed managed application roles calls it. Ownership/role checks still
precede it. Exactly 28P01 permits existing account reconciliation; TLS/network,
unknown failures and other SQLSTATEs stop Apply. Ordinary psql SELECT 1 remains
the post-update login and existing-mode check. Shared login no longer recognizes
an English password-error phrase; its optional managed-skip flag is scoped only
to that preflight include. Separate Verify playbooks/tasks are unchanged.
No infrastructure-role password path, server locale, dependency package, public
contract, desired-state store or runtime service was added or changed.

Focused current-source RED OS native evidence:
- Existing resources/accounts/repeat, managed mismatch/reconciliation with C and
  ru_RU.utf8, foreign ownership, and existing-mode/login regression: three PASS.
- Initial direct-probe fixture failed because the automation account could not
  traverse its private PostgreSQL CA directory. Matching the production task's
  become context fixed the fixture; no production relaxation was introduced.
- Corrected native probe test PASS, 15.447s: correct credential, localized 28P01,
  missing CA, wrong TLS identity, closed port; all changed=false. Password values
  were asserted absent from captured output. No new Verify scenario/function.
- qa-sync verification of workspace335b5c90 against the current tree PASS.

Current-source bundle3669a380ff7bca999c07262e54e2fc1b600d9b2b2cb20777131b313fa0c12545
was built on node2 using existing runtime-input50 without acquisition. The first
standard remote-builder export exhausted temporary disk during result.tar
creation; its workspace was cleaned. The same Python builder via qa-sync and
recursive SCP completed without extra tar copies; standard publisher validated
and published into active cache. Catalog digest remains0312ef6d. Published probe
bytes match the working tree. Previous d887ddc1 is verified/preserved locally.
Node1 staging initially failed with only1.8GB free. No active runs were found;
only this task's retired9b25c6d4 and babc4089 releases were removed after matching
manifest digests and validating retained local bundles. Current d887ddc1 and all
other releases were preserved. Standard resumable promotion then prepared and
activated3669a380 and rebound the QA project. Its duplicate native artifact lock
was aligned by one-occurrence CAS while owned Wails was stopped.

Upstream SZI schema requires an explicit PostgreSQL resource parameter name.
The two previous partial overrides failed with six schema findings. Actual React
resource editor/Review/Save materialized the same previously Core-resolved names:
sdku-dm/alarms_db=sdku_alarm_view and cspa/alarms_db=cspa_alarm_view. No database
rename, restore or binding change was requested/performed. Project Verify then
VERIFIED revisionacfa287cff9e949353e5f27ae73bd5182f06d611b8626d9f320ef31eff26e670.
Public projection confirms five generated SDKU sources/five manual CSPA sources.
A stale QA-host Go/config copy initially lacked the current React library-order
priorities; no plan was dispatched. Owned QA internal/config/contracts/main were
aligned to the current repository with a recoverable source-only backup. No
production Go/React edit was made for that preparation correction.

Master was fast-forwarded from5f614312 to origin/master327c0b76 (source-snapshot
refresh only), preserving all existing dirty work. No feature commit/push or
new independent review occurred. Actual execution/password-delivery result is
recorded below after completion; this preparation does not itself close AGP-D01.

### Owner-approved manifest order correction (2026-10-22)

Run installer-8ebc903c5e0fa3169352117a5b41d9ae on revision acfa287c,
plan plan-051bba10c34c0560e96c25f8 and bundle3669a380 failed before Ansible
with EXECUTION_MANIFEST_INVALID. Core selected [sdku-dm,cspa] from configured
library priorities; validate_application_manifest accepted it, but _command
incorrectly required alphabetical order. No provider password update or Verify
started. This run's session lease was already cleaned before the hash check;
its credential handoff must not be reported as verified.

Owner approved preserving Core order and checking uniqueness instead. The
single guard comparison was corrected; invalid IDs, bounds and targets remain
checked. Added a regression for ordered Apply admission and invalid selections.
Current-source RED OS test_execution_lifecycle + test_application_mixed_execution:
70 tests PASS. Prior target-free candidate check covered 8 valid/invalid command
admissions without dispatch. No Verify or infrastructure-password change.

Bundle07ee125e7d274bb5434936378cb04f975aca009f46358e0f784821b52be8f25b
was built from current sources on node2, verified, standard-published, prepared
and rebound. Previous3669a380 was validated/preserved locally. Catalog0312ef6d
unchanged; native duplicate lock aligned by exact one-occurrence CAS while owned
Wails stopped. Actual React/Wails fresh Verify: revision97dddcabe87308e730f00f0ee536bf5ded7cf5b50198f4181beb2971a8c03b90.
Actual fresh plan plan-aafa7edb75b01f2040a905eb: APPLICATION_LIBRARIES_APPLY then
APPLICATION_LIBRARIES_VERIFY, skipInfraVerify=true. Actual Approve/Start created
installer-9463a0c8951e2ffa7feed2265fe6e633. Five manual CSPA lease hashes matched
submitted values. Controller order guard passed; real PostgreSQL SQLSTATE probe
completed successfully, so the localized-auth admission failure is resolved.

Run FAILED in ClickHouse preflight before provider account mutations, Vault
publication, Agent/application replacement, or library Verify. Public diagnostic
ANSIBLE_ASSERTION_FAILED loses the provider detail. Read-only current-runtime
projection and native ClickHouse preflight reproduced
CLICKHOUSE_APPLICATION_OWNERSHIP_UNKNOWN for database/sdku_dm. Existing ownership
witness is present and all three member UUIDs match, but its marker refers to
resource analytics; expected marker refers to history. Both share project
project-b46aa3f5f57a495f, providerqa-clickhouse and librarysdku-dm. No ownership
repair performed. Requested owner approval for backup plus exact marker-tail
analytics→history correction and another fresh skipInfraVerify plan. Password
acceptance/live Java delivery remains NOT CONFIRMED, AGP-D01 OPEN. Infrastructure
passwords and Verify implementation unchanged. Node2 build QA workspace cleaned.

Owner approved the exact ClickHouse resource-marker repair. Rechecked the
current marker and native database UUIDs on all3 members under the existing
custody lock. Created application-objects.before-history-20261022.json alongside
the witness (0600); preserved a local QA copy. Published only marker tail
analytics→history for database/sdku_dm, preserving every UUID and other record.
No SQL database mutation. Read-only combined ClickHouse preflight then PASS,
changed=false. Actual React/Wails fresh Verify retained revision97dddcab and
runtime07ee125e; another owner-authorized fresh plan/start is in progress.

Actual fresh run installer-e4338605b2a919e660ae121364157210 (same revision97dddcab,
plan-aafa7edb75b01f2040a905eb, skipInfraVerify=true) passed all provider preflights,
including ClickHouse. Five CSPA manual lease hashes matched again. PostgreSQL
managed password reconciliation changed both account scopes and subsequent
TLS authentication passed; Redis/Sentinel and ClickHouse account hooks passed.
Run then FAILED at Kafka task Reject non-credential errors and mismatching
read-only application accounts, ANSIBLE_FAILURE_REDACTED, before account Vault
publication/Agent/application replacement and library Verify. Existing running
applications have not been confirmed to use the newly reconciled credentials.

Read-only diagnoses used installed07ee125e native CLI, actual account template,
and Ansible engine: synthetic wrong password produces SaslAuthenticationException
with invalid-credentials text; the existing guard recognizes it at both10000ms
and ordinary30000ms. Broker journal in the original failure window records one
invalid-credentials authentication failure without TLS/timeout evidence. Exact
original CLI stderr was not retained due no_log; its guard failure remains
unreproduced, not declared fixed. No Kafka or Verify production changes made.
A retry using retained UI inputs stopped before Plan/Start because one-shot
manual inputs were unavailable; no run was created. Continuing the owner-requested
fresh retry through full UI credential/session preparation. CSPA inputs are
fresh random manual values, SDKU remains generated. No concurrent Apply.

Fresh retry installer-4a5d154de7944a7578261d0ce0c0b312 retained runtime07ee125e,
revision97dddcab and skipInfraVerify=true. Five newly entered CSPA manual values
matched the attached lease. No production code changed for this retry. Kafka
recognized the mismatches, updated both application SCRAM passwords using the
existing file interface, and authenticated both successfully afterward. This
retry passed the prior Kafka guard; it does not establish a root cause/fix for
the earlier unreproduced failure.

Direct TLS Vault check: all10 account documents exist under project-ID-free
paths, owners present; all5 CSPA password hashes match submitted values, all5
SDKU generated values present. SDKU all3 Java processes matched Vault for every
account-bound username/password/JAAS environment value; Agent HCL includes every
current account path and no secret/data/project- path: 50 checks PASS.
All SDKU placements subsequently passed ordinary readiness. CSPA node1 Java
comparison also20 checks PASS, matching the submitted manual hashes via Vault;
its actuator returned200/UP, db/kafka/redis UP. Other CSPA placements and the
terminal Apply/Verify result remain pending at this checkpoint. Health warm-up
was temporarily unhealthy and later became UP without intervention.

On installer-4a5d154de7944a7578261d0ce0c0b312, all6 running Java processes now
match the10 Vault account documents for all account-bound ENV/JAAS values.
The full delivery check PASS100/100: five CSPA values match the entered manual
hashes; five SDKU generated values exist; all6 Agent HCL files reference all
current account paths and contain no secret/data/project- path. Independent
direct SHA256 comparison from Java ENV to submitted CSPA fingerprints PASS15/15
(5 accounts x3 hosts), without relying on Vault equality alone. Ten distinct
account passwords; no plaintext values emitted/stored in evidence. Provider
post-reconciliation login checks already passed for all affected providers.
SDKU all3 ready; CSPA node1/node2 passed readiness, final placement pending at
this checkpoint. Node2 startup was slow under load~41 and swap~2.3GiB; it became
ready without timeout/resource/configuration changes. Run is still RUNNING;
terminal Apply/Verify is not yet claimed PASS.

### Final owner-requested run result (2026-10-22)

**SUCCEEDED** installer-4a5d154de7944a7578261d0ce0c0b312. Actual React/Wails
Open/SSH trust/session secrets/Project Verify/fresh Plan/Approve/Start, saved
revision97dddcabe87308e730f00f0ee536bf5ded7cf5b50198f4181beb2971a8c03b90,
runtime07ee125e7d274bb5434936378cb04f975aca009f46358e0f784821b52be8f25b,
catalog0312ef6d691d72d2a9aca03b208632391045191dffaed8f83b76e0e6f95524ad,
plan-aafa7edb75b01f2040a905eb. Manifest contains exactly library Apply and Verify;
skipInfrastructureVerify=true. Both ACTION_COMPLETED statuses SUCCESS; terminal
result SUCCEEDED. PostgreSQL SQLSTATE28P01 and manifest-order correction exercised.

Final evidence under .runtime/qa/generated-password/: acceptance-summary.json,
execution-success.json, session-lease-check-kafka-retry.json, vault-values-check.json,
live-delivery-check.json, manual-live-env-check.json, live-health-check.json.
Safe booleans/counts only:10 Vault documents PASS;100/100 all6 Java/Agent/account
comparisons PASS; direct manual-submission hashes against Java15/15 PASS; all6
HTTP health endpoints200/UP with db/kafka/redis UP. Ten distinct application
passwords. Infrastructure passwords unchanged; separate Verify source files
have no diff and no Verify functionality/tests were added. Visual inspection
not performed. No new feature commit/push or independent review was requested.

This real flow closes the previously absent first generated Apply/Agent/live
Kafka evidence for the owner's specified project, including mismatch reset.
The historical FULL DIFF verdict/frozen fingerprint remains unchanged. A second
actual UI Apply proving published generated-value reuse was not performed;
native reuse evidence exists above. Do not describe the full historical review
acceptance matrix as independently closed/re-reviewed by this result.

Cleanup complete: node2 current-source build workspace was removed with qa-sync;
node1 diagnostic/current-source workspace likewise removed. Initial cleanup
could not remove root-owned .runtime/secrets; restored ownership only of that
verified QA subtree and its .runtime parent, then qa-sync cleanup succeeded.
Owned QA Wails/Vite/Edge processes stopped through their original exec sessions;
ports34129/5194/9341 no longer listen and exact owned PIDs are gone. Unrelated
user application processes and target application containers were preserved.
ClickHouse ownership backup remains alongside its witness for recovery. Project,
active immutable cache07ee125e, protected runtime credential inputs and safe
local evidence retained. git diff --check PASS (normal CRLF notices only).

## Example promotion and commit preparation — 2026-10-22

Owner requested updating `examples/sdku` and committing. Promoted only the tested SDKU,
CSPA and alarm-view-service package defaults; added a portable generated/manual
secret-source example with placeholders; refreshed canonical package digests and
updated the sample group variables and README/validation notes. Validation on RED OS
node2 against the exact final source passed: 28 package schemas/digests, two generic
preparation jobs, two secret-example jobs and 26 synthetic Compose renders; no real
target execution. Example offline validator passed and its temporary QA source was
removed via `scripts/qa-sync.ps1`.

The optional full Core regression was interrupted after about 55 minutes while
repeated local PKI/Ansible subprocesses continued unusually slowly. Its partial
progress stream showed failures, but the runner had not emitted final tracebacks or
summary, so this is not a completed result and is not counted as PASS. Only the exact
owned test process and its temporary QA workspace were stopped/cleaned. Earlier
focused feature/provider/frontend/native and real React/Wails checks remain recorded
above; this partial full-suite run does not change those results.
