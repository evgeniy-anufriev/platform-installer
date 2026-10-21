# Kafka / Schema Registry PEM — isolated evidence

2026-10-20. Owner authorized role implementation and isolated verification only.
No installed Kafka/Registry units, application containers, Kafka data/ACLs or
runtime bundles were changed. Worktree:
C:/Users/AnufrievEV/.codex/worktrees/kafka-pem/platform-installer-v2,
baseline6e04b15a52ebf269d434a0d56649618f1b182bb5. The root master changed in another
chat during preparation; four initial owned files were hash-verified into the
worktree and only the two owned role edits were restored in root. Other root
changes were preserved. Reviewed PLAN base was b33a425e; the intervening image
metadata commit is unrelated to this role scope.

## Implementation

Existing platform_kafka_store_type defaults to PEM; explicit PKCS12 retained.
Exact PKI request and usages guards remain. PEM does not read storePasswordSecretRef.
Small native Ansible sequence derives protected identity.pem from existing PKCS#8
key, certificate and CA chain, with public-key equality validation, no_log and
atomic copy. Broker/controller, generic CLI and Registry Kafka/HTTPS configurations
contain PEM paths and omit store/key password properties. Verify checks existing
bundle checksum, owner/group/mode and the installed broker TLS config without repair.
Registry digest/ownership checks remain. Existing restart/change signals include
identity updates. Library-only topic/account hooks and SCRAM bootstrap use existing
invocation-private directories/always cleanup; authoritative PKI material is unchanged.
Global PKI formats/password requirement and Java application PKCS12 are unchanged.

## Environment and source

Primary QA node192.168.56.101, platform-automation persistent EXEC-01 SSH identity,
IdentitiesOnly=yes, sudo-n only for isolated root-owned temporary hook custody.
Existing JDK21.0.12, Kafka clients4.3.1, Confluent Schema Registry/rest-utils8.3.2.
No acquisition/install. Native tests use synthetic RSA PKCS#8 certificates/keys
created under TemporaryDirectory and bind only loopback ephemeral TLS sockets.
They do not start Kafka or Schema Registry service processes. Java source launcher
uses existing jdk.compiler; no workstation Python/Core execution.

Current-source transfer via scripts/qa-sync.ps1. Final code/test workspace:
/var/tmp/platform-installer-qa-a45af175cf0b4e2f83de13a195691710.
Documentation-only status/README updates followed; tested production/test bytes
were unchanged. Earlier fixture attempts lacked the Registry security_protocol,
public role defaults and template lookup context; the harness was corrected and
the complete native suite rerun. Negative assertions inspect protected failure
codes inside Ansible rescue, without disabling production no_log.

## Results

- Native qa_pem_tls.py: **4 tests PASS,261.374s**. PEM Apply/repeat/Verify without
  any store-password file; explicit PKCS12 Apply/repeat/Verify with synthetic
  runtime input. Real Kafka DefaultSslEngineFactory and Registry SslFactory HTTPS
  context load rendered files and perform mutual loopback TLS with CA/hostname
  checks enabled. Native generic CLI executes against an ephemeral rendered config.
- No private key or password property in PEM server/Registry/client properties.
  Repeat changed0; Verify changed0. Injected password property, bad identity mode,
  missing bundle, mismatched key/cert, wrong PKI request, unsupported format and
  PKCS12 without input reject without fallback/repair. Old PKCS12 properties fail
  new-default Verify even if a PEM bundle already exists. Successful/error library
  hook cleanup checks exact invocation directories; authoritative hashes unchanged.
  Hook resource/account lists are empty: these checks prove custody/cleanup, not
  live topic/user/ACL provisioning or SCRAM authentication.
- Service01B23 + Service01D9 + Kafka Registry projection16 + listener6: **54 PASS**.
- Application providers23 + real provider action4: **27 PASS**.
- PKI resolution13 + target-free SCRAM ProjectSnapshot1: **14 PASS**; snapshot6.197s,
  unchanged60s timeout. Total with native4: **99 tests PASS** across these runs.
- Syntax: Kafka Apply/Verify and application-provider Apply/Verify, **4 PASS**.
- git diff whitespace PASS. No Core/Go/UI infrastructure rule changes; no full Go
  or frontend rerun required for this role-only change. No real bridge/visual PASS.

## Review and cleanup

FULL PLAN APPROVE_WITH_CHANGES, blockers0; nonblocking PEM-P01/P02 incorporated.
FULL DIFF APPROVE_WITH_CHANGES, blockers0; see
[independent report](../reviews/kafka-pem-diff-review.md). All21 frozen fingerprints
matched during review. Nonblocking PEM-D01 corrected afterwards: Registry no
longer creates unused separate private-key.pem/certificate.pem copies. Existing
files are retained; helper still reads authoritative source directly.
Post-review focused native PEM and explicit PKCS12 Apply/repeat/Verify/TLS-loader
tests: **2 PASS,208.561s**. Fresh qa-sync workspace:
/var/tmp/platform-installer-qa-3e5bf1ee029542cd9376fb330fbfe081.
Corrected schema_registry_member.yml local/remote SHA-256 matched:
655c3b989b8fa27066ee391c82c5b41aa3ab7e9a83a2269dbfef6e6ae196351b.
This is the sole production correction after frozen review; no new FULL review.
Four superseded source workspaces4c9f8136,796b1fe7,05f92a33,34ffadc1 and the final
a45af175 source workspace were removed through qa-sync -Cleanup.
Post-correction workspace3e5bf1ee was also removed through qa-sync -Cleanup.
Native synthetic keys/processes cleaned by test finally/TemporaryDirectory.

## Remaining acceptance

Real multi-host/controller deployment, authorized PKCS12-to-PEM migration,
restart/recovery and actual Schema Registry schema operations, real React/Wails
flow and matching published bundle remain unperformed. Native evidence covers
synthetic RSA/default provider, not every key/provider/FIPS variant. No stand
installation or target acceptance claimed; those operations remain unauthorized.

## Owner-authorized separate-project installation preparation — 2026-10-20

After the isolated-QA checkpoint, owner authorized a separate project containing
only qa-kafka-structure and in-place Kafka/Schema Registry installation through
a fresh approved plan. Certificate parameters must remain as on other deployments;
host-wide reset, data deletion and neighboring deployment changes are outside scope.

Prepared project: .runtime/qa/qa-kafka-structure-only. Original working project is
preserved. Retained installation identity project-b46aa3f5f57a495f to use the same
existing managed CA; CA/profile/scope/TLS definitions and member placements copied.
Removed other service/application deployments from the new project's desired state.
Admin input submitted through existing pending runtime-secret setter; no value is
recorded here. Registry Kafka listener remains SSL; selected store format is PEM.

Built current-source runtime on trusted acquisition node2 from existing approved
local packages/Python/Kafka/Confluent artifacts; no downloads. Bundle version
kafka-scram-pem-20261020-48, digest
sha256:190ae47e421097aa34fad30c8d58875fe984d9d980c4f779413fb17746336ade.
Standard validation/publication completed; prior runtime47 preserved outside cache.
New project rebound with supported preview/confirm. Real React handlers and Wails
Go methods exercised using the existing bounded Edge preparation seam. node1
prepared and READY on that exact digest; three host fingerprints independently
matched existing trusted records. Project Verify VERIFIED. This is preparation,
not installation or full SI11/visual acceptance.

Initial generated-copy failures: ownership headers omitted by YAML serialization
(WRITE_NOT_ALLOWED), then noncanonical manifest lock-block order rejected rebind
(RUNTIME_LOCK_SET_UPDATE_INVALID). Corrected only the new copy's headers/lock
layout, preserving semantic values; rebind then UPDATED. No production guard bypass.

Fresh plan plan-a8539e3d2993af9612260eaa, revision
sha256:db0ac389929f41a02daa5076e4e46023212961a130d8522350533bb30216e613,
status EXECUTABLE. Actions: PKI_REISSUE for qa-tls-profile--node1/2/3, PKI_APPLY,
SERVICE_APPLY and SERVICE_VERIFY only for qa-kafka-structure. Scope guard stopped
before approval because certificate preservation had not been satisfied.

Existing node1 certificate: CN=*.evoscada.internal; SAN DNS *.evoscada.internal,
node1, qa-clickhouse.evoscada.internal, qa-haproxy.evoscada.internal,
qa-vault-consumer.evoscada.internal; IP192.168.56.101. Kafka-only snapshot resolves
DNS node1/IP192.168.56.101 (analogous node2/3), because pki_resolution derives SAN
from the remaining service consumers/endpoints. CertificateScope explicit UI DNS
does not feed this materialization path. Request fingerprints also cover consumers.
CA file checksum matches existing Kafka/Registry trust:
90fe778a01cfc79930ef96ed8ca1c9eb10c3cb9568fcbc05e855906ad682ae2b.

Owner clarification requested: retain current certificates and hold installation,
or explicitly accept leaf reissue with the same CA/profile and reduced SAN.
No plan approval, Start or Kafka/Registry installation performed at this checkpoint.
No new run ID. Neighbor units/config/public-certificate hashes captured read-only
in .runtime/qa/kafka-scram-pem-before.json; live node2 also contains qa-sr-wails and
qa-schema-registry-20261012, excluded from the plan. Prepared-plan evidence:
.runtime/qa/kafka-pem-install-evidence.json. Staging workspace on node2 retained
pending the certificate decision; service data and certificates were not mutated.

## Owner-selected manual in-place update — 2026-10-20

Owner subsequently chose manual update of qa-kafka-structure. This supersedes
the pending certificate decision above: reuse existing certificates and omit
PKI issuance/deployment entirely. The earlier Installer plan was not approved
or started; this is standalone Ansible execution, not a Go installation run.

Execution Node node1; current verified runtime190ae47e above. Protected execution
workspace /var/tmp/platform-installer-manual-kafka-20261020. Kafka-only desired
context is a copy of .runtime/qa/qa-kafka-structure-only. Runtime-only explicit
PKI inputs bind each existing qa-tls-profile--nodeN directory to its exact Kafka
member. No desired-state PKI projection or marker/fingerprint is forged or edited.
Wrappers reuse the original Kafka identity-discovery/materialization sequence,
Kafka role and Registry phase; no pki-apply import. Credentials are staged only
inside the execution workspace's .runtime/secrets with protected permissions.

Read-only preflight: localhost28, node1 16, node2/3 15 tasks, all changed0 and
failed0. Existing source/active leaf checksums match; OpenSSL chain, advertised
IP and expiry checks pass. Existing wildcard and additional DNS SAN are retained.
Before service changes, protected checksum baselines cover original CA/leaf/key,
PKCS12 stores, materialization markers and /data/qa-kafka-structure/meta.properties.
Cluster identity remains 3N6GP_oL7fty118ZQ_4AVw.

Initial manual attempts exposed missing archive checksum (guard stopped before
service mutation; checksum added from verified manifest) and a newline introduced
by the manual stdin password transfer. The latter was removed without logging
the value. First admin-creation attempt failed; peer hosts nevertheless continued
the original play's finalization, leaving node2/3 in AuthorizerNotReadyException
and broker-listener startup timeout. Restoring the already owner-approved temporary
certificate superuser on node2/3 recovered all three brokers/listeners; recovery
failed0. No certificate/data reset or anonymous superuser was used.

Retried original authorization helpers separately with any_errors_fatal=true,
without restarting brokers: AUTHORIZATION_EXIT0. Admin created and actual SCRAM
credential possession verified; compatibility ACLs configured. Recap localhost28,
node1 266/changed9, node2/3 159/changed0; failed/unreachable0. First failure's raw
stderr was protected by production no_log; newline correction and successful
retry are evidence, not a claim of separately captured parser diagnostics.

Serial1 finalization PASS: remove temporary certificate superuser, restart one
member, verify real admin SCRAM and metadata quorum before continuing. Recap7
tasks/changed2 on each host, failed0. Existing Registry-only phase PASS:
localhost28/changed0, node1 217/changed3, node2/3 214/changed3, failed0.

Independent immutable-input verification PASS,3 tasks/changed0 on each host:
all original CA/leaf/key/PKCS12/marker files and meta.properties remain byte-identical.
Direct final-state audit PASS on all3: both units active, SASL_SSL9096, StandardAuthorizer,
super.users=User:admin, Kafka/Registry PEM, Registry Kafka protocol SSL, private
identities0600 with service owners, zero password= entries in broker/Registry/client
properties. Protected execution-log scan found no admin value/private-key bodies.

## Live findings in the unmodified production tasks

The stock Verify did NOT pass. Manual installation success must not be reported
as acceptance of the ordinary Installer Apply/Verify path. Production source and
immutable runtime were not patched; manual checks retain actual process evidence,
resource-aware security restrictions and immutable-file comparisons.

- **KAFKA-M01:** failed run_once admin creation on node1 did not stop peer hosts
  from revoking bootstrap privileges. Actual peer listener timeouts and
  AuthorizerNotReadyException required the bounded recovery above. Deployment-wide
  failure propagation before revocation needs correction/testing.
- **KAFKA-M02:** authorization_inputs computes AnsibleUnsafeText containing False;
  stock Verify treats the nonempty string as true and rejects finalized hosts.
  Actual process observations were final=true on all3; guarded diagnostic
  normalization accepted only a false string AND demonstrated final runtime.
- **KAFKA-M03:** Kafka4.3.1 --list --cluster --resource-pattern-type match also
  returned wildcard TOPIC/GROUP/TRANSACTIONAL_ID blocks. The stock security guard
  mistook their legitimate ALL operations for CLUSTER administration. Actual
  CLUSTER block contains only ANONYMOUS Describe/IdempotentWrite and certificate
  principal ClusterAction/Describe/IdempotentWrite; no non-admin management grant.
- **KAFKA-M04:** stock ACL Verify reported missing IdempotentWrite despite actual
  IDEMPOTENT_WRITE ALLOW on CLUSTER. Manual verification matches explicit uppercase
  operations within the exact resource/principal block; no ACL was added merely
  to satisfy this false negative.
- **KAFKA-M05:** verify_member drops listener keys when passing dict values to
  the PEM verifier, which expects kafka_ssl_listener.name. Manual runtime metadata
  retains the canonical name alongside unchanged listener settings; actual config
  is not rewritten to work around the checker.
- **KAFKA-M06:** the stock controller quorum diagnostic uses certificate SSL;
  Kafka returns ClusterAuthorizationException / needs ALTER permission. Granting
  ALTER to that principal would violate the owner-selected boundary. Manual quorum
  diagnostics use the already authenticated admin on SASL_SSL broker listeners.

Shared account templates also need the existing generic runtime secret-file map
in post-bootstrap SASL mode; manual invocation supplies the same file map under
platform_application_secret_files, without duplicating secret values.

Final manual component verification PASS. Original per-member runtime/storage
and all9 Kafka listener TLS handshakes passed with retained listener-name metadata.
Final verify-complete.yml then checked exact11 real ACL bindings, sole-admin
management restrictions, actual SCRAM login, quorum and unfenced brokers through
each of the3 SASL bootstrap addresses, original Registry ownership/PEM/configuration/
readiness checks and immutable-input comparisons. Quorum keeps cluster ID
3N6GP_oL7fty118ZQ_4AVw, voters1/2/3, ready leader1; direct status showed follower lag0.
Final recap: localhost28, node1 179, node2/3 167; changed0, failed0, unreachable0,
rescued0 on every host. The earlier stock Verify failures are retained above;
this PASS applies to the explicit manual component checks, not the stock entrypoint.
Normal automated acceptance and cold-start/failure-path tests remain open.

Manual invocation corrections also included the generic secret-file alias for
shared templates, explicit original-host bootstrap addresses and running the
remaining administrative diagnostics sequentially on node1. Failed intermediate
diagnostic wrappers did not repair or mutate infrastructure. Source and immutable
runtime were not modified to hide the stock checker failures.

Neighbor preservation:35 certificate/marker/neighbor configuration hashes match
the pre-update snapshot. qa-sr-wails unit PIDs remained unchanged. The older
srqa Kafka/Registry qa-schema-registry-20261012 units on node2 changed PIDs through
automatic restarts (counters exceed1000/300); their configs/certificates were not
changed. Public leaf AND isolated CA expired Oct14 10:18:11 UTC, before this task.
Their restart cause is not attributed solely from these observations; no repair,
stop/start or cleanup of those neighboring deployments was performed.

## Final artifacts and cleanup

Local evidence: .runtime/qa/kafka-manual-evidence-20261020 (36 public wrapper/log
files, including retained failures and final successful recap), final safe state
.runtime/qa/kafka-scram-pem-final-state.json, preservation comparison
.runtime/qa/kafka-scram-pem-preservation.json. Final log scan: no admin password
value or private-key bodies. No credential/property files were exported.

Removed the execution-only SSH key, password, JAAS/admin/SSL client properties and
private diagnostic copies; the execution .runtime/secrets directory is now absent.
Original protected local runtime input remains in the established secret store.
Removed only the empty failed preparation directory under execution/manual-kafka;
retained public execution evidence. Source/build workspace e81497d6 on node2
cleaned using qa-sync -Cleanup. Prior runtime47 remains preserved outside cache;
current runtime190ae47e and separate project's verified bundle remain available.
No source-code commit/push or neighboring service repair was performed.


## KAFKA-M01–M06 source repairs and admin inventory — 2026-10-21

Owner authorized source corrections, isolated RED OS QA and documentation only.
No stand installation, Kafka/Registry restart, certificate issuance or bundle
publication. Earlier manual execution and stock failures above remain historical
evidence; source repairs do not turn that run into a stock Apply/Verify PASS.

Production remains ordinary Ansible tasks and existing templates/SecretRefs:

| Finding | Source correction |
| --- | --- |
| M01 | Fatal all-host admin/ACL barrier; standard Kafka Apply also has any_errors_fatal. One run_once loop delegates finalization to members in node order, one at a time. Each revocation waits for listeners, confirms that the process loaded admin-only superusers, then queries quorum using admin before the next member. Failure leaves later members untouched; successful prior revocations are not undone. |
| M02 | Normalize the aggregate bootstrap decision with trim/bool; boolean conversion also applied to host observations and Verify predicate. |
| M03 | Select CLUSTER resource blocks before rejecting non-admin administrative ALLOW operations; wildcard data-resource ALL cannot masquerade as cluster administration. |
| M04 | Prior27a94a90 already corrected operation normalization by using the folded YAML predicate with properly escaped regex backreferences. Keep that implementation; add native integration coverage for exact CLUSTER IdempotentWrite/ClusterAction selection from mixed-resource inventory. |
| M05 | Preserve dictionary listener key as name when passing listener settings into the PEM verifier; no embedded name field is required. |
| M06 | SCRAM quorum diagnostics use admin with --bootstrap-server on the unambiguous SASL_SSL broker listener. Broker registration diagnostics use the same administrative identity and validate each broker's selected listener name/protocol/address. Without SCRAM the controller/client diagnostic paths remain. |
| Admin inventory | authorization_setup reads fresh SCRAM metadata before application_account and provides the generic secret-file alias across initial and finalized admin templates. Existing admin credentials are authenticated, never reset. |

Admin CLI configuration uses a private mode0600 temporary properties file from
the existing runtime SecretRef, always removed; secret values are absent from
argv. SASL_SSL uses the existing CA truststore and SCRAM admin, without client
keystore/admin certificate privileges. Explicit PKCS12 truststore passwords
remain runtime-only under the existing option; PEM requires none.

Isolated QA PASS; independent FULL DIFF result recorded below.
Final source/test identity is recorded in the dedicated review report. An
unrelated concurrent inline-secret/UI workstream is excluded from this scope.

Intermediate QA retained: first native8 sixPASS/two fixture failures (delegated
hosts absent from synthetic inventory; dummy JAAS parser assumed unescaped '=');
native9 repeat eightPASS/one negative fixture incorrectly expected the runner
to fail rather than return rc to its caller. Initial Kafka35 regression34PASS/
one stale PKCS12 fixture missing formats; fixture updated to current contract.
Attempted M04 one-backslash rewrite failed CamelCase coverage and was reverted
to the prior working spelling. No production retry/readiness timeout changed.

Remaining acceptance: fresh published-runtime normal Kafka Apply/Verify/repeat,
multi-node cold start and interrupted-bootstrap recovery through real execution.
These are not authorized by this isolated repair task. Synthetic CLI/finalization
substitutions prove task routing/barriers, not real Kafka quorum availability.
The earlier alarm-view application run does not cover service installation.

Final isolated RED OS node2 evidence (current qa-sync sources, no live Kafka/Registry calls):

| Check | Result |
| --- | --- |
| New native service repair scenarios | 11 PASS /218.160s |
| Exact ACL/operation native checks | 5 PASS /24.572s |
| Kafka regression, including native CLI retry and exact PKI selection | 35 PASS /40.666s |
| After final revocation-scope guard: affected transition cases | 5 PASS /36.068s, including new limited-play refusal |
| Standard service Apply/Verify syntax | 2 PASS, no targets executed |
| Final source verification and git diff --check | PASS |

This is51 cases before the final guard, plus five affected-case executions
(four repeats and one new case):52 distinct cases covered across the final
combined evidence. The guard only constrains revocation; preexisting admin
setup still delegates to the selected broker. A limited bootstrap play must
include all deployment hosts before sequential revocation is allowed.

Final source/test snapshot: base61c52f194d45c11d6ddd8991424026372f4190f3,
15 sorted path/file-SHA256 pairs fingerprint
sha256:c98af61a7cfe20553d3f18804d2d939aeb03c3350f9ecea2394000b4a689cb76.
All15 bytes unchanged after QA. Detailed independent review: [FULL DIFF](../reviews/kafka-service-repairs-diff-review.md).
QA copies a92f4b82/d6458474/32bb08d2/d12f8f27/1ccf0618 cleaned with standard
qa-sync; local synthetic evidence retained. No new runtime bundle, real
React/Wails execution, stand mutation or commit/push. Final real service
Apply/Verify/repeat and failure-recovery acceptance remain open.

Independent FULL DIFF final verdict APPROVE, open BLOCKING0, CURRENT for the
final15-file snapshot above. KSR-D01 generic admin secret-file scope and KSR-D02
selected-listener broker expectations corrected within the same review pass;
no targeted recheck invoked. Review does not authorize installation.


## Read-only stand Verify of existing qa-kafka-structure — 2026-10-21

Owner superseded the intermediate Apply/Verify/repeat authorization with read-only
Verify only. No Apply, restart, PKI issuance, cold start or bootstrap fault
injection authorized in this run. This is standalone current-role Verify, not
a real React/Wails installation run; no Installer plan/run ID. The earlier
skipInfrastructureVerify request applies to plans; no infrastructure pre-Verify
plan stage is invoked by this standalone role test.

Execution Node node1 (.101), target nodes .101/.102/.103; original Kafka-only
project context and exact runtime PKI requests/plans copied into a new protected
execution workspace. Source copied through qa-sync; all15 reviewed source/test
hashes match fingerprint c98af61a7cfe20553d3f18804d2d939aeb03c3350f9ecea2394000b4a689cb76.
Fresh runtime-only admin/SSH inputs under the established protected secrets
channel; no values in project or command arguments. Existing CA/certificates/
keys/stores/markers/data identities remain the immutable baseline.

The wrapper performs normal validation/discovery/derived identity projection
and calls the unmodified current platform.kafka.kafka_kraft role with
platform_kafka_verify_only=true and platform_kafka_phase=full. No prior manual
normalization, injected listener names, resource-aware replacement checks or
replacement quorum commands. A final read-only checksum comparison uses the
retained original PKI/data-identity baseline. No pki-apply import.

**PASS**. Command rc0, no failed/unreachable hosts. Observed local execution
window2026-10-21T12:07:08Z–12:21:10Z (15:07:08–15:21:10MSK), approximately14m01s
including SSH/process startup and output delivery; not an isolated CLI benchmark.

| Host | ok | changed | failed | unreachable |
| --- | --- | --- | --- | --- |
| localhost | 28 | 0 | 0 | 0 |
| node1 | 424 | 0 | 0 | 0 |
| node2 | 291 | 0 | 0 | 0 |
| node3 | 291 | 0 | 0 | 0 |

Real admin SCRAM metadata/login, sole-admin security ACL guard and declared
compatibility ACL verification PASS. Kafka member process/config/identity,
PEM verification and9 real TLS handshakes PASS. Quorum via admin/SASL_SSL and
exact registered/unfenced broker listener checks PASS. All three Registry
units/configuration/PEM, SSL broker readiness and existing schema-topic policy
PASS; HTTP/HTTPS readiness6 successful probes, no schema writes. Topic creation
and all service mutation/revocation tasks SKIPPED. Original CA/leaf/private keys,
PKCS12 stores, markers and meta.properties checksum assertions PASS on all3.

Safe evidence under .runtime/qa/kafka-service-stand-*: verify-01.log,
result.json, source-proof.json, task-summary.json and secret-scan.json.
No admin value or private-key body detected in the execution log. Runtime-only
admin/SSH inputs removed and absence checked. Standard source verification PASS.
Initial qa-sync cleanup failed on root-owned Python bytecode/validation output;
after verifying the exact owned workspace path, its ownership was restored and
standard cleanup PASS. The protected public execution context/baseline remains;
source workspace removed. Prior manual context and service files not rewritten.

This closes live current-role read-only Verify coverage for the M02–M06/admin
inventory paths. Bootstrap revocation/rolling Apply, repeat Apply, cold start,
interruption recovery, stock full PKI playbook and real React/Wails installation
acceptance remain open. Owner revoked Apply authorization for this run; no
bundle publication, PKI reissue, service restart, Installer Start or commit/push.

Commit preparation removed only a redundant blank line at EOF in verify_quorum.yml
found by staged diff --check (previous untracked file). Task content/behavior
unchanged; reviewed and stand-tested snapshot identities above remain exact
historical evidence. No tests or stand run repeated for this whitespace-only edit.
