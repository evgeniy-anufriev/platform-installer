# SI08-B — standalone Vault role — DONE

Owner authorized the next milestone on 2026-09-26 after SI08-A commit
`c154bc0`. Authority: service-install-08-vault-architecture.md §3–9.

Scope: ordinary documented Ansible variables, normalization/preflight,
materialized PKI, approved package source, isolated units/config/data/audit,
one init followed by sequential unseal, audit/KV v2/userpass configuration,
read-only verify and standalone 1/1 and 3/1 fixtures. No active catalog or
Installer lease/delivery/UI integration; SI08-C/D/E are not started.

Implementation checks must include identity/resource collisions, TLS join,
safe retained standalone bootstrap files, no re-init on lost response,
initialized/sealed repeat prerequisites, incompatible mounts/audit preservation,
and real systemd BindPaths support. No Vault data cleanup is authorized.

Initial read-only QA observation: RED OS 8.0.3, systemd 253.30, SELinux
Disabled. An isolated systemd BindPaths probe passed without installing Vault
or changing Vault state. This proves namespace behavior only on the observed
non-enforcing host and makes no claim about enforcing SELinux.

Raft memory policy: disable_mlock=true per pinned upstream guidance and require
swap already disabled in preflight; do not change host swap policy implicitly.
Production verify is read-only. No deployment acceptance is claimed yet.

## Bootstrap serialization decision

The former SI08-B-BOOTSTRAP-LOCK-01 blocker is superseded by the accepted
shared-lock design. Apply uses the fixed root-owned `/run/lock/platform-vault`
directory and a persistent lock inode named by SHA-256 of deployment ID. A
transient systemd unit holds `/usr/bin/flock --nonblock --exclusive` on that
inode through the mutating lifecycle; the standalone Ansible and Installer
paths share this role boundary. The unit uses `Type=notify` and is considered
active only after `flock` acquired the lock and the holder sent `READY=1`.
`Type=simple`/`ActiveState=active` alone is not accepted as lock proof.
`always` stops only the current invocation's random transient unit. The lock
inode is never unlinked, preventing split-lock races. A controller crash may
leave a holder behind; this is fail-closed and requires an operator to confirm
no apply is active before manual release. No automatic scavenger exists.
Verify-only is read-only and takes no apply lock.

### Filesystem ancestry preflight

Before provisioning writes, preflight inspects every fixed Vault root and each
deployment/member/PKI directory component with no-follow `stat`. Existing
components must be real directories with the expected root or service-account
ownership. This applies independently to config, Raft data and audit-log trees.
Provisioning explicitly creates/retains root-owned root and deployment parent
directories before creating service-owned member directories. A substituted
symlink or unsafe owner/type stops the role before it reads retained member
state or writes into the tree. The check is bounded to the known paths derived
from validated deployment and member IDs; it does not scan filesystems.

### Artifact source behavior

Vault follows the same two-mode source behavior as existing service roles.
When Installer artifact-source authority is active, or a resolved source map
is already supplied, the common `artifact_source_gate` is required before
mutation and the selected repository/offline artifact is consumed. A direct
Ansible-only invocation with neither authority input nor resolved map does not
gain a new mandatory gate; the pinned Vault package may be installed from the
operator-configured system repository, matching the established roles. No
Vault-specific source policy or alternate source model is introduced.

## Current implementation and evidence

Implemented: closed primitive/member validation, deterministic normalization,
PKI materialization, isolated unit/config/data paths, protected standalone
bootstrap output, one-time init recovery, sequential seed/follower unseal,
audit/KV v2/userpass configuration and read-only verification. Target-free
standalone 1/1, three members on one host, and three members on three hosts
validation fixtures pass under `sudo unshare -n`, changed=0. The focused lock
playbook passed on RED OS: only one contending unit reached READY, and the
lock was reacquired after both normal stop and holder-process failure. Seven
no-follow path-boundary cases (config deployment/member/PKI, data
deployment/member, log deployment/member) were rejected before the test's
outside-write sentinel; the outside sentinel remained unchanged. Vault role
contract tests: 14 PASS. Read-only preflight and apply/verify syntax checks
passed. Full Core suite: 322 PASS, 4 skipped; catalog and service-schema
reproducibility passed. No Vault package, Vault unit or Vault data was
installed or changed.

Audit rotation is per exact Vault unit: daily, maxsize 100 MiB, fourteen
rotations, mode 0600, and HUP only to that unit's main process. Preflight
requires at least 1,600,000 KiB free on the `/var/log` filesystem, enough for
the current file plus the configured rotation bound. The initial targeted
review lacked the lock/path execution evidence; after that evidence was
recorded, the owner-authorized targeted recheck passed DIFF-01 and DIFF-03.
DIFF-02 passed under the owner-approved existing-service source policy. All
three findings are resolved with zero blocking and zero overengineering
findings. SI08-B is DONE. No real Vault deployment is part of B; it remains
SI08-E work.

The QA host has active disk/zram swap. Raft preflight requires swap already
disabled and never changes host swap policy automatically.
