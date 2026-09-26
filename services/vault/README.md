# Vault package — SI08-C Core integration

This package defines the catalog-backed authoring/settings contract and the
standalone Ansible role. Catalog registration enables Core snapshot, planning,
source authority, PKI and member-list projection. It does not claim real Vault
deployment acceptance; that remains SI08-E.

Modes: one-member standalone and three-member Raft HA, both MEMBER_SCOPED;
distinct hosts are not required. Defaults implemented by B: API 8200,
cluster 8201, stable member slot stride 2, shares 3 / threshold 2. API TLS,
cluster protection, file audit (log_raw=false), KV v2 at secret/ and userpass
at userpass/ are invariants, not user-disableable settings. SI08-B adds daily,
bounded audit rotation per instance. No users/policies are created. Cross-field
bounds (threshold<=shares, threshold>=2 for multiple
shares; port range/collision after slot expansion) belong to Core/role, not Go.

Generated configuration schema contains primitive bounds only. It does not
pretend to prove cross-field runtime validity. Installer authoring and typed
lease UI integration remain SI08-D; real deployment acceptance is SI08-E.
No password, root token, unseal key or selected file path belongs in desired
configuration. Secret inputs and encrypted outputs use the separate contracts
in docs/service-install-08a.md and the parent architecture plan.
