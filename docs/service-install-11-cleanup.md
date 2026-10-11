# S11-00 — Installer-free QA baseline: execution record

Owner revision (2026-10-01): do not restore a clean OS image. Remove only
confirmed Platform Installer, Execution Node and QA service installations
from the dedicated RED OS VMs. This produces an **Installer-free QA baseline**,
not proof of a freshly installed OS. The S11 all-services UI run is separate
and has not started.

## Scope and protected baseline

- node1 `192.168.56.101`: prior Execution Node and target;
  node2 `192.168.56.102`, node3 `192.168.56.103`: targets.
- Keep the `platform-automation` account, its SSH trust, passwordless sudo,
  VM network, system resolver, baseline RPMs/repositories and OS-owned data
  needed to bootstrap S11. Use IP addresses for QA SSH access.
- Do not mutate the Windows Installer project, local bundle cache or prior
  documentation/evidence. Do not touch unrelated hosts/deployments.
- All destructive paths must be literal, bounded and checked for ownership;
  absent/ambiguous/foreign paths are recorded, not guessed away.

## Pre-clean inventory and actions already performed

All three VMs were reachable as `platform-automation` with the established
identity and `sudo -n`. No `ansible-playbook`, `execution_protocol.py` or
`execution_controller.py` process was observed. Exact running QA units were
enumerated before mutation. They included Kafka (plus legacy QA instances on
node1), Redis/Sentinel, Vault, ClickHouse, PostgreSQL, HAProxy, Keepalived,
BIND and rootless Docker on node1.

1. Stopped the exact enumerated application units, then HAProxy,
   Keepalived and BIND on all three nodes. Disabled their autostart and
   reset failed QA unit state after removing their unit files.
2. On node1 stopped/disabled `lxc-net.service` and stopped the
   `platform-docker-lxc-ready.target`; no `dockerd` process remained.
3. Removed only QA service RPMs after `rpm -e --test` passed on each node:
   `bind`, `haproxy`, `keepalived`, PostgreSQL/`pg_auto_failover`, `redis`,
   `vault`, ClickHouse packages; node1 also Docker/Compose/containerd/
   rootlesskit and LXC packages. `bind-dnssec-utils` and
   `postgresql-private-libs` were installed with the QA services and removed
   after a second dependency test. OS-baseline `bind-libs` and `bind-utils`
   were retained by installation-time comparison with `systemd`.
4. Removed exact enumerated custom service unit files, Vault logrotate
   entries and the Docker readiness target; reloaded systemd.
5. On each host the only difference between `/etc/hosts` and the existing
   pre-Installer backup was the bounded `PLATFORM INSTALLER MANAGED HOSTS`
   block. Restored `/etc/hosts` from that exact root-owned backup; SHA-256
   now matches on all three. Removed the exact Platform DNS-client resolved
   drop-in and restarted the previously active systemd-resolved service.
6. After path/type/mount checks, removed the enumerated service config/data/log
   roots for Kafka, Redis/Sentinel, Vault, ClickHouse, PostgreSQL, HAProxy,
   Keepalived, BIND and Docker/LXC. Removed Execution Node releases, runtime,
   journals and workspaces under its exact Installer roots. No run was active.
7. Removed the identified QA temp workspaces, Core/NET-04 archives/logs,
   stale Ansible tmp, PostgreSQL tmp and bounded Installer backup/candidate
   files. Removed orphaned ClickHouse SysV links and limits file. OS-owned
   systemd-private temp directories and admin-owned `dnf-admin-*` remain.
8. On node1 disabled `platform-docker` linger, terminated its user session,
   verified its processes and user runtime had exited, then removed that QA
   account, its home, subuid/subgid entries, LXC configuration and lease.
   Removed the QA service accounts on all three VMs only after confirming no
   process ran under them. Preserved `platform-automation` and its SSH/sudo
   bootstrap; removed only its identified QA/Ansible temp files.
9. Cleared the empty Kafka and Redis/Sentinel systemd slices (plus the legacy
   exec01a Kafka slice on node1) after verifying `TasksCurrent=0`. They no
   longer appear in the slice listing.

## Final audit — PASS for the bounded S11-00 contract

On node1/node2/node3, SSH as `platform-automation` and `sudo -n` work;
`sshd` and `systemd-resolved` are active; the enabled RED OS repositories
remain listed. All `/etc/hosts` files have the same restored SHA-256:
`ebe6a0f64091eb7a69a4a5d4ce98c1b9c3ee1311d5e0148ba4e612d67d87dc4e`.
The exact Installer/Execution Node and QA service roots tested in the final
audit are absent. The QA application RPMs, accounts, units and listening
service ports are absent; only the OS resolver listens on loopback port 53.
Root filesystems have 26/28/27 GiB free on node1/node2/node3 respectively.

The remaining failed units are `mcelog` and three VirtualBox guest units on
each VM, not current or legacy Installer deployments. Baseline `bind-libs`,
`bind-utils` and `bind-license` remain; `bind` server is absent. The existing
`/etc/selinux/config` says `SELINUX=disabled`; S11-00 did not change this OS
policy or attempt an image-level rollback. No pristine-OS claim is made.

S11-00 is complete. The all-services Wails/React installation acceptance is
**NOT STARTED** and must use its separate UI-only test cases.

## Repeat S11-00 — 2026-10-08

Owner explicitly requested cleanup by S11-00 and clarified that the scope is the test servers. node1/node2/node3 (192.168.56.101/.102/.103) were inventoried through strict known-host SSH as platform-automation with the persistent EXEC-01 identity and sudo -n. No execution controller/protocol/ansible-playbook or Installer browser process was running. All identified QA service units were stopped/disabled before package/data deletion. Removal used exact enumerated roots with owner/type/realpath/mount checks; rpm -e --test passed before QA RPM removal. Baseline bind-libs/bind-utils/bind-license and existing OS/network/repositories were retained.

Removed Kafka, Redis/Sentinel, Vault, ClickHouse/Keeper, PostgreSQL/pg_auto_failover, HAProxy, Keepalived and BIND where installed, plus Docker/rootless/LXC on node1. Removed service configuration/data/logs, Installer PKI and execution/runtime/workspaces, custom units/drop-ins/logrotate, RPM-generated service rpmsave/candidate files, QA-only accounts/homes, rootless linger/subids/network lease, known QA/Ansible/temp workspaces and residual runtime directories. node1 cleanup paused on a transient remaining platform-docker process after terminate-user; no files were deleted while it was present, and retry followed only after the process exited.

Final audit: SSH and sudo -n work on all three, sshd/systemd-resolved active; no QA RPMs/accounts/service processes/listening endpoints, no enumerated Installer/service roots or QA temp directories. The old queried named.service appears only as not-found/inactive, with no installed unit/package/process. /etc/hosts remains unchanged and matches ebe6a0f64091eb7a69a4a5d4ce98c1b9c3ee1311d5e0148ba4e612d67d87dc4e on each VM. No LXC bridge/veth or Keepalived VIP remains. Existing enabled RED OS repositories remain. Root free space: node1 25 GiB, node2 28 GiB, node3 27 GiB. Empty /run/clickhouse-server on node2/node3 was separately owner/process/mount checked and removed. Protected platform-automation SSH/sudo bootstrap files and OS-owned egl_external_platform.d retained.

Evidence: .runtime/qa/s11-00-cleanup-20261008/ holds inventories, literal bounded cleanup scripts and per-node safe cleanup/audit logs; no secret contents captured. Windows projects, exported copies, bundle cache, protected local secrets and all uncommitted source changes retained. This repeat proves an Installer-free QA baseline, not pristine OS or secure erasure of shared OS journals. A new installation/run is not authorized by cleanup.

## Repeat cleanup — 2026-10-11

Owner explicitly authorized removal of all Installer-installed services, their
data and the Installer runtime/data on node1/node2/node3
(192.168.56.101/.102/.103). Strict known-host SSH as `platform-automation`
with the persistent EXEC-01 identity and `sudo -n` succeeded. Before mutation,
no Installer/Ansible execution process was active. The exact selected service
units and service RPMs were inventoried; all service data/runtime roots passed
literal-path, owner, realpath and mount-boundary checks. RPM erase dry-runs
passed on all nodes.

Stopped and removed BIND, ClickHouse/Keeper, Kafka, PostgreSQL/pg_auto_failover,
Redis/Sentinel, Vault, HAProxy, Keepalived, DNS-client configuration and
rootless Docker/LXC. Removed their 28 service RPMs per node, service
configuration/data/log paths, exact custom units/drop-ins, generated
`rpmsave` files, service accounts and rootless subuid/subgid entries. On all
three nodes removed `/etc/platform-installer` and `/var/tmp/platform-installer`;
on node1 also removed `/var/lib/platform-installer` (about 6.6 GiB) and 16
bounded Installer QA workspaces. The separate
`/var/lib/platform-app-probe-qa` directory on node1 was preserved as agreed;
its Docker engine was removed with the Installer-installed Docker deployment.

One initial node2 cleanup invocation returned nonzero after completing its
mutations because a final check incorrectly required node1's separate
`platform-app-probe-qa` directory on every host. A fresh read-only node2 audit
confirmed the cleanup state before continuing; node3 and node1 then completed.
The node1 Kafka unit took longer to stop cleanly; no data was removed until all
service processes had stopped.

Final audit PASS on all three nodes: no Installer runtime roots, service data
roots, QA temp workspaces, service RPMs/accounts/processes, Installer units or
service-specific RPM residuals remain. Only OS baseline `bind-libs`,
`bind-utils` and `bind-license` remain from the BIND package family. The
systemd resolver is active, `/etc/hosts` retains baseline SHA-256
`ebe6a0f64091eb7a69a4a5d4ce98c1b9c3ee1311d5e0148ba4e612d67d87dc4e`, and
`platform-automation` SSH/sudo remains usable. No service listeners, Keepalived
VIP or LXC bridge remains. Workstation sources, project, bundle cache and
protected local secrets were not touched. This is not secure erasure of OS
journals or proof of a pristine OS; no installation was started.

Safe final audit metadata: `.runtime/qa/s11-00-cleanup-20261011/audit.txt`.
