# A1 implementation and acceptance journal

Scope authorized 2026-10-10: standalone schemas, read-only Ansible/Core resolution,
fixtures and compatibility. Branch `codex/application-libraries`, base `d7c3a3a`.
No real infrastructure Apply, Docker/Vault mutation, bundle build or UI changes.

## Implemented boundary

- Desired-state v3alpha1 selected explicitly by ordinary group var; infrastructure
  schemas stay v2alpha1. Library output uses ProjectSnapshot v2alpha1, rejected
  by the existing execution planner until A7. Old snapshots remain v1alpha1.
- Exact local package refs, file allowlist, bounded sizes, path/symlink checks,
  namespace/schema checks and content digest. Package files including library
  `.env` participate in the existing project revision mechanism.
- Built-in Ansible include_vars/combine resolves independent library/app/host
  contexts. Generic structured snapshot consumes the same resolved rows as
  validation. No independent Python precedence or Jinja evaluation.
- IDs derive application name + library ID; SERVER_ID derives host ID. Paths and
  Compose/container identity include project namespace. Shared `.env` is described,
  not materialized. Agent, accounts and image delivery are requirements, not actions.
- ServiceType connection defaults and existing effective client ports/listeners;
  no manual port copy from service manifest. Missing provider refs skip unused
  connections; declared account/resource dependencies still validate.

## Evidence

Execution Node: RED OS `192.168.56.101`, platform-automation, established persistent
SSH identity with IdentitiesOnly. Source transferred with scripts/qa-sync.ps1.
All Ansible tasks execute only on localhost with gather_facts false. Fixture target
addresses use TEST-NET. Temporary source copies are removed after final QA.

Initial focused suite: 10 tests PASS. Initial real standalone suite: 7 tests PASS
(two libraries/three placements, parameter/credential identity isolation, repeat
fingerprint, infrastructure-only without packages, no accounts/no Agent, missing
unused provider ref, port collision, missing Kafka selector, secret-safe rejection).
Final regression and FULL DIFF verdict are recorded below when completed.

Final FULL DIFF: **BLOCK**, findings A1-D01–03 and nonblocking A1-D04; see
[report](a1-diff-review.md). The owner explicitly requested stop after recording
the report; no corrections or TARGETED_RECHECK performed.

Final Core regression was stopped on owner instruction before its summary;
two errors had appeared in progress. It is **INCOMPLETE**, not PASS. The chained
final standalone 8-case suite did not start. Earlier focused 10/standalone 7 PASS
refer to intermediate source copies and do not establish final acceptance.
Only the identified A1 QA shell and descendant processes were terminated after
checking its exact workspace and owner. Temporary QA source workspaces are cleaned
with qa-sync. No infrastructure service or unrelated process was stopped.

## Deliberate limits and execution prerequisites

- Multiple Redis members and multiple ClickHouse members on one host require
  a provider-owned allocated-port projection not currently available in the
  generic read-only configuration. These cases block rather than guessing ports;
  connecting provider normalization belongs to later stages before their Apply.
- Kafka account/ACL creation is unsupported; the fixture uses SSL client listener
  without SASL. Real application provisioning, RoleID delivery, NAT-aware CIDRs,
  TLS materialization and Agent re-auth are A3/A4/A5 work, not proven by A1.
- Source `.env` supports blank/comment lines and KEY=value assignments, preserving
  source bytes for future materialization. Duplicate keys, SERVER_ID and named
  credential keys are rejected. No shell execution or dotenv expansion in A1.
- Image tag is a QA requirement only; immutable platform/image/archive locking
  and delivery are A2.1. No image rebuild or registry access occurred.
- PostgreSQL CSPА infrastructure admin credential is intentionally absent from
  the read-only fixture: the existing infrastructure runtime requirement collector
  rejects duplicate package requirement IDs across two PostgreSQL deployments.
  A1 neither changes that collector nor claims this fixture is ready to execute.
- Package templates/defaults are trusted operator-authored Ansible/Jinja code;
  fingerprints identify exact bytes but are not a signature or sandbox.

Overall status and owner gates remain in CURRENT_STATE.md.

Owner subsequently authorized only A1-D03: PostgreSQL connection targets now
filter member roles to database; monitor-only input fails closed. Focused RED OS
tests for HA database-only selection and standalone member port override: 2 PASS.
Source transferred/cleaned using qa-sync; no target contacts or recheck performed.
At that point A1-D01 and A1-D02 remained uncorrected.

The owner subsequently accepted A1-D01. Checks now cover resource parameters,
account grants and endpoint settings, including the final public projection.
RED OS focused boundary test: 1 PASS. Standalone secret-marker test (three
subcases) and valid multi-host/parameter-isolation test: 2 PASS. Markers were
absent from the public snapshot; invalid projections were blocked. Runtime
references and the valid scenario remained supported. The qa-sync workspace
was cleaned. No target writes or independent recheck occurred. A1-D02 remains
under clarification; the overall BLOCK verdict is unchanged.

Owner accepted A1-D02 correction, including mixed account/shared bindings and
shared-only without accounts. Source schema is exclusive and complete; Agent
and AppRole demand derives from secret_bindings, independently of account hooks.
RED OS current-source workspace ba95d36b2fe94b88aaf07bb11ebbae17: one focused
schema test (seven cases) PASS; six standalone tests PASS in 30.708 seconds.
Cases: mixed sources/multi-host isolation, shared-only, no secrets, ambiguous
source, unknown shared secret, missing Vault reference. Read-only snapshots only;
no infrastructure writes. qa-sync cleanup follows the run. Independent recheck
has not been authorized or performed; overall FULL BLOCK remains unchanged.

Owner subsequently requested the single TARGETED_RECHECK. Independent reviewer
returned APPROVE_WITH_CHANGES on fingerprint
A9B3A5D6CBB8707BD79786F7F077323CFCC44BA637139C7E28BD889012AA9922
(51 files). A1-D01–03 RESOLVED; zero blocking findings; A1-D04 nonblocking/open.
Reviewer inspected code and test evidence without running QA or contacting
targets. Broad regression remains INCOMPLETE; review does not close A1 acceptance.
The FULL plus TARGETED_RECHECK budget is consumed. See a1-diff-review.md for
scope, exact revision identity, evidence and limits.

## Final A1 continuation QA — 2026-10-10

Owner requested continued A1 work. A1-D04 corrected with explicit Compose grammar
validation; invalid IDs are rejected without sanitization. The Kafka invalid-selector
test now supplies the valid host fixture so it exercises selector rejection rather
than failing early on unrelated missing host data. No provider behavior changed.
The outdated shared-only negative row in the technical plan was synchronized.

Current-source qa-sync workspace: 15bb382e8e5441c2a2ad271fe226710d.
`qa-sync -Verify` confirmed source identity after the standalone run.
Focused application suite: 15 PASS (0.520 seconds).
Full real standalone application suite: 14 PASS (151.347 seconds).
Full Core regression: 517 tests in 1492.031 seconds; 491 passed, 19 skipped,
six PKI playbook timeouts (90-second harness limit) and one Redis consumer
fixture failure (missing ACL-task change-result variables). This run is FAILED,
not PASS. The old source workspace was cleaned with qa-sync after completion.
The affected PKI/Redis test and production role files were unchanged by A1.
Test-only corrections: playbook timeout 180 seconds and explicit unchanged ACL
task results in the Redis/Sentinel consumer fixture. No production PKI/Redis code
changed. Seven failed cases were rerun from qa-sync workspace
161efc51412c48269de312d57bd38a0e: **7 PASS**, 2152.213 seconds. This closes the
seven failures from the broad run; it does not replace its original FAILED
summary with a claim that the whole suite was rerun. Combined evidence covers
498 passing cases and 19 skips. Skips belong to existing root-dependent/isolated
execution acceptance, outside target-free A1; A1-specific suites had no skips.
`qa-sync -Verify` confirmed current-source identity before standard cleanup;
both final QA workspaces were removed. Passed cases were not rerun without cause.
No A2, target mutation, UI, bundle build or third architecture review occurred.

## A1 acceptance

**PASS / complete** for standalone versioned contracts, native Ansible read-only
resolution, safe snapshot/validation, library/app identity, shared/account secret
descriptors, multi-host placement, package closure/revision and infrastructure-only
compatibility. Architecture blockers A1-D01–03 were independently resolved;
nonblocking A1-D04 was corrected and tested. No required A1 QA failure remains.

QA base/HEAD before the implementation commit: d7c3a3a7191e3d6eac826521c3135c664a828633. Final tested source
fingerprint for 40 modified/new files under ansible-core/, contracts/, examples/:
`F3AF220AC7B13480ACDA393A80A1E6FAEDC3C5F07EB26CF8C56304D926DFCDF9`.
Rows are sorted unique relative paths plus space and uppercase file SHA256,
LF-joined UTF-8 without final newline. Documentation/state are excluded from this
source fingerprint; independent review identity is preserved separately above.
Implementation is maintained on branch codex/application-libraries.
Execution prerequisites listed earlier remain later-stage work, not implemented
application installation. A2 and Go/UI work require the next owner request.
