# SERVICE-INSTALL-10 — Docker rootless + Compose architecture and acceptance

Status: DONE (2026-10-01). This plan does not
change the deferred EXEC-PLAN-SCOPE-01 or partially accepted SI09 milestones.

## Goal and boundaries

Install standalone Docker Engine in rootless mode and the Docker Compose CLI
plugin on RED OS. No Swarm, rootful Docker daemon, registry login, container
deployment, or workstation-to-target Docker control is introduced. The service
remains usable by autonomous Ansible with documented inventory variables;
Installer/Core/Go/Wails use the existing service-manifest, PKI and runtime
secret paths rather than a Docker-specific editor or transport.

The operator selects either `create-user` or `existing-user` and supplies a
bounded account name. In create-user mode, the password is supplied via the
existing per-service Secrets dialog as a session-only `SERVICE_PASSWORD`
requirement; the portable project stores only `passwordSecretRef`. The Ansible
role accepts an equivalent runtime-only secret-file mapping for autonomous
installation. In existing-user mode, the role must not set or change that
account's password, UID, home or shell; it fails if the account is ineligible.
The create-user password is applied without exposing plaintext in Ansible
output, environment, command arguments, logs or project files. Reapply must
not rotate or rewrite an unchanged password. The standard Ansible user module
creates an initially locked account; a subsequent protected `chpasswd -e`
task receives the runtime-derived hash through stdin only when the account
is still locked/unset. A later Apply does not rotate the password. Under the existing `SERVICE_PASSWORD`
contract, create-user Verify also requires that session secret; existing-user
Apply/Verify do not.

## Runtime and network

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
alive without a login session. Apply/verify check both managers, target
state and daemon state; no claim of a direct cross-manager `After=` edge.

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

## Gates

1. One independent FULL PLAN architecture review with mandatory
   overengineering check before implementation; BLOCK stops the milestone.
2. RED OS package/preflight and autonomous Ansible apply/verify/reapply,
   including `changed=0`, unsupported OS, missing LXC helper, existing-user
   safety, create-user password, TLS positive/negative clients, and
   no-Swarm proof.
3. Target/bridge proof: lxc-net stopped means dockerd never starts; a late
   lxc-net start activates the target and Docker without polling; stopping
   lxc-net deactivates target/bridge and Docker; after reboot the same order
   holds. Also prove a manual user-service start cannot bypass the gate.
4. Target-free Core plan and actual Go execution; real nonvisual React/Wails
   Secrets -> plan -> Start -> terminal result. Mocked frontend tests are
   supplementary only.
5. Focused unit/schema/catalog tests, full Core suite, Go tests/vet, frontend
   lint/test/build, affected race checks, security/secret audit, and
   `git diff --check`. High-risk container runtime DIFF gets one independent
   FULL DIFF review. No DONE claim without all applicable gates.

## Existing-work separation

SI10 is developed in a separate worktree. The primary checkout's unrelated
EXEC-PLAN-SCOPE-01/SI09 changes are not part of this milestone.

## SI10 acceptance evidence (2026-10-01)

- The two owner-approved DIFF corrections are in scope: a narrow root-owned,
  no-follow destination guard for Docker/LXC files, and explicit dual
  `serverAuth`/`clientAuth` EKU proof on the selected PKI certificate. The one
  authorized targeted recheck resolved `S10-DIFF-01` and `S10-DIFF-02` with
  zero blocking or overengineering findings.
- The RED OS repository publishes `docker-ce-rootless-extras` version `29.7.2`
  as `noarch`, unlike the other x86_64 Docker packages. The manifest now uses
  its exact repository architecture; the generic source resolver is unchanged.
  Focused positive/negative source-identity tests pass.
- The immutable QA runtime is
  `sha256:46fbb7be6578c5e5c004188e7ad6b8b4945ab8519365a820374d4d61e8770165`;
  catalog digest is
  `sha256:5d32e0fdc5526625edd329f3cb5a16f3f3cfa471811207435e0daed789dd9c7a`.
  The QA project's saved revision is
  `sha256:bfe22067146e6774cd287ccc23d964197a614f6e01c4f934b710404c445f9501`.
- Real nonvisual React/Wails invoked project open, Execution Node readiness,
  service Secrets, fresh plan, approval, Start and terminal observation through
  bound Go methods. Plan `plan-5b4f134cb5ef60834cdd0290` produced initial
  run `installer-b37382a3d07ccc3ce4472f2d251274db` and strict repeat
  `installer-5c5f5df7fa464a1f7ace36eae87209dc`. Both authoritative runs
  SUCCEEDED with PKI apply, Docker apply and Docker verify SUCCESS. The repeat
  had zero CHANGED and zero FAILED task results; the React/Wails polling
  observed its terminal SUCCEEDED state. A headless dev-bridge warning in
  `/wails/ipc.js` did not prevent any bound operation; it is not a React
  application exception or a substitute for the successful terminal proof.
- Direct autonomous Ansible apply/verify/repeat passed for both an existing
  account and create-user mode; repeat recaps were `changed=0`. After the
  Installer run, stopping `lxc-net` stopped the target, system/user bridge and
  rootless Docker. A manual user-service start failed while the target was
  unavailable. Starting `lxc-net` restored the whole chain. A controlled QA
  reboot restored all four units automatically; rootful Docker service/socket
  remained inactive. `docker compose` reported `5.3.1`; the TLS API returned
  `OK` with the selected PKI certificate and rejected a client without a
  certificate. No active LXC/Docker containers or unrelated execution run
  were present before the controlled stop/reboot tests.
- Final gates: RED OS Core `python3 -m unittest discover -s ansible-core/tests
  -p 'test_*.py' -q` passed 419 tests (19 skipped); focused Docker safety/TLS
  tests 2/2 passed; apply/verify/clear syntax-check passed. `go test ./...`,
  `go vet ./...`, affected RED OS Go race tests, frontend lint, 67 frontend
  tests, frontend production build, and `wails build -nopackage -clean` passed.
  Catalog and service-schema generators reproduced their checked-in outputs;
  focused secret-literal audit and `git diff --check` passed. The temporary
  RED OS source workspace was removed after testing.
