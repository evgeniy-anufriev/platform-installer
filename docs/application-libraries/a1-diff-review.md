# A1 — independent FULL DIFF review

Current disposition after the owner-approved TARGETED_RECHECK on 2026-10-10:
**APPROVE_WITH_CHANGES**, A1-D01–03 **RESOLVED**, zero blocking findings.
A1-D04 was subsequently corrected and tested under owner-authorized A1 continuation
(see final QA journal); it was not independently re-reviewed. The initial FULL verdict below is historical;
review does not close incomplete QA or authorize A2.

Date: 2026-10-10. Verdict: **BLOCK**. Independent architecture-reviewer, using
ansible-core-review. Base d7c3a3a7191e3d6eac826521c3135c664a828633;
branch codex/application-libraries, managed application-libraries worktree.
Reviewed 46 modified/new files; independently reproduced content fingerprint:
`B82686292BAD52EF3B60F477648223BFE674C9388A68C13ABE2C08850B0A86FE`.

## A1-D01 — BLOCKING / OPEN: secret-safe output boundary

`application_libraries.project` checks parameters/environment/command and literal
password descriptors, but publishes unrestricted resources.parameters,
accounts.grants and endpoint.haproxy. The new applicationLibraries field is added
after the existing snapshot redaction boundary. Credential-like values in these
fields can therefore reach public snapshot output.

Evidence: application_libraries.py lines 268, 342, 345, 359 and action
project_snapshot.py line 470 at the reviewed revision.

Smallest correction: validate all free nonsecret areas before publication; invalid
inputs produce safe BLOCKED findings and empty libraries. Add final output defence
without losing allowed secret descriptors/refs. Test synthetic secret markers in
resource parameters, grants and endpoint backend: no marker in any public output.

## A1-D02 — BLOCKING / OPEN: ambiguous secret binding

settings.schema.json source permits an empty object, account without field, and
account plus library_secret together. Projection does not require one source.

Evidence: settings.schema.json lines 318–337; application_libraries.py line 324.

Smallest correction: oneOf closed {account, field} and {library_secret} variants,
required fields and additionalProperties:false; retain semantic reference checks.
Schema/standalone tests cover empty, incomplete and dual sources plus valid cases.

## A1-D03 — BLOCKING / OPEN: PostgreSQL monitor in client targets

The non-Kafka resolver includes every member. pg_auto_failover contains monitor
and database members, and monitor must not become an application database endpoint.

Evidence: application_libraries.py lines 236–251; PostgreSQL service manifest
lines 19–29.

Smallest correction: filter database member roles using existing metadata, or
explicitly block unsupported HA connection projection. Test monitor plus two
database members; monitor must be absent or the unsupported mode must be BLOCKED.

## A1-D04 — NON_BLOCKING / OPEN: Compose project name

The general ID grammar permits dots while Compose project names do not. Check
the derived name against Compose grammar and reject without silent sanitization.
Evidence: application_libraries.py lines 259, 361. Add dotted/ordinary ID tests.

## Scope and disposition

No proven blocking overengineering findings. Existing Ansible built-ins and Core
revision/schema mechanisms are reused; no new persistence, Python precedence
engine, package manager, Go/UI resolver, target mutation or A2 implementation.
Reviewer did not run QA or inspect runtime credentials/target hosts.

Owner selected **stop after recording the report**. No corrective source edits
or TARGETED_RECHECK are authorized/performed. Three blocking findings remain.
Any continuation requires owner authorization for corrections; one owner-approved
TARGETED_RECHECK may inspect A1-D01–03 under the existing review procedure.
Later factual journal/status/report changes do not correct or supersede this verdict.

## Owner-directed A1-D03 correction

After the stop, the owner requested PostgreSQL targets include only database
members. This bounded correction is implemented: non-database roles are excluded;
a monitor-only deployment fails with no connection targets. RED OS focused HA and
standalone/member-port tests: 2 PASS. A1-D03 awaits independent recheck and is not
formally closed. At that point A1-D01/A1-D02 remained unchanged.

## Owner-directed A1-D01 correction

The owner subsequently accepted A1-D01. Secret-like values are now rejected in
resources.parameters, accounts.grants and endpoint settings, with an additional
check at the public application projection boundary. Typed credential references
remain supported. RED OS: one focused boundary test and two standalone tests PASS
(three secret-marker subcases plus the valid multi-host scenario). Source was
transferred and cleaned with qa-sync; no infrastructure writes occurred.
A1-D01 and A1-D03 await independent recheck. A1-D02 remains under clarification;
no TARGETED_RECHECK has been authorized or started. The FULL BLOCK verdict stands.

## Owner-directed A1-D02 correction

The owner accepted exclusive sources per binding, simultaneous account/shared
bindings and shared-only applications. Source schema now requires exactly
account+field or library_secret. Agent/AppRole requirements depend on nonempty
secret_bindings; account hooks remain conditional on accounts. Shared-only
applications require a Vault reference and a valid library secret.
RED OS: one schema test with seven source cases and six standalone tests PASS
(mixed sources, shared-only, no secrets, ambiguous source, unknown shared secret,
missing Vault reference). No infrastructure writes or independent recheck.
A1-D01–03 corrections await independent recheck; FULL BLOCK remains in force.

## Independent TARGETED_RECHECK — 2026-10-10

Owner explicitly requested the recheck. Independent architecture-reviewer
`/root/a1_targeted_recheck`, using ansible-core-review, inspected only A1-D01–03
and the immediately affected schema/publication/resolution boundaries.
Verdict: **APPROVE_WITH_CHANGES**. Zero unresolved blocking findings.

Base/HEAD: `d7c3a3a7191e3d6eac826521c3135c664a828633`, branch
`codex/application-libraries`, managed application-libraries worktree.
51 modified/new files; fingerprint independently reproduced before and after:
`A9B3A5D6CBB8707BD79786F7F077323CFCC44BA637139C7E28BD889012AA9922`.
Identity uses sorted unique git modified/untracked paths, rows of relative path,
space, uppercase SHA256, LF-joined UTF-8 without a final newline. This record
changes documentation bytes; the fingerprint identifies the reviewed source
before recording this result.

- A1-D01 **RESOLVED**: free resource parameters, account grants and endpoint
  settings checked; final publication defence preserves typed references and
  blocks/clears invalid projections. Evidence: application_libraries.py:271–281,
  379; action project_snapshot.py:463; secret-marker and valid-reference tests.
- A1-D02 **RESOLVED**: exclusive complete source variants, semantic reference
  checks, mixed/shared-only support; bindings control Agent/AppRole demand.
  Evidence: settings.schema.json:319–344; application_libraries.py:275–278,
  329–334,350–360; qa_application_libraries.py:94.
- A1-D03 **RESOLVED**: database-only PostgreSQL client targets; monitors excluded,
  monitor-only input blocked. Evidence: application_libraries.py:237;
  test_application_libraries.py:128; PostgreSQL service metadata database roles.
- A1-D04 **NON_BLOCKING / OPEN**: retained from FULL review, outside recheck scope.

Overengineering: zero findings; existing schema validation, metadata and small
explicit checks reused. Reviewer read test code/evidence but did not execute QA,
inspect runtime credentials or contact targets. Overall regression remains
INCOMPLETE; no installation acceptance, A2, Go/UI or provider writes reviewed.
Review budget consumed: one FULL plus one owner-approved TARGETED_RECHECK.
No additional automatic review cycle is authorized.

## Subsequent nonblocking A1-D04 correction

Owner requested continued A1 work. Derived Compose project names now validate
against `^[a-z0-9][a-z0-9_-]*$`, returning a safe
APPLICATION_COMPOSE_PROJECT_INVALID finding without normalizing IDs.
Focused tests cover dots in project/library/instance/host components; standalone
tests cover the dotted project root and unchanged valid identity. Correction
verified in 15 focused and 14 standalone RED OS tests. A1-D04 implementation is
resolved; no additional independent review was run. This bounded correction is
outside the previous D01–03 recheck scope and does not reopen that review budget.
