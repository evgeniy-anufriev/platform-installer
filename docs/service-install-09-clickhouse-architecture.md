# SERVICE-INSTALL-09 — ClickHouse + ClickHouse Keeper

Status: implementation and isolated service/endpoint QA pass; SI09 NOT DONE.
The pinned RPMs were acquired with signed metadata and SHA-256 proof and
published in immutable runtime releases. Direct Ansible 1/1, 3/1 and 3/3
apply/verify/repeat pass, including cross-host replicated writes and owned
node3 failure/recovery. Direct 3/3 ClickHouse apply/verify and its HTTPS
HAProxy endpoint also pass. The real nonvisual React/Wails cumulative run
`installer-f1c76b8b08a861e5cd10257ddc679809` terminated FAILED at HAProxy
apply, although ClickHouse apply succeeded. The HAProxy TLS-probe timeout was
fixed and verified by a later direct apply, but the owner declined a repeat
full-plan run. Consequently the required real-bridge terminal PASS is absent;
this is partial acceptance only. See `CURRENT_STATE.md` for exact evidence.
The former all-services one-plan final
acceptance moves to SERVICE-INSTALL-10 after this milestone; it is not started.

## Scope and ownership

Add one catalog service `clickhouse`. In HA, each explicitly placed member is
a paired `server + keeper`, analogous to Kafka's paired broker/controller
member. Standalone has only a server. Modes:

| Mode | Members | Placement | Data topology | Keeper quorum |
| --- | ---: | --- | --- | --- |
| standalone | 1 server | 1 host | 1 shard, 1 replica | none |
| raft-ha | 3 | 1 host | 1 shard, 3 replicas | 3 voters, one failure domain |
| raft-ha | 3 | 3 hosts | 1 shard, 3 replicas | 3 voters, three failure domains |

The 3/1 topology proves instance isolation, not host failure tolerance. Do not
advertise it as host HA. Each HA member has one stable ID, one server process
and one separate Keeper process. Standalone starts no Keeper process, allocates
no Keeper listeners and has no Keeper state. All three HA Keeper IDs and all
three replica macros are unique even when host addresses coincide. The service
role validates exact mode-dependent roles and cardinality; no service-specific
branch belongs in Go or UI.

Standalone and HA use one service package, one ordinary-variable Ansible role,
`apply.yml` and `verify.yml`. Manual inventory remains supported without Go.
Core owns topology/configuration projection and the existing PKI and endpoint
resolution. Installer only transports typed intents, plans and results.

## Network and TLS

Every enabled externally reachable protocol is TLS-only: ClickHouse HTTPS
client, secure native TCP, interserver HTTPS, and, in HA only, Keeper secure
client and Keeper Raft.
No plaintext HTTP, native TCP, interserver HTTP or Keeper client listener is
enabled by the managed instance config. HTTPS/native clients authenticate as
the standard ClickHouse `default` user with a password. The RPM may create
that user, but the role must not rely on an interactive package prompt or a
package-generated password. An Installer session supplies the password using
the existing deployment-scoped `SERVICE_PASSWORD` runtime-secret descriptor
in the service's **Secrets** screen. The portable configuration holds only a
`passwordSecretRef`, as with Redis/PostgreSQL; no password is stored there.
The role consumes the existing runtime-only secret-file map. The password is
valid UTF-8, 1–4096 bytes, and is never trimmed or normalized. For the pinned
version, the role renders the documented `password_sha256_hex` verifier of
those exact bytes to an instance-owned, access-restricted users config,
never plaintext. The verifier is treated as sensitive and not logged. Direct
Ansible receives the same ordinary credential reference and protected local
secret-file input, without Installer dependence. Missing/invalid password
blocks apply and authenticated verify; wrong password is rejected at HTTPS.

The role renders service-specific XML
from the established runtime projection and existing PKI materialization; it
does not issue certificates or invent SANs. TLS server authentication is
mandatory at every client and inter-node verification boundary. The HAProxy
backend verifies ClickHouse's CA and hostname, but does not present a client
certificate: ClickHouse authenticates that HTTPS request with the `default`
password. Thus ClickHouse's incoming HTTPS/native TLS does not demand mTLS.
Separate Keeper TLS configuration may require PKI `clientAuth` identities for
Raft/secure Keeper clients; peer certificate verification on all outgoing
connections must be proven on the pinned build. Neither `skip_verify` nor
acceptance of invalid certificates is a managed option. Certificates cover the
effective member DNS/IP names used by clients, Keeper peers and replication.
For 3/1, equal host addresses are allowed but ports, process identities,
config/data/log directories and systemd units remain member-unique.

Use `configuration.port` for the HTTPS client listener (default 8443); expose
that existing generic endpoint-listener contract to HAProxy. The service
endpoint is optional as a project assignment, but this milestone's acceptance
requires one HTTPS endpoint. The endpoint never points to Keeper, native TCP
or an insecure listener. Use existing BIND/Keepalived/HAProxy provider and
certificate-scope contracts: one service backend fragment, CA verification and
hostname verification against the actual certificate. No service-specific Go
backend branch, no React port inference. Other listener bases are closed
deployment settings; per-member overrides are limited to already supported
safe fields and must pass collision/overflow checks before mutation.

Default ports proposed from official examples: HTTPS 8443, secure native 9440,
interserver HTTPS 9010, and for HA only secure Keeper client 9281 and Keeper
Raft 9444. The effective per-member allocation is deterministic and
host-local, with no collisions across enabled listeners. Non-default values are documented
ordinary role variables and catalog-managed settings where safe. The same
resolved values feed apply, verify and endpoint projection.

## Files, package source and state safety

Pin an exact upstream ClickHouse LTS build for RED OS 8 x86_64. Candidate:
`26.8.14.3`, the official LTS published on 2026-09-28. The four official RPMs
exist at the ClickHouse LTS package endpoint: `clickhouse-common-static`,
`clickhouse-server`, `clickhouse-client`, `clickhouse-keeper`. The pinned
`clickhouse-keeper` RPM conflicts with `clickhouse-server` on the same host.
Because this service deliberately co-locates server and Keeper for every HA
member, its runtime package closure is the first three RPMs. The exact pinned
server RPM itself provides `/usr/bin/clickhouse-keeper`; the role verifies RPM
ownership before starting separate Keeper units. The fourth acquired RPM is
not a service requirement and must not be installed on a paired host. Acquisition uses
only `https://packages.clickhouse.com/rpm/lts/` on a trusted Linux DEV
environment. Pin the official repository metadata key's primary fingerprint
`3A9EA1193A97B548BE1457D48919F6BD2B48D754`; reject a different key.
Verify `repomd.xml.asc` against the pinned key, the primary metadata checksum
against signed `repomd.xml`, then each exact RPM's name/version/architecture,
size and SHA-256 against that verified primary metadata. Check exact RPM
dependency closure and RED OS 8 compatibility before import; retain bounded
source URLs, key fingerprint, metadata signature/checksums and RPM digests as
safe provenance evidence. The official repo sets `repo_gpgcheck=1` and
`gpgcheck=0`; per-RPM GPG signatures are not claimed or required by this
owner-approved trust path. A package whose digest cannot be traced through
the signed metadata is rejected, even when its filename matches. Also check
redistribution terms. Record the verified
digests in `services/clickhouse/artifacts.yml` and the service manifest; never
use `latest`. DEV acquisition is explicit and allowed by this owner request;
download into ignored `.runtime/artifacts/clickhouse/`, then use the existing
builder and immutable publication path. Runtime targets never download from
the Internet. Existing repository-first/offline-second source policy remains.
Do not mutate an old release or silently update an existing project lock;
use the existing guarded CAS lock-upgrade path where required.

Package installation is host-scoped and idempotent; managed instance units,
paths and config are deployment/member-scoped. Preflight inspects existing
ClickHouse packages, stock units, owned paths, listener occupancy, disk and
memory. Do not stop an unrelated ClickHouse instance or remove foreign data.
The role creates only its owned instance resources and verifies identity
before overwriting or clearing. Running Keeper log/snapshot and ClickHouse
data survive repeat apply; repeat `changed=0` must reflect real idempotence.
The pinned server RPM enables its stock `clickhouse-server.service` as a package
side effect. After package installation, the role disables that unit only when
its unit file belongs to the exact pinned RPM and the unit is inactive. It
never stops an active stock unit; preflight continues to reject one as a
foreign-service conflict. This prevents the stock service from starting on a
later reboot alongside Installer-managed member units.
Teardown is a separate narrow, explicitly authorized, identity-checked QA
operation; no host-wide package purge.

## Plan and acceptance

Implement in bounded steps: contract/schema/fixtures; role and standalone
Ansible; immutable source acquisition/publication; 1/1 acceptance; 3/1;
3/3 plus HTTPS endpoint; full regression. New session configuration uses the
existing catalog-derived UI controls. Any complex/unsupported setting remains
read-only and writer-preserved, rather than a speculative rich editor.

For each topology: direct standalone Ansible apply/verify, target-free Core
validate/plan, Go protocol-mediated plan/approval/Start/result, and real
nonvisual React handlers -> Wails Go methods -> Execution Node. Perform a
strict second run with `changed=0`. Validate TLS handshakes and identity on
each enabled protocol, Keeper quorum and replicated table write/read in HA,
member-specific units and data paths, and an authenticated HTTPS request
through DNS/VIP/HAProxy using the session-only `default` password. Reject an
absent/wrong password and invalid upstream certificate without fallback; do
not claim process-unique TLS identity when same-host members share a hostname.
Standalone must prove no Keeper process/listener/state
was created. For 3/3, prove loss/recovery of one Keeper
and one ClickHouse member without losing committed replicated data; for 3/1,
prove independent process restart and port isolation, not host failover.
Capture plan/revision/run IDs, terminal events, per-host recaps and safe
evidence. Do not expose credentials or keys in project, plan, logs or events.
Do not alter active Vault/Kafka/Redis or other QA deployments to free ports or
space. Stop on conflicts. Run Core/full Go/vet/frontend/Wails, affected RED OS
race, catalog/schema reproducibility, secret audit and `git diff --check`
before declaring DONE. One fresh all-services plan belongs to SI10, not SI09.

## Sources and bounded decisions

- [Official ClickHouse packages](https://packages.clickhouse.com/): pinned LTS
  RPM source, standalone Keeper package and package formats.
- [Official ClickHouse TLS guide](https://clickhouse.com/docs/guides/sre/tls/configuring-tls):
  HTTPS/native/interserver secure ports, Keeper secure client and Raft settings,
  and separate Keeper OpenSSL configuration.
- Existing project contracts: `docs/project-contract.md`,
  `docs/service-install-acceptance.md`, `services/kafka/service.yml`,
  `services/vault/service.yml`, and the bundle builder.

The role must prove strict TLS verification on the pinned version rather than
copying upstream sample `verificationMode=relaxed`. If the package cannot
support required verified peer identity, stop instead of weakening TLS.
