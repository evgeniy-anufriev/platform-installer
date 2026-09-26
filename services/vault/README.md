# Vault contract foundation — SI08-A

This package currently defines authoring/settings contracts only. It is not
registered by the fixture catalog or runtime bundle. The referenced Ansible
role is not implemented until SI08-B. This directory is not an installable
Vault release and must not be advertised as one.

Modes: one-member standalone and three-member Raft HA, both MEMBER_SCOPED;
distinct hosts are not required. Defaults to be implemented by B: API 8200,
cluster 8201, stable member slot stride 2, shares 3 / threshold 2. API TLS,
cluster protection, file audit (log_raw=false), KV v2 at secret/ and userpass
at userpass/ are invariants, not user-disableable settings. No users/policies
are created. Cross-field bounds (threshold<=shares, threshold>=2 for multiple
shares; port range/collision after slot expansion) belong to Core/role, not Go.

Generated configuration schema contains primitive bounds only. It does not
pretend to prove cross-field runtime validity. Full integration is SI08-B/C.
No password, root token, unseal key or selected file path belongs in desired
configuration. Secret inputs and encrypted outputs use the separate contracts
in docs/service-install-08a.md and the parent architecture plan.
