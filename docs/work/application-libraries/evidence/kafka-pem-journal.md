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
