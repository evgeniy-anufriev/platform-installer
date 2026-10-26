# Docker rootless and Compose contract

Contract sections extracted verbatim from [the SI10 plan](../work/docker/service-docker-rootless-architecture.md).
Current status is recorded in [CURRENT_STATE](../../CURRENT_STATE.md).

## Goal and boundaries

Install standalone Docker Engine in rootless mode and the Docker Compose CLI
plugin on RED OS. No Swarm, rootful Docker daemon, registry login, container
deployment, or workstation-to-target Docker control is introduced. The service
remains usable by autonomous Ansible with documented inventory variables;
Installer/Core/Go/Wails use the existing service-manifest, PKI and runtime
secret paths rather than a Docker-specific editor or transport.

Account policy was updated by the owner on2026-10-26. The default mode is
`auto`: an absent account is created; an existing account is reused after
password verification. The saved `create-user` and `existing-user` modes remain
supported. `existing-user` rejects an absent account. The only reserved account
name is `root`; actual account eligibility still requires an unprivileged UID
and a supported home directory.

All modes require the existing session-only `SERVICE_PASSWORD` input through
`accountCredential.passwordSecretRef`. The portable project contains only the
reference; autonomous Ansible accepts the established runtime-only secret-file
mapping. No alternative secret store or conditional password admission is added.

An existing account's password must match the supplied runtime value. A mismatch,
locked account or unavailable password verifier blocks Apply without changing
the account's password, UID, home or shell. Authentication uses the system
libcrypt against the NSS shadow record; the check is protected with `no_log` and
passes the runtime value through stdin, never process arguments or environment.
Existing password records are not returned or persisted by the role.

Only an account created by this invocation receives a new password, using the
existing protected OpenSSL SHA-512 hash and `chpasswd -e` stdin sequence. Reapply
verifies the existing account and does not rotate or rewrite its password.
Apply/Verify require the session password reference in all modes. An operator
must separately authorize any password initialization/reset for an existing
locked account; the role never unlocks or resets it implicitly.

## Runtime and network

### Docker data directory

`platform_docker_data_root` defaults to
`/home/{{ platform_docker_account_name }}/.local/share/docker`. The catalog
exposes it as deployment setting `dataRoot` («Каталог данных Docker»,
«Хранение») through the ordinary override/reset and Review/Save flow.
The role writes `data-root` in the selected account's
`~/.config/docker/daemon.json`, preserving other JSON properties, and restarts
the existing managed bridge when the configuration changes. This is the
rootless daemon configuration, separate from the rootful `/etc/docker` path.

The directory must be an absolute bounded path with no traversal, symlink,
foreign-owned or group/world-writable ancestors. System directories and
other users' homes are rejected. An existing leaf must belong to the Docker
account; Apply creates a missing private directory. Changing the setting
does not migrate or delete existing images, containers or volumes. The
operator must plan any required data migration before Apply. Apply validates
the directory and configures `data-root`. Ordinary Verify checks daemon/API
availability, rootless operation and Compose; it does not audit data paths.

RED OS repository packages provide Docker Engine/CLI/rootless extras,
RootlessKit, LXC, fuse-overlayfs and the `docker-compose` package, which
supplies the `docker compose` CLI plugin. Package acquisition follows the
existing repository-first/offline-bundle policy; the role never downloads
from the Internet. Compatibility is proven on the exact RED OS target before
applying, not inferred from package names.

RootlessKit uses `lxc-user-nic` as network driver and `builtin` as port driver.
The LXC package provides `/usr/libexec/lxc/lxc-user-nic` and
`lxc-net.service`. The role validates the installed helper owner/mode and
the bridge before use, configures only the managed account's entry in
`/etc/lxc/lxc-usernet`, and uses the actual helper path in RootlessKit's
environment. It does not replace other users' entries or silently fall back
to slirp/pasta. Required user namespaces and subuid/subgid allocation are
validated and safely configured through the OS-supported path. An active
rootful Docker daemon/socket is a fail-closed conflict, not something this
role stops automatically.
The role selects an owned LXC dnsmasq override with `port=0` so `lxc-net`
provides DHCP without competing with an existing host DNS provider (for
example BIND bound to port 53). A foreign active LXC dnsmasq override is a
conflict, not silently replaced. Container DNS remains Docker's own resolver
path and is verified independently during acceptance.

Rootless Docker is a user systemd service; `lxc-net.service` is a system
service. A user-unit `After=lxc-net.service` is **not** a cross-manager
ordering guarantee. The system manager owns an explicit
`platform-docker-lxc-ready.target` with `BindsTo=lxc-net.service` and
`After=lxc-net.service`. The target is installed as a `WantedBy=lxc-net.service`
dependency, so **every** start of `lxc-net`, including a late restart after a
failed boot attempt, pulls in the target; the target is not dependent on a
finite retry or on `multi-user.target` being entered again. The
account-specific system-side bridge service is also `WantedBy=lxc-net.service`
(not `WantedBy=` the target, which would create a target-ordering cycle), and has
`BindsTo=`/`After=` that target and `Requires=`/`After=` the selected
`user@UID.service`. It uses `Type=oneshot` with `RemainAfterExit=yes`, so its
`ExecStop` still runs when the target stops. It starts the *user-manager*
`docker.service` only when the target is active, and stops that same user
service in `ExecStop` when the target stops. The bridge runs only the
`systemctl --user` control command as the selected account; it never runs
`dockerd` as a system service with `User=`. The rootless user unit is **not**
enabled in the user's `default.target`, so login/linger cannot start it
before the bridge. A user-unit `ExecStartPre` also requires the system target
to be active, so manual `systemctl --user start docker.service` cannot bypass
the gate. There is no finite polling window: a late `lxc-net` start brings
up the target and bridge, then starts Docker. When `lxc-net` stops, the
target and bridge stop and Docker is stopped. Linger keeps the user manager
alive without a login session. Apply configures both managers and the target;
Verify checks the resulting user daemon and API. There is no direct
cross-manager `After=` edge.

## Docker TCP API and TLS

The only network Docker API listener is TCP with mutual TLS (`--tlsverify`),
default port 2376 and explicitly configured external bind address. No plaintext 2375
listener or fallback. Existing PKI materialization supplies an appropriate
server certificate/key and trust CA; client certificate authentication is
mandatory. Requested DNS/IP identities must cover the configured API
address. RootlessKit's `builtin` port driver maps the *external host*
address/port to the distinct fixed `12376` port in the *rootless network
namespace*. `dockerd`
listens on the internal namespace address/port and terminates/validates TLS;
RootlessKit is a TCP forwarder, **not** a TLS terminator. For this LXC
network mode, `DOCKERD_ROOTLESS_ROOTLESSKIT_DETACH_NETNS=false` keeps
`dockerd` in the forwarded child namespace. The two bind
addresses are separately resolved and verified; the internal listener is
not assumed to possess the host's external IP. No unprotected external or
internal TCP listener is permitted. Private key permissions grant access only to the
selected Docker account and required root-owned PKI lifecycle, without
copying keys into the portable project. Apply and verify consume one resolved
runtime projection; Go/React never calculate certificates or TLS validity.

Owner decision for the closed operating environment: reuse the **same
existing PKI-plan certificate and private key** for Docker's TLS server and
Docker API client. Do not create a separate Docker client CA or client leaf.
The selected PKI profile/request must explicitly provide both `serverAuth`
and `clientAuth`, and its SAN must cover the external API identity; otherwise
the service fails closed before exposing the TCP port. `--tlscacert` trusts
the existing PKI-plan CA, not an Internet or arbitrary systemwide CA. A
holder of the shared private key can authenticate as a Docker client; the
owner accepts that risk for the closed environment. The Ansible role does
not auto-export or duplicate the key into the project, logs or Installer
workstation. Authorized client distribution is an operator custody step;
local acceptance uses the existing material without inventing a
certificate-distribution protocol. Negative tests still require rejection
of a connection with no certificate and of a certificate outside the
trusted PKI CA. TLS remains mandatory despite the shared leaf/key decision.

## Service package and owned files

Use one service manifest, schema/compatibility, and a bounded Ansible role with
apply, verify and clear entrypoints following existing services. The role
manages only its selected Docker account's scoped LXC/subid entries,
its user unit drop-in/configuration, and its packages according to the
existing package policy. Clear never deletes an account, even one created by
this role; this avoids needing a second account-ownership ledger. Clear must
not delete a pre-existing account or
unrelated containers, images, volumes, LXC users or other services.
The manifest exposes mode, account name, TLS profile, API address/port and
closed credential metadata via the existing catalog/UI seams; no Docker-only
Wails method or second secret DTO. Defaults, group_vars and host_vars may
override documented role variables for autonomous Ansible. `docker compose`
is available to the selected account; no Compose project is auto-launched.
