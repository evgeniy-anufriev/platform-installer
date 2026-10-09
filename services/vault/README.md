# Vault package — SI08-C Core integration

This package defines the catalog-backed authoring/settings contract and the
standalone Ansible role. Catalog registration enables Core snapshot, planning,
source authority, PKI and member-list projection. It does not claim real Vault
deployment acceptance; that remains SI08-E.

Modes: one-member standalone and three-member Raft HA, both MEMBER_SCOPED;
distinct hosts are not required. Defaults implemented by B: API 8200,
cluster 8201, stable member slot stride 2, shares 3 / threshold 2. API TLS,
cluster protection, file audit (log_raw=false), KV v2 at secret/ and userpass
at userpass/ and AppRole at approle/ are invariants, not user-disableable settings.
Existing AppRole mounts are retained; a different method at approle/ blocks
configuration before writes. AppRole roles, policies and role/secret IDs are
not created. SI08-B adds daily,
bounded audit rotation per instance. No users/policies are created. Cross-field
bounds (threshold<=shares, threshold>=2 for multiple
shares; port range/collision after slot expansion) belong to Core/role, not Go.

Audit API options are string-valued: new devices use `log_raw: 'false'`.
Configure/verify also accept the existing `"0"` false representation without
rewriting an enabled device. Unknown or true values remain fail-closed;
no general bool coercion is used for this security option.

Transient lock hold/release coordinates one invocation and reports no
desired-state change. Lock admission/readiness/contention and always-release
remain enforced. Persistent directory creation, configuration, PKI, packages
and service changes retain normal change reporting.

Generated configuration schema contains primitive bounds only. It does not
pretend to prove cross-field runtime validity. Installer authoring and typed
lease UI integration remain SI08-D; real deployment acceptance is SI08-E.
No password, root token, unseal key or selected file path belongs in desired
configuration. Secret inputs and encrypted outputs use the separate contracts
in docs/service-install-08a.md and the parent architecture plan.

Filesystem permissions: fixed config/data/log roots are root-owned 0755.
Deployment parents are root-owned with `platform_vault_group` and mode 0750:
the service can traverse them but cannot modify their entries. Member config,
Raft data and PKI directories remain service-owned 0700; private keys and
configuration remain 0600. Ownership/no-follow preflight remains mandatory.

Bootstrap custody: immediately after a usable init response, write only
root_token and explicitly indexed keys to the private minimal recovery record.
Confirm safe readback and synchronize the file/directory with Linux coreutils
`/usr/bin/sync -f` before validation or normal publication. Existing conflicting
custody blocks completion without overwrite. Remove recovery only after a
matching, synchronized admin-token/unseal-shares pair; sync the directory after
cleanup. Interruption recovers through the same files without another init.
Response loss/crash before the first durable record still requires operator
recovery; the role never automatically resets an initialized seed.

Explicit standalone reset: `playbooks/clear.yml` is opt-in and is never called
by apply/verify. It requires ordinary Vault variables and exact acknowledgement:

```sh
ANSIBLE_COLLECTIONS_PATHS=services/vault:ansible-core/collections \
  ansible-playbook -i /path/to/inventory services/vault/playbooks/clear.yml \
  -e @/path/to/vault-vars.yml \
  -e platform_vault_confirm_destructive_reset=vault-ha
```

The acknowledgement must equal `platform_vault_deployment_id`, not the project
display name. Select all intended target hosts and members in the variables;
do not limit out the canonical first member (the shared lock host). Stop active
Installer runs first. Clear takes the existing deployment flock, validates every
selected member before stopping units, then freshly validates stopped members.
Only the standard `platform-vault` account/group is supported by clear.

Clear destroys selected Raft contents but keeps the member root and identity
marker, config, TLS, audit logs, package/account and exact systemd units. Selected
units are stopped/disabled; a later explicit apply starts/enables them again.
No broad service stop, process kill, controller custody or journal cleanup occurs.
Missing/foreign identity, active processes or lock contention block the operation.
This is not an uninstall or automatically recoverable transaction: after partial
failure already-deleted Raft data cannot be restored by the role.

The narrow `platform.vault.clear_member` module opens fixed member ancestry
without following links, validates the held marker/unit/config objects and
deletes contents relative to the held member descriptor. Linux root, Python with
no-follow fd-relative operations and readable Linux descriptor mount identity,
and permission to create a private mount namespace are required. Every directory's
opened `mnt_id` must match the member's mount before descent, including
directories moved after initial admission. Nested mounts, including bind mounts, block clear;
there is no unsafe pathname fallback. `--check` only inspects and predicts data
changes; it does not acquire locks or stop services.

Previous bootstrap tokens/shares are intentionally retained but become obsolete
after reset. Use a fresh protected bootstrap output namespace for the new store;
do not silently reuse old custody. See `docs/service-install-08e-clear.md`.
