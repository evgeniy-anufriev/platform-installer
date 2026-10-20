# Kafka PEM — FULL PLAN review

2026-10-20, independent architecture-reviewer /root/scram_compatibility_plan_review.
Verdict: APPROVE_WITH_CHANGES. Exact unresolved BLOCKING: 0.
Plan SHA256 DCDC05569DD4A69E696FED5DF3BB5156FF975A5E3B443D20EF75957464B1C66B.
Baseline b33a425e80bf533aad39ed5dfe805baf48c8f883.

PEM-P01 NON_BLOCKING: clarify library-only hooks assemble identity.pem in their
invocation-private directory with always cleanup and no writes to authoritative
PKI targetDirectory. Persistent copies only in existing Kafka/Registry owned paths.
Verify success/error cleanup and library-only Apply/Verify without service Apply.

PEM-P02 NON_BLOCKING: explicitly test PEM without password, PKCS12 override with
valid password and failure without it, invalid type and no implicit fallback.
Legacy PKCS12 installation under new PEM defaults must fail Verify without repair;
require explicit override or separately authorized Apply migration.

Both clarifications are bounded; no further PLAN review is required.
No new authority/store/transport/UI or ACL boundary. Existing PKCS#8 generation,
file-based Kafka PEM and rest-utils8.3.2 HTTPS PEM helper checked in source.
Overengineering findings: 0. Small shared builtin slurp/copy sequence is justified;
no custom executable or framework. Source support does not prove shipped binaries.

Reviewer read CURRENT_STATE, PKI lifecycle/project contracts, role code and upstream
sources. PKI-01 contract SHA256
66628EDF7FA3F73EC97BAE6FE01826D885BEB251B4A28140C1982230A4F329B7.
Project contract SHA256
D497327CD3B74466087D05E66A1F9576AF3306DD39C3DC9766D68EE8F6E7D598.
No tests/processes/target visits or secret reads. Binary inventory supplied by parent.
Report saved by parent from independent response. Scope excludes global PKI
pipeline, Java app PKCS12 and ACL policy. Review validity CURRENT for reviewed
plan revision; authority/path ownership/store-policy changes need boundary audit.
Proceed with authorized implementation and isolated QA; no stand operations.