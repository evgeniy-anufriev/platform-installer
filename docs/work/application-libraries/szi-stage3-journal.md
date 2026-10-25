# SZI Stage3 implementation evidence

## Scope and baseline

Owner authorized implementation on 2026-10-24 in worktree
`szi-stage3-implementation`, branch `codex/szi-stage3`, base
`24e24f9594b38b484682d27e433bc25b572935b5`.
The [technical plan](szi-stage3-technical-plan.md), SHA-256
`4de51e6d62e5eb71fe62b57def88d8e703b4507dbd46d93ec237f16eaf87bbea`,
and [FULL PLAN review](reviews/szi-stage3-plan-review.md) define the scope.

Owner explicitly prohibits building a real-project deployment plan or starting
installation until a further command. The owner will supply the stand acceptance
plan after tests and implementation review. No Stage3 real-project plan or run
has been started. No runtime bundle has been published or activated.

## Implementation

- Core derives invocation-only execution scope from library instance IDs. Full
  project resolution and library order remain available. Apply, existing Verify,
  images, own resources/accounts and Vault Agent jobs exclude skipped libraries.
- Referenced skipped providers retain minimal script contexts and required
  credential-source reads. Selected consumers still receive groups, clients,
  accounts and secret bindings through existing provider batches and Vault paths.
- Package manifest v1alpha2 adds integration_apply and integration_consumers.
  The generic script runner is unchanged. New request v1alpha7, plan v1alpha8,
  manifest v1alpha6 and capabilities v1alpha11 bind selection through image
  preparation, planning and execution; old runtimes reject nonempty selection.
- Go carries invocation selection without deriving infrastructure semantics.
  UI provides per-library skip checkboxes, resets approval when selection differs,
  and requires a fresh plan. Selection is not saved into portable desired state.
- CSPA declares SSO/groups using the existing provider script. SDKU declarations
  remain compatible. nginx startup and integration hooks share the same selected
  consumer projection; route update remains additive, with no deletion.

## Test evidence

Python/Ansible run on RED OS Execution Node 192.168.56.102 as platform-automation,
using current sources transferred only through scripts/qa-sync.ps1. Local transient
scripts and results are under .runtime/qa/szi-stage3, outside tracked sources.

- Go: go test ./... and go vet ./... PASS.
- Frontend: 303 tests / 27 files PASS; lint and production build PASS.
- Current application suite: 218 tests, 216 passed / 2 skipped, 201.946 seconds,
  exit 0, workspace platform-installer-qa-6d50690acd0940ad85fbb99f33d98224.
- Native package runner: 2 PASS. Native skipped-provider executor test: PASS,
  including repeat and an unreachable provider target; no Docker preflight on it.
- SDKU/CSPA package validation: 28 schema/digest checks and 26 Compose renders
  PASS. This is synthetic rendering, not real target acceptance.
- Isolated native nginx routes: 1 PASS in 32.272 seconds, workspace
  platform-installer-qa-268c6405b44e4f068d48a20d45876db1. Actual Ansible
  package_script role and the installed nginx-lua-resty:1.0.3-redos3-certs image
  exercise startup, selected-consumer update and repeat. Existing unselected route
  survives; first sorted placement wins; repeat reports changed=false. A unique
  temporary Compose project is removed in always cleanup; working SZI containers,
  configuration and endpoints are not changed. No image pull is allowed.
- Earlier full Core run: 857 tests / 24 skips, one fixture failure. The native
  callback fixture put script contexts in play vars instead of localhost host vars;
  fixture corrected and both native runner tests passed. That original full run
  remains FAILED; it is not relabeled PASS.
- A broad pre-D01/D02 Core regression completed successfully: 863 tests, 838 passed / 25 skipped, 2634.841 seconds, exit 0. Corrected-source application/protocol evidence follows below.

## Remaining gates

Independent HIGH-RISK FULL DIFF and owner-authorized targeted recheck are complete; D01/D02 are resolved, open BLOCKING0. See the review reports below. Real React/Wails and SDKU/CSPA
stand installation/Verify acceptance remain unperformed under the explicit owner
hold. No visual acceptance is claimed. Changes are uncommitted.

Seven earlier owned qa-sync workspaces were cleaned with the standard helper.
The earlier failed full-run log and current application/native nginx logs are
retained under .runtime/qa/szi-stage3/results. The latest full-regression workspace was subsequently cleaned after its PASS log was preserved; see Final regression and cleanup below.

## D01/D02 corrections and owner-authorized targeted recheck

Independent FULL DIFF returned BLOCK with SZI3-D01/D02; the original verdict,
identity and findings are preserved in [the report](reviews/szi-stage3-diff-review.md).
Owner explicitly authorized their correction, real protocol tests and one
TARGETED_RECHECK on 2026-10-24. No real-project plan or installation is authorized.

- D01: only the new manifest v1alpha6 schema now accepts the two canonical secret
  operation scopes: Apply-only and Apply+Verify. Verify-only and unknown operations
  remain invalid. Callback credentials are not broadened to Verify.
- D02: only the new Build request schema uses the existing nonempty string project
  path; the v1alpha7 request parser rejects objects/empty strings. Image DESCRIBE
  requires applicationLibraryOrder, and DESCRIBE/PREPARE reject each other's fields.
  Previous contract versions remain unchanged.
- The native protocol test validates the exact outgoing v1alpha7 JSON against the
  canonical schema, then invokes the actual execution_protocol process and Ansible
  planner with synthetic inventory. A skipped provider exposes its callback and
  integration_apply hook using one runtime secret reference; the selected consumer
  still produces an admitted manifest with Apply-only requirements. The test also
  checks Apply+Verify admission and unknown/Verify-only operation rejection.
- Schema/request agreement test checks valid Build, DESCRIBE and PREPARE; object
  and empty project values, missing required fields and phase-inappropriate fields
  must fail both schema validation and the real request parser.
- Focused protocol: 2 tests PASS in 91.294 seconds, exit 0.
- Current application regression: 220 tests, 218 passed / 2 skipped, 548.723 seconds,
  exit 0. This explicitly enables the isolated native nginx image test; startup,
  integration update, route retention and unchanged repeat passed again.
- Source workspace: platform-installer-qa-95502f1fa24f4096a4a32e368f915084.
  Focused result retained locally as results/d01-d02-protocol-pass.log under the
  Stage3 runtime QA directory. Full application log is retained there after copy.
- Test-fixture debugging exposed missing required address.wildcard in the synthetic
  endpoint group, corrected before PASS. The failed fixture result is preserved as
  results/d01-d02-fixture-missing-wildcard.log; no product validation was bypassed.
- The broad regression in workspace 268c6405... used the pre-D01/D02
  source. Its PASS result is baseline regression evidence, supplemented by the
  current corrected application suite above, not a second full current-source run.

The corrected source was frozen for one TARGETED_RECHECK of SZI3-D01/D02 and their
immediately affected schema/protocol/admission boundaries. Stand acceptance,
actual React/Wails selection and deployment remain pending the owner's test plan.

Targeted recheck completed: APPROVE, SZI3-D01/D02 RESOLVED, unresolved BLOCKING0.
See [report](reviews/szi-stage3-targeted-recheck.md), fingerprint
E6CDB25B500BC821D58AA4E2D588B06BB38B9E5E62FDB45CDAD7493CB52A76EB.
Reviewed production/test code remains unchanged. Only review/evidence/status
records were added after the recheck. The corrected-source QA workspace was
cleaned with qa-sync after preserving PASS logs locally. Real acceptance remains
pending the owner's separate stand test plan.

## Final regression and cleanup

Broad Core regression on the pre-D01/D02 source completed: 863 tests in
2634.841 seconds, OK (838 passed / 25 skipped), exit 0. The original earlier
857-test fixture failure remains preserved; it is not relabeled PASS.
Current corrected-source proof is protocol2 PASS and application220
(218 passed / 2 skipped), including the explicitly enabled native nginx test.
This is combined regression evidence, not a claim of another full run on the
post-correction source. No new code changes followed the targeted recheck;
all 72 source/test/generated entries were independently rehashed unchanged.

Final broad log retained locally as
.runtime/qa/szi-stage3/results/core-tests-stage3-baseline-pass.log.
All owned remote qa-sync source workspaces are now removed using the standard
helper. No test process remains active. No real-project deployment plan,
installation, runtime bundle publication/activation, commit or push occurred.
Stand acceptance is pending the owner's explicit test plan and authorization.

## Owner stand acceptance — direct phase, 2026-10-24

Owner's ordered acceptance is recorded in szi-stage3-acceptance.md. This phase
has not launched Ansible, an installation plan or an installation run.
Five SZI containers on102 were stopped as authorized; SZI103 remains active.
Three source107 images were exported, hash-verified and loaded on101/102.

Six clients use three common application-owned JSON templates. SDKU groups are
Администратор СДКУ, Инженер СДКУ, Диспетчер управляющий and
Диспетчер неуправляющий; CSPA groups are Администратор ЦСПА and Инженер ЦСПА.
Their role files preserve source realm/client distinctions and map only their
own library's application clients. Twenty direct provider-script calls PASS;
all ten repeat operations report changed=false. Independent API readback PASS:
six clients, role catalogues, authorization resource/policy/scope names,
redirects/public flags and six groups with required mappings and no cross-library
application assignments. Evidence: .runtime/qa/szi-stage3/results/direct-integration.jsonl
and independent-readback.jsonl. Full deep client comparison is also performed
by the provider; independent readback is not claimed as another full deep diff.

Owner corrections: data-manager has no Kafka connection/account/secret bindings;
Kafka remains for hmi-backend. Actual JAR confirms data-manager's Kafka feature
is disabled by default. No package default chooses qa-shared-endpoint: endpoints
are disabled until project overrides select/enable a group. This also corrects
alarm-view-service. Frontend TLS mounts use PEM certificate/key and CA chain;
healthcheck trusts the CA chain. Six application containers have not been started;
direct readiness/logs, Ansible and React/Wails acceptance remain open.
### Direct frontend checkpoint

Both hmi-frontend-para-sdku-node1 and hmi-frontend-para-cspa-node2 started using
materialized package Compose/nginx/ENV templates. Their QA-only PEM leaves were
signed by the existing project's managed CA; private material stays under the
established .runtime/secrets paths. Both running/healthy, CA-verified HTTPS200,
rendered backend/data-manager links correct, log error lines0. Source image ID
634bfc5225182aa71025344f0ca03258fd79dc0cb00171e2feee9089f31d91a0 matches on both.
Evidence: .runtime/qa/szi-stage3/results/direct-frontend-health.json.
This does not prove backend availability or published HAProxy/nginx routes.

Acceptance project .runtime/qa/szi-stage3/project preserves source project ID/PKI,
includes SZI and two consumer libraries, one shared application-packages directory,
SDKU=node1 and CSPA=node2, endpoint group selected only in project overrides.
Its runtime bundle/artifact locks are deliberately not yet refreshed; no plan
or Ansible call was made. Infrastructure Vault token was loaded from its existing
private file; authenticated API access PASS, unsealed, secret KV and AppRole
mounts present. No credentials were logged. Package catalogue updated for six
changed packages; public YAML parses and git diff whitespace check PASS.
Four backend containers/provider accounts/Agent delivery remain open.
### Direct backend and custody checkpoint

The initial manual QA certificate issue used the stale authority state on102.
Its CA subject matched, but its SHA256 fingerprint differed from the live SZI CA.
The established authority on101 matches the live SZI/Vault chain (95def9fa...abf306).
QA leaves/stores were reissued on101 without copying the CA key. Only the four
owned test containers were restarted. Future Core execution must preserve the
actual authority custody on101; project ID alone does not identify a CA key.
The stale authority on102 was not altered or substituted.

Both data-manager-sdku-node1 and data-manager-cspa-node2 now running/healthy,
restarts0. Actual JVM environment matches all15 Agent secret bindings; Docker
Config excludes all15. Native database migrations/startup succeeded. Warnings
(Flyway version/composite-id/JTA) are retained; no new TLS/auth/config ERROR found.
Evidence: direct-data-manager-health.json and redacted per-instance logs.

PostgreSQL ordinary provider SQL templates were rendered and executed directly
through psql on writable103: two model DBs, normal library-owner/account markers,
rights and verification PASS; final ensure/repeat12 all changed=false. The first
resource notice detector only inspected stdout, then was corrected to include
stderr notices; the retained final file is the repeated-state proof.
Redis/Sentinel uses the existing application_acl functions directly, without
Ansible. Admin runtime inputs were resolved in memory from existing protected
Sentinel config, since legacy Windows secret files did not authenticate. All24
member/account ensures and24 repeats PASS; repeats changed=false. Existing
ownership witnesses and guards remain intact. No admin credential values logged.

Vault projection/Agent HCL use existing pure Core functions with direct QA
inputs. Ordinary KV/AppRole API setup prepared16 documents and4 identities;
repeat semantic changed0, including normalizing Vault's /32 serialization in the
QA comparison. Values/role IDs remain under .runtime/secrets. Backend defaults
now use secret mount like tested alarm-view-service, rather than applications.
No Ansible process/playbook or deployment plan/run was launched.

Owner supplied the current ClickHouse admin credential at runtime; it matches
the live hash and native authentication. SDKU DB/account creation and verification
PASS on initiating102. Existing CSPA custody is on101; the initial call on102
correctly rejected missing ownership evidence. Calling the existing native scope
function in its original custody on101 passes CSPA ensure/verify/repeat; repeat
changed=false. The direct harness supplies arguments to the unchanged native
scope body; this is supplementary direct proof, not Ansible execution evidence.
Before native Ansible acceptance, reconcile the new SDKU witness location using
exact owned identity evidence; do not bypass ownership checks or delete objects.
Kafka preparation and both hmi-backend containers remain pending. Four of six
application containers are healthy; published endpoint/nginx-route acceptance,
Ansible and actual React/Wails acceptance remain open.
### 2026-10-24 — Schema Registry serializer and HTTP timeout correction

Owner-requested direct check uses KafkaProtobufSerializer/Deserializer and
TnMsg.Msg from the actual hmi-backend JAR, executed inside both application
containers. Spring Binder consumes the actual container environment plus the
Agent-supplied store passwords in memory; the package KafkaManagerConfig factory
builds the producer configuration. No plaintext credentials are printed.
A deliberately incomplete Kafka-only TLS map reproduces PKIX, but this is NOT
the cause of the reported real-runtime error: existing library base environment
already supplies schema.registry.ssl.truststore.location=ca-chain.pem/type=PEM.
The real configuration reproduced the exact Type.proto URL failure with
SocketTimeoutException during TLS handshake at the existing 1000 ms HTTP timeout.

Changed only the shared SDKU/CSPA defaults HTTP connect/read limits for both
Kafka consumer and producer to 10000/30000 ms. Existing PEM trust remains shared;
no Schema Registry PKCS12 override or new password binding was added. HMI's
existing Kafka store-password placeholders now use Compose escaping ($$), so
Vault Agent/Spring, rather than Compose, resolve their values. Current source
transferred with qa-sync to b39af729c7e04be8ac98d3e8057e67d5; both direct containers
recreated from the package templates and existing Agent configuration.

Both applications register and deserialize their actual generated protobuf
message through EACH Schema Registry endpoint 101/102/103:8082: six PASS calls,
no serializer ERROR or timeout. Independent HTTPS API readback on all three
nodes confirms Type.proto id1/version1 and sdku-main-compact-value plus
cspa-main-compact-value id3/version1, schemaType PROTOBUF, with Type.proto and
QualityDescriptor.proto references. Repeated serialization retained version1.
Both hmi containers healthy/restarts0; all17 Agent credential fields match JVM
and remain absent from Docker Config. Evidence: ignored QA scripts SchemaProbe.java,
test-schema-serializer.cjs, readback-schema-registry.cjs; logs/schema-serializer-*-runtime.log,
results/schema-registry-readback.jsonl and direct-hmi-backend-health.json.
Separate application log issues (absent alarm-service and CSPA websocket closed
peer/Broken pipe) remain outside this Schema Registry fix; no overall clean-log
acceptance is claimed. No Ansible, deployment plan/run or bundle activation.

### 2026-10-24 — nginx route catalogue readback

Six SDKU/CSPA routes were present but retained temporary direct IP/port URLs.
The current provider prepare-routes.sh was invoked directly with canonical
https://<applicationId>.evoscada.internal endpoints: ensure changed=true,
repeat changed=false. Independent live routes.effective.json readback confirms
all six exact subpaths/endpoints and the three prior SZI routes unchanged;
nginx -t PASS. Shared HAProxy endpoints return200 for both HMI/frontends.
Both data-manager endpoints currently return503: independent container check
shows unhealthy and Java heap OutOfMemoryError. This is a NEW open direct
acceptance failure; earlier healthy evidence does not describe the current state.
Authenticated nginx checks use the actual X-SECURITY-SIGNATURE header:
anonymous protected routes302 to Keycloak, admin-token protected routes403;
frontends200. This does not prove access with a correctly authorized SDKU/CSPA
user. Evidence: results/nginx-routes-readback.jsonl, direct-nginx-upsert.json,
direct-nginx-http.jsonl and current sanitized data-manager logs. No Ansible/plan.

### Owner decision — direct gate accepted; standalone Ansible stage authorized

Owner accepts the direct-check stage despite the subsequently observed
Data Manager QA heap issue, and authorizes removal of all six test containers
and their SDKU/CSPA integration records, followed by standalone Ansible Apply/
Verify with SZI skipped. UI planning/Start remains outside this authorization.
QA project overrides now use -Xmx1536m for both Data Managers (HMI remains768m).
All six containers were removed; six clients and six SDKU/CSPA groups deleted
from Keycloak, six nginx routes removed, retained SZI entries unchanged. Private
reset backups remain on103 under runtime secrets; no realm reset/admin deletion.

First fresh native resolution found APPLICATION_SCRIPT_REFERENCE_INVALID:
frontend intentionally opts out of library defaults, but validation incorrectly
required IDENTITY_GROUPS there for a library-scoped script actually assigned to
the backend representative. A shared library_script_hosts selection now aligns
validation and the existing runner choice; it does not add a new execution mode.
Three regression tests cover representative-only parameters, a still-blocked
missing representative parameter, and per-host connection eligibility. Focused
51 tests PASS on RED OS from the current source. Supplementary Ansible preparation
using previously native-resolved rows PASS; full fresh Apply is still required.

Native selection reports skip=[szi], install=[sdku,cspa], six consumer instances,
provider=szi/keycloak. Script contexts retain existing provider callbacks. SDKU
ClickHouse witness entries were copied from their original102 custody into the
normal101 initiator custody only after exact source marker/identity/conflict
checks; prior101 file backed up and original provider checks remain enabled.
Three-image standalone bundle built on102 by the standard builder, validated by
the standard CLI on101: f7cc7ba837688917646df9cb438f9c553e7987e7b8707f16738a5f1ceb6c52dd.
It supplies artifact authority for standalone QA only; no UI cache publication
or project/UI runtime activation. Current Core collection source is separate.

Owner proposed simplifying defaults.connections.sso.enabled, then explicitly
deferred it. The seven temporary default edits were reverted, including catalog
hashes and QA package copies. Both declaration and enabled settings remain as
before. The initial in-progress Apply was stopped during native resolution
before target writes, then restarted against the restored project. SZI baseline
captures all ten container IDs/StartedAt/states; node102 stopped and node103
running. Full Apply/Verify and recreation/readback evidence remain in progress.

### Standalone Ansible — provider and Vault regression checks

Unused alarms_db definitions inherited from the prior QA project conflicted
with databases owned by a different QA project. Removed only these unselected
resource definitions from the acceptance project; no database or owner changed.
Actual PostgreSQL provider preflight then passed:31 ok,changed0,failed0.
Additional selection/image/runner tests:25 PASS on RED OS.

A later Apply recreated the six SSO clients and six groups with role mappings,
then stopped before application startup at additive Vault policy retention.
The filter expected project-prefixed KV paths although the established Core
projection uses mount/data/<libraryId>/... . Corrected the filter to accept
canonical own-library paths, retaining old same-project paths for compatibility.
Core document paths, Vault documents and Agent paths are unchanged.
Vault projection/batch tests30 and Vault provider tests15 PASS. A read-only real
Ansible regression fetched all four existing instance policies and rendered each
against its actual Core projection twice:17 ok,changed0,failed0. Protected full
failed Apply output retained as apply-vault-path-failure.log on Execution Node.

Current standalone Apply uses source e6a43ff0b2a54c32a515b73e44b6e51b,
skip=[szi], install=[sdku,cspa]. Independent Keycloak readback confirms six
clients and six groups with expected realm/client mappings and no cross-library
client-role assignments. Runtime/Agent/nginx verification remains in progress.
No UI BuildDeploymentPlan/Start or installation plan launched.

### nginx route hook — jq implementation and continuation at failure

The previous standalone Apply failed at integrate-routes on node2: rc124.
The transient docker compose run was stopped by terminal job control under
Ansible/sudo; no consumer containers had started. Protected complete output is
retained as apply-route-timeout.log. Owner requested a jq-only implementation
and continuation at the failed operation, without replaying common preparation.

prepare-routes.sh now constructs/merges JSON with jq and atomically publishes
routes.effective.json only when semantic content differs. Unselected entries
remain; repeat preserves the effective file bytes and mtime. No Docker command,
container startup, nginx -t or reload is performed by this script. The obsolete
Lua upsert assets/configuration/mounts were removed from the package. Its caller,
arguments, script phases and generic Core runner are unchanged; jq is required
on the selected target and exists on both acceptance hosts.

Five direct/native tests PASS, including first/repeat/update, retained entries,
deterministic placement, missing endpoints and diagnostic/cleanup failure cases.
The actual provider integration hook resumed on node2 and node3 through existing
application-provider-script.yml/package_script, then repeated successfully with
unchanged route results; native recap localhost1/node1 49 ok,failed0.
No SZI container was started. Consumer continuation now reruns only read-only
preflight to restore process-local context, reads already published Vault
credentials/RoleIDs, and uses the standard ordered consumer tasks. It does not
replay PostgreSQL/Redis/ClickHouse/Kafka or SSO account provisioning. No production
resume API/checkpoint mechanism or UI installation plan has been introduced.

### Standalone consumer continuation completed; Data Manager correction

The standalone continuation finished with a complete native recap, failed0 and
unreachable0 on every host:localhost550/changed0,node1 679/changed43,
node2 434/changed41,node3 173/changed6. All six consumers are running/healthy.
Both frontends pass CA-verified HTTPS200, rendered links and errorLines0.
Actual Java processes match15 Agent fields per Data Manager and17 per HMI;
these fields are absent from Docker Config.Env. All ten SZI container
IDs/StartedAt/states remain unchanged. No UI deployment plan was launched.

Startup logs nevertheless exposed Data Manager heap OOM with1536m. Its package
ENV overrides the JAR default10MB HTTP header limit with100MB; the measured live
heap contained1.38GB byte arrays. Changed that existing ENV key to64KB, retained
QA heap1536m and updated the package catalog digest. A focused native Ansible
correction for these two existing instances only is running; other four
containers have a separate before/after identity baseline. Final OOM/readiness
and memory checks are still pending, so overall acceptance is not yet PASS.

The SDKU synthetic Compose fixture lacked the newly required endpoint-group and
resolved common-ENV contexts. Updated its representative fixture (provider group
preparation remains covered by native SSO tests); all28 package schema/digest
checks,26 Compose renders and both example preparations now PASS. No production
validation or template rule was bypassed. HMI startup logs contain missing alarm-service configuration (outside the selected
three-app scope) and separate WebSocket disconnect exceptions;
post-correction recurring integration errors still require classification.

## 2026-10-25 — standalone closed; UI run postponed

Owner closed standalone acceptance and initially authorized cleanup and actual React/Wails SDKU+CSPA installation with SZI skipped. Already-running reset completed: six selected consumer containers on101/102 removed; six selected clients and six groups removed from Keycloak; six routes removed from nginx103, three SZI routes retained. Evidence: `.runtime/qa/szi-stage3/results/ansible-reset.json`. Provider accounts/resources have not been removed.

Owner then postponed the real run and requested generic post_install scripts after all plan actions. No Wails plan, approval or Start was invoked. [Extension plan](post-install-scripts-plan.md) submitted to independent FULL PLAN review. Remaining cleanup and actual installation are on hold.

## post_install implementation and independent FULL DIFF

Owner approved plan and implementation on2026-10-25; real installation run remains forbidden. New package3, plan9, manifest7 and capability12 implement a terminal typed operation via existing package_script. Core204 cases PASS (2 skips); Go executionnode/desktop/installer tests and vet PASS. Live data-manager-sdku was temporarily started from installed Compose only. Actual standalone terminal entrypoint curl GET/POST /v1/project created QA project2000000025, recap localhost ok494 changed1 failed0. Repeat: ok494 changed0 failed0; no duplicate project creation. Preliminary attempts failed before script due incomplete QA collection path, then API rejected a name with spaces; corrected QA arguments, no production workaround.

Independent [FULL DIFF](reviews/post-install-scripts-diff-review.md) BLOCK: POST-D01 exact Vault-owner token permissions, POST-D02 ordinary standalone Build required fields, POST-D03 terminal approved-trust guard. POST-N01 duplicate script IDs on Execution Node can cause copy changed on repeat. Work stopped for owner authorization of corrections and one TARGETED_RECHECK. Existing Vault binding check was already in progress when verdict arrived; collect its result separately.

Owner decision: all post_install FULL DIFF blockers rejected as requiring general script-logic changes outside the agreed terminal-call scope. Do not expand implementation or run a TARGETED_RECHECK. Historical verdict retained separately from owner acceptance.

Already-running second-process Vault test completed successfully: actual published postgres password was read via generated account secret_binding and compared privately with the session input by assert-secret.sh. Recap ok525 changed3 failed0 (first delivery of the additional fixture/CA; both scripts report changed=false). Derived generated source and runner transient input copies absent afterwards. This is existing-value recovery, not creation of a new generated password during terminal execution. Live curl readback found exactly one project2000000025. Temporary data-manager-sdku container removed; five other consumers remained absent. The QA application project in DB is retained for repeat checks. No actual installation run, new runtime bundle publication, commit or push performed.

## Fresh UI acceptance preparation — 2026-10-25

Owner authorized cleanup, runtime update and actual Wails/React SDKU+CSPA installation with SZI skipped. data-manager package declares post_install/create-project, execution once on Execution Node, resolved own endpoint plus demo argument. Curl GET/POST /v1/project checks name and allocates next ID, preserving existing projects. Real HTTP fixture create/repeat PASS; SDKU28 package schemas/digests and26 synthetic Compose renders PASS. Application package digest ad928751.

Cleanup: two selected PostgreSQL model DBs and two data_manager logins removed on writable node3; private dumps retained. Two shared owner roles retained because pla_5cb6... also owns old QA database a9_sdku; no foreign DB removed. ClickHouse sdku/cspa DBs and two hmi_backend users dropped on cluster; corresponding local witnesses removed. Redis/Sentinel8 account entries per member removed and persisted on101/102/103; two matching cache keys deleted on primary. Kafka two SCRAM accounts, declared ACLs and10 topics removed. Vault16 owned documents and4 AppRole/policy identities deleted; private backups under established runtime secrets. SZI unaffected, consumer containers remain absent.

Runtime source /var/tmp/platform-installer-qa-9748279b955a4b55909ce0901881ba52 built on trusted102. Bundle szi-stage3-20261025-01, digest sha256:dce41925b24c0ebc799182213152b6eef6d02cf272036e06affc22798dd4b198, validated and standard-published into active worktree cache; project/bundle staged for real UI rebind. Initial SCP artifact transfer hit Windows path-length limits; standard artifact tar transfer completed and bundle validation then passed. Go/Wails dev binary built and frontend build PASS; Vite5177 running.

Automatic exec approval rejected the Wails Start-Process command: blocked by policy; no more specific reason returned. No bypass/retry through alternate launcher was attempted. User launcher .runtime/qa/szi-stage3/scripts/start-wails.ps1 and actual React/Wails automation install-ui.cjs prepared. No actual plan/approval/Start occurred. Runtime inputs remain only in protected secrets/session preparation; no secret values logged.

Owner launched Wails manually. Stage2 szi2-install-ui-16f-repeat.cjs reused with Stage3 project/digest/skip options and same real handlers. Initial Open returned WRITE_NOT_ALLOWED: earlier standalone QA YAML serialization had dropped managed headers in project.yml, group_vars and3 host_vars files. Original corresponding Stage2 documents prove Installer ownership; current QA documents backed up and only original header restored. No Core/writer guard changed. Real React Open and ConfirmRuntimeBundleUpdate then succeeded (UPDATED); digestdce41925 matches published cache. Target trust and node1 preparation in progress.

Actual Stage2-derived UI preparation succeeded: bundle rebind UPDATED; node1 READY; all target fingerprints confirmed; infrastructure Vault file accepted automatically; Project Verify VERIFIED; application references entered through inline fields. The added skip checkbox must be selected after opening Plan tab (QA ordering corrected). Fresh request captured: APPLICATION_LIBRARIES_ONLY, skipInfrastructureVerify true, order szi/sdku/cspa, skipApplicationLibraries [szi]. Build installer-264902435522259812373867648513389785999 BLOCKED before approval/Start with5 ARTIFACT_SOURCE_OFFLINE_REQUIRED findings: ClickHouse client/common-static/server and Kafka binary/Schema Registry binary. Native three-image-only bundle lacked mandatory planning closure. Existing verified runtime16 on acquisition102 provides all5 exact components; sizes/SHA256 verified from manifest303d60f4 and hardlinked into approved build input. Runtime02 build in progress; no source-selection guards changed and no Internet acquisition.

Runtime02 szi-stage3-20261025-02 sha256:d66812ed9eed2d9706e38056dccfef97868959f88b3d61a83849a8f98ef2ac66 validated and standard-published; real UI rebind and node1 preparation PASS. Same Stage2-derived React flow accepted infrastructure Vault file and session inputs automatically. Plan plan-ac8500d838036d9de1eacabc executable, approved through real React controls; Start returned installer-82f291b9d43e51a137d8df0cb61ef770 RUNNING. Scope SDKU/CSPA, skip SZI and infrastructure Verify, actions APPLY/VERIFY/POST_INSTALL. Terminal acceptance pending.

## Real UI terminal result and display corrections — 2026-10-25

Run installer-82f291b9d43e51a137d8df0cb61ef770 SUCCEEDED through actual Stage2-derived React handlers/Wails: applications:apply, applications:verify and applications:post-install. Saved revision sha256:fd12c741e61da3d1099be6e3cfb0a88f7d1de68ba475a899e663ba53055c59fd; plan plan-ac8500d838036d9de1eacabc; runtime d66812ed. All6 containers healthy, restart0; SZI10 container identities/StartedAt/states unchanged. Independent Keycloak readback6 clients/full profiles/resources/scopes and6 groups/realm+client role assignments PASS. nginx102/103 catalogs each9 routes (6 consumers+3 SZI); all6 endpoints HTTPS200, protected proxy4 correct-client302/frontend2 HTTP200. Agent Java-child data-manager15 fields each, hmi-backend17 fields each match session inputs; Docker Config excludes secret fields. Two demo projects, each ID1/count1, and direct repeat of actual run project asset returns changed=false for both. Evidence .runtime/qa/szi-stage3/results/stage3-install-ui-evidence.json, real-ui-demo-readback.json, szi-before-real-ui.json/szi-after-real-ui.json, ansible-* readbacks. Full current logs: DM/frontend ERROR0; backend unselected alarm-service1 each; CSPA2 startup WebSocket disconnect messages, no claim of zero errors.

Owner connected from a second browser; existing reconnect resumed event replay after delay but lacked actions/percentage. Source cause: Attach response omitted display plan and React explicitly cleared runPlan. Owner requested correction after terminal. New starts retain only the existing safe InstallationPlanView in the existing local operational record (bounded1MiB, no raw manifest/credentials); record identity matches plan/revision/node. Attach returns snapshot, React initializes known action IDs before replay. Display evidence never sets current approval or authorizes Start. Legacy records remain readable and explicitly lack plan/percentage. Unsent Start rollback compares serialized records to handle omitted empty fields. Owner also requested positive checkbox semantics: table Library/Install, all checked by default; unchecked IDs remain skipApplicationLibraries in the Core request.

Go test ./... and go vet ./... PASS; frontend303 tests, lint and production build PASS. Focused93 includes real React attach handler + replay50% and skip selection defaults/restore. Real React/Wails checkbox flow all3 default checked, uncheck/recheck PASS, no plan/Start. Reconnect snapshot real-Wails acceptance remains pending a future authorized execution with snapshot; current completed run predates it. Separate dev binary platform-installer-stage3-ui-fixes.exe built and existing start-wails.ps1 updated; running Wails left intact. No new run/commit/push.
