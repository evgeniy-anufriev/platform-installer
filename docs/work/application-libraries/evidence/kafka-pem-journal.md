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

Finalization now uses serial1: remove temporary certificate superuser, restart
one member, verify real admin SCRAM and ready metadata quorum before continuing.
Then execute the existing Registry-only role phase and full read-only role Verify
with original-PKI/data-identity checksum comparison. These final stages are still
running at this checkpoint; final result and cleanup will be recorded here.
