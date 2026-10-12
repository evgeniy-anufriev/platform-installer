# SI08-F — Vault endpoint with shared HA providers

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-08f-vault-endpoint-ha-checkpoint-002).



## Goal and owner decisions

Build one NEW Installer-managed 3-host HA project containing Keepalived,
HAProxy, BIND and a freshly installed Vault Raft 3/3 deployment. Before
building its plan, retire ALL existing QA Vault deployments (standalone,
HA 3/1, HA 3/3). The existing BIND, HAProxy and Keepalived providers stay
running because they serve the shared QA environment; reconcile their full
candidate graph in place without interrupting unrelated deployments. Publish a Vault
client endpoint through the existing endpoint-group, DNS, VIP and HAProxy
provider lifecycle. Each target service deployment gets its own
`30-backend-<deployment>-<group>.cfg`; HAProxy stats remain separate.

Endpoint assignment is voluntary for every service. Missing `endpointGroup`
and missing `haproxy` relation remain valid and do not cause publication or a
new validation finding. This project explicitly chooses both for Vault.
Kafka and Redis endpoint/backend policy and SI09 full-cycle execution are
outside SI08-F. For endpoint-publishable services, the canonical default
backend port setting is `configuration.port`; this does not rename settings
for services that do not expose an endpoint.

The portable project stores endpoint/provider relations and service settings,
never computed target addresses, backend files, certificate paths or secrets.
Core resolves infrastructure semantics; Go coordinates the existing
EditSession/Save/Verify/BuildDeploymentPlan/Start flow; React/Wails displays
and invokes it without computing ports or TLS identities.

## Existing contract and the two plan corrections

NET-04.2 already uses `serviceDeployment.endpointGroup` for DNS and an explicit
`serviceDeployment.haproxy.deploymentRef` plus typed `backend` for HAProxy.
Provider reconciliation rebuilds the complete graph after the source service,
including a source apply with `changed=0`. The existing PostgreSQL path and
HAProxy-owned stats path remain regression baselines, not Vault-specific code.

### HA-VAULT-PLAN-01 — canonical port and exact member targets

The current HAProxy resolver looks for `configuration.port`, then a resolved
`port`, then a single deployment-scoped catalog listener, and collapses targets
by host. Vault currently uses `apiPort`; its role assigns base + 2 times a
global member index. Both behaviors must change for this clean installation.

Rename the Vault managed setting `apiPort` to `port` in its new service package
and configuration schema. `port` defaults to 8200 and is the client API port
used by endpoint/backend resolution; `clusterPort` stays separate. Do not
introduce two simultaneous managed aliases. Existing immutable bundles and
their `apiPort` projects stay pinned to their old package; the fresh project
uses `port` only. Map the new managed `port` to the existing documented
`platform_vault_api_port` role variable so standalone manual inventory is not
silently broken merely by changing the managed key.

For endpoint-publishable services, Core defaults the backend to the resolved
effective `configuration.port`. There is no independent backend port field in
the UI and no port inferred from a service ID or label. A narrow, closed
catalog extension identifies the publishable client listener and the
host-local member allocation rule. It refers to conventional `port` rather
than an arbitrary `portSetting` name, and it is not a formula language or a
new public endpoint DTO. Unknown/ambiguous metadata fails closed.

Vault `port` may be set at deployment scope and overridden for an individual
member through existing typed configuration. Effective client port is:

1. an explicit member `port` override (exact port), if present;
2. otherwise deployment `port` or default 8200, plus 2 times the member's
   zero-based ordinal among members on that SAME host, sorted by member ID.

Thus 3/3 defaults to 8200 on every distinct host; 3/1 defaults to
8200/8202/8204. Core creates one private target per canonical
deployment/member identity and never deduplicates members by host. The
private execution projection conveys the exact member ports to the role;
standalone Ansible with manual inventory computes the same defaults. Resolve
the separate cluster listener consistently, and reject duplicate identity,
missing/invalid ports, overflow, same-host API/API and API/cluster collisions
before service mutation. No Vault-specific branch belongs in Go, React or the
generic HAProxy resolver.

### HA-VAULT-PLAN-02 — backend TLS identity

`sslVerify: required` remains the HA backend policy. Do not add `skip_verify`,
`sslVerify: none`, a raw certificate path or a plaintext/key reference to this
Vault project. The existing HAProxy PKI trust chain supplies `ca-file`.

For the currently deployment-scoped shared Vault leaf, target-free Core
selects the resolved Vault endpoint FQDN as the expected backend certificate
name only when the current PKI request projection includes that DNS name.
The runtime PKI materialization/verify gate must then prove that the actual
serving leaf has the required SAN before HAProxy candidate activation; a
target-free request alone is not evidence of the bytes on each target.
The same expected service name is valid for all three
members because they intentionally share that deployment-scoped leaf; this
does not claim three independent per-host private-key identities. If the
identity is unavailable, stale or lacks the name, block publication and use
the existing PKI reissue path; do not bypass `CERTIFICATE_REISSUE_REQUIRED`.
The generic HAProxy target projection carries the validated expected name,
and the generic template renders `verifyhost` for each TLS target. Health
checks must use the same verification. No path from a project/UI field is
accepted. A wrong-name certificate must fail the actual TLS connection.

## Clean-state prerequisite and provider graph

- Reuse the existing endpoint group, BIND/HAProxy provider relations and
  Keepalived VIP ownership. Do not invent a second endpoint/backend registry.
- Before touching targets, inventory exact QA project identities/revisions,
  service deployment IDs, active units/listeners, Vault data paths, provider
  fragments, VIPs, DNS zones and generated state on all three hosts. Build an
  explicit allow-list of owned objects to clear and a deny-list of unrelated
  deployments. All QA Vault standalone/HA 3/1/HA 3/3 are in scope; unrelated
  Kafka, Redis and PostgreSQL installations are not.
- Derive every old Vault member's exact unit name, config/data/log directories
  and logrotate entry from the SAME normalization/provisioning logic of that
  member's pinned package (`deploymentId`, `memberId`, configured roots). Do
  not reconstruct names with an independent script, broad glob or current
  package if the old package differs. Compare each derived identity with the
  installed unit content and the existing member ownership marker before any
  retirement. The old package's `clear` first validates, stops/disables and
  clears Raft for each exact member; it does NOT uninstall units or config.
  After that, a narrow retirement step removes each verified old unit from
  active systemd by archiving its exact unit file and exact logrotate entry,
  and archives the exact member config/data/log paths into a restricted,
  non-active QA archive. Preserve file bytes; do not delete configuration
  files. Reload systemd and prove the retired units cannot restart, no old
  listener remains, and no old path can be reused by the fresh project. Move
  only proven owned paths, with no-follow/identity-safe admission and an
  explicit stop on substitution, shared path, mount or ownership uncertainty.
  Do not move a broad deployment/service root or any unrelated member path.
  The old standalone release has no `clear` entry. Owner-approved exception:
  use the byte-identical `clear_member.py` from the later pinned Vault release
  only for that standalone member, after read-only `inspect_only` proves its
  old marker, unit and config match; all unit/path identities still derive
  from the installed old package. Preserve run journals and encrypted Installer custody files separately;
  do not reuse old Vault bootstrap material for the new project.
  The narrow QA retirement tool now requires an explicit pinned release root
  for each allow-listed member. It checks the exact old defaults,
  normalization, provisioning and unit/logrotate template component hashes,
  derives deployment and roots from those verified defaults, then loads the
  clear module from the same verified package bytes. Only `vault-1` may use
  the explicitly supplied later compatible clear release. A target lacking
  the old pinned package copy blocks before retirement; a current checkout is
  not silently substituted. The three variants are pinned to releases
  `d84df0dc...`, `c6a54fca...` and `fd434131...` respectively.
- Do not stop or uninstall shared BIND, HAProxy or Keepalived on the QA nodes:
  the configured resolver uses all three BIND addresses, and live unrelated
  services depend on the shared network plane. Validate the complete new
  provider candidate before in-place reconciliation. Never erase broad service
  roots, project roots or neighboring QA data. Prove unrelated units, DNS and
  VIP state remain available before and after the new installation.
- HAProxy `.cfg` files are NEVER deleted by this stage. Replace the current
  `30-backend-*.cfg` wildcard deletion in activation: before any active
  config copy, compare existing files with the exact prior Platform-owned
  backend inventory and the new candidate set. Archive only positively owned
  stale backend `.cfg` files outside active `conf.d`, preserving their bytes,
  owner/mode and recoverable source identity. An unproven same-pattern file
  stays untouched and BLOCKS activation before mutation; a filename pattern
  alone is not ownership proof. If archival, candidate validation or
  activation fails, restore the prior active set from the archived bytes or
  stop in an explicit recoverable state; never silently leave a mixed graph.
  Keep the existing candidate/active graph digest equivalence check. Test
  owned-stale archival and unowned-file blocking, including failure recovery.
  The prior exact Platform-owned backend inventory is captured BEFORE the old
  `.platform-candidate` is reset. Admission compares the complete retained
  prior candidate main/config fragments byte-for-byte with the active graph
  through no-follow regular-file handles, then carries only exact backend
  names and SHA-256 digests into activation. The archive step requires those
  digests to match the same active files. A new ownership header alone is not
  proof; an old headerless fragment is admissible only with this matching
  prior candidate. Missing, stale or differing prior evidence blocks a host
  with old backend fragments without deleting or rewriting them.
- Create a NEW canonical project ID with a fresh pinned verified immutable
  release. Its generated state must not inherit an old project/run identity.
  Use the existing managed editor/writer and guarded Save. Resolve every
  service from the pinned catalog; if catalog/bundle
  compatibility or PKI reissue blocks, stop on the concrete finding.
- Resolve and validate the full backend graph before provider mutation. The
  Vault backend file must contain exactly three member targets. Old owned
  fragments are archived, never deleted; third-party fragments remain
  untouched and block if they collide with the active graph.
- A TCP-only check is not sufficient evidence of a usable Vault HA endpoint.
  Test real API traffic through DNS/VIP before and after leader change and
  node loss. If standby routing/redirects fail the endpoint contract, stop
  and design a narrow catalog-declared active-only health check; do not add
  a Vault branch to HAProxy or silently accept a socket-only result.

## Acceptance sequence and QA matrix

1. Clean-state gate: exact owned QA Vault objects retired, including all three old
   Vault QA variants; shared providers and unrelated active deployments remain
   available. Record bounded
   before/after units, ports, VIPs, DNS, backend files and ownership proof.
   Check exact Vault identities derived by the old package, clear then archive
   unit/logrotate/member paths, systemd reload and no restart; no `.cfg`
   deletion. Prove owned HAProxy stale fragment archived and unowned
   same-pattern fragment preserved with fail-closed activation.
2. Target-free Core: absent Vault endpoint/relation remains valid; explicit
   relation resolves exact endpoint, DNS and three member targets. Verify
   new `port` default/mapping and no `apiPort` alias, old pinned package
   compatibility, 3/3 equal-port, 3/1 distinct-port, explicit member override,
   role/Core parity, collision/overflow, missing metadata and fingerprint.
3. TLS: correct current SAN and CA succeed; wrong name, wrong CA, missing SAN,
   stale evidence and required reissue block. Confirm `verifyhost` is used by
   connections and checks, never `verify none`.
4. Regression: PostgreSQL backend resolution and one-file-per-deployment
   behavior, HAProxy stats isolation, BIND full-model reconciliation,
   Keepalived VIP ownership, Vault 1/1 and 3/1 role behavior, standalone
   Ansible with manual inventory, catalog/schema reproducibility.
5. Environment: on RED OS, preflight exact three hosts and provider state;
   use the supported immutable release path, not mutation of an existing
   release. Prepare the same saved project incrementally through the real
   React/Wails binding, not a mock or a separate save/start path. The new
   project must not be an edit of the prior Vault QA project.
6. Fresh current-revision Verify and BuildDeploymentPlan, approval, one real
   plan/Start, task stream and terminal result. Prove PKI/apply/verify PASS,
   three active Vault units, exact HAProxy backend and native `haproxy -c`,
   DNS/VIP TLS reachability, authenticated Vault operation, leader failover,
   and no contact with unrelated deployment units.
7. Fresh repeat plan/Start must finish normally with `changed=0` for the
   unchanged project. Capture plan/run IDs, durations, task counts, digests,
   active units, safe event evidence and provider state. Execute affected Core
   and service suites, Go/frontend/Wails gates where touched, relevant RED OS
   race tests, secret audit and `git diff --check`.

The plan alone did not authorize execution. The subsequent owner-approved
implementation and real acceptance evidence are recorded below. SI09 is not
started automatically.

## Acceptance evidence (2026-09-29)

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-08f-vault-endpoint-ha-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
