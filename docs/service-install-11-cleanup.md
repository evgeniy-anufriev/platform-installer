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
