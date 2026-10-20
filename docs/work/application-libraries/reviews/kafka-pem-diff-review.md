# Kafka PEM — independent FULL DIFF review

Date: 2026-10-20. Reviewer: independent architecture-reviewer,
scram_compatibility_plan_review. Reviewer was read-only and did not run tests.

**APPROVE_WITH_CHANGES. Unresolved BLOCKING: 0.**

## Review identity

Worktree: C:/Users/AnufrievEV/.codex/worktrees/kafka-pem/platform-installer-v2.
Baseline: 6e04b15a52ebf269d434a0d56649618f1b182bb5.
Frozen scope: [kafka-pem-diff-scope.json](kafka-pem-diff-scope.json), SHA-256
0A3D830B09E07AC032BAFAE753CF52CF734ED8710DBE099B049FAEB701CCD8DF.
All 21/21 fingerprints matched, including the reviewer's final check.
Reviewed plan fingerprint:
8bfb414af11cb23df33a493bdde13634a3326d38fc2dd5cde37d898b0fce6478.

## Finding returned by reviewer

**PEM-D01 — NON_BLOCKING:** schema_registry_member.yml copy loop unnecessarily
copies separate private-key.pem/certificate.pem, including explicit PKCS12 mode.
Registry runtime uses identity.pem or keystore.p12; readiness uses the CA bundle.
The identity helper reads authoritative source directly. Extra protected copies
add sensitive artifacts and maintenance work without adding capabilities.

Recommended bounded correction: omit these two destinations, retaining CA,
fingerprint, selected stores and identity helper. Do not delete existing files.
Validate native PEM/PKCS12 materialization, repeat/Verify and TLS loaders.
Reviewer explicitly stated that this correction needs no repeated architecture
review. Implementer applied this two-item copy-list correction after the frozen
review; subsequent validation is recorded in the journal. Frozen fingerprints
remain historical review evidence, not hashes of the corrected final tree.

## Confirmed boundaries

PEM default and explicit PKCS12 override without fallback; exact request/usages/
formats guards; no store-password lookup/properties in PEM branches; protected
atomic identity copy with PKCS#8/key-certificate validation; read-only consumer
and broker-config Verify; existing restart signals; private CLI/provider/bootstrap
bundles and always cleanup; Registry SSL listener, identities, ACL policy and
CA/hostname checks retained. Core PKI pipeline, Java application stores, desired
state authority and Go/UI ownership are unchanged.

PEM-P01/P02 from PLAN review are RESOLVED: temporary hooks do not mutate the
authoritative PKI directory; compatibility and pre-migration Verify are explicit
in documentation and tests.

Overengineering: unnecessary abstractions, duplicate contracts, new persistence/
API/lifecycle layers, premature scope and speculative features: 0. Shared native
Ansible helper is justified by existing consumers. No new production Python
executable or parallel secret transport.

## Evidence and limits

Reviewer inspected the scoped diff, helpers/tests, plan, journal, instructions
and relevant PKI/project contracts using ansible-core-review. Native tests use
production tasks/templates, Kafka SSL engine, Registry HTTPS loader and loopback
TLS. Parent-reported evidence: 99 tests and four syntax checks PASS. Reviewer did
not independently execute these tests or inspect targets/secret values.

Empty-list hook checks prove custody/cleanup, not live provisioning. No stand
migration, multi-host restart/recovery, real React/Wails bridge, bundle publication
or Registry schema-operation acceptance. Those gates remain unperformed.

Review validity: CURRENT for the frozen scope above. The sole subsequent source
correction is PEM-D01 as described; documentation status/evidence was finalized
after review. No automatic second FULL review was performed.
