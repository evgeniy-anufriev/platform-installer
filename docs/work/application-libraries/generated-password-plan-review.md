# Generated passwords — independent PLAN review, revision 2

Current verdict: **APPROVE** after TARGETED_RECHECK of AGP-P03.
Unresolved blocking findings: **0**. Original FULL PLAN verdict below is historical.
Reviewer: independent architecture-reviewer agent generated_password_plan_review.
No implementation, tests, target operations or secret inspection performed.

Reviewed baseline: `e2b965b4256e22185a4652ef0fb133444a228fd1`.
Plan: `generated-password-plan.md`, SHA256
`DAD018764E7ADBEBE7380E89BFF79CBF73363B953C61E053A30D2C20F2820F06`.
Review validity: CURRENT for that exact revision. This file records the returned
report's findings and evidence; it is not an approval or implementation record.

## AGP-P03 — BLOCKING, OPEN

Concurrent first Applies of the same generated descriptor can select A and B.
After provider A/login, provider B/login, Vault B publication, the first Apply's
generic Vault CAS retry can overwrite the document with A. The provider then
uses B while Vault/Agent receive A. Existing provider locks do not cover final
Vault publication, and CAS alone does not couple provider and Vault credentials.
The plan's exclusion of conflicting manual passwords does not exclude this
same-descriptor generated case.

Smallest correction: obtain an explicit owner decision and establish one Apply
for a project across the entire selection/provider/publication interval, including
standalone and multiple Execution Nodes. If concurrent execution must work,
define concrete coordination rather than claim existing locks/CAS suffice.
Do not automatically introduce a universal coordination subsystem.

Required evidence: reproduce the interleaving or prove an enforced execution
restriction excludes it. Conflicting values must not be reported as a successful
consistent result. Single-writer exclusion is not yet owner-approved.

## AGP-P04 — NON_BLOCKING, OPEN

Limit retry-convergence claims to already confirmed managed ownership and
completed provider hooks. Redis account creation/ACL SAVE occurs before witness
publication; ClickHouse account SQL also precedes witness publication. A crash
inside that initial interval still fails closed on the existing ownership guard.
Password replacement alone does not recover missing ownership evidence.

Smallest correction: document that boundary; do not add recovery tooling.
Required evidence: distinguish failures after a complete hook from failures
inside first creation. The latter must remain safely blocked.

## Previous review findings

AGP-P01 and AGP-P02: OPEN -> SUPERSEDED. They concerned early Vault publication
in revision 1, removed by the owner's changed password-reconciliation instruction.
Revision 1 review remains STALE; this is not a correction of an implementation.

## Mandatory overengineering result

Zero blocking overengineering findings. No new DTO/API, standalone persistence
system, speculative feature or generic framework is proposed. Existing private
action, standard secrets, runtime files, bindings and transport suffice. A
single-writer restriction is the smaller alternative to new coordination, at the
cost of unsupported concurrent Applies. No Kafka witness store is proposed.

Kafka authority change is explicitly exposed: a managed application declaration
plus existing admin credentials replaces password-possession proof when setting
an unknown password. Concrete-plan owner approval remains required.

## Evidence and limitations

Reviewer directly checked fingerprint/HEAD, full replacement proposal, PostgreSQL
login/preflight/account SQL, Redis locks/ACL/witness, ClickHouse ownership/UUID/
account SQL/witness, Kafka adoption/login, provider-to-Vault ordering and generic
CAS retry. Previously inspected unchanged contracts, scoped instructions, UI
design and Verify flow were reused. No tests or actual acceptance were performed.
No Verify functionality is requested by this plan.

Next action: return AGP-P03 and AGP-P04 to the owner, obtain concurrency and
authority decisions. No automatic redesign or FULL re-review loop.

## Owner decision and targeted recheck, 2026-10-21

Owner clarified that two simultaneous installations are not expected after the
question explicitly covered standalone and different Execution Nodes. Supported
scope is one project Apply at a time over selection -> provider -> publication;
operator/caller serialization is required. There is no new enforced lock and no
claim of concurrent safety.

Independent reviewer returned **APPROVE**, PLAN/TARGETED_RECHECK, for AGP-P03 only.
Reviewed HEAD remained `e2b965b4256e22185a4652ef0fb133444a228fd1`; corrected plan
SHA256 `7E0BD519C6D210FE28977D5DA3C04089CD3F61429C00EDEE0D509221CE010DCB`.
AGP-P03: OPEN -> OWNER_ACCEPTED as an explicit supported-execution restriction,
not a technical fix of the unsupported concurrent algorithm. Zero unresolved
blocking findings. Recheck validity: CURRENT within that scope. No new mechanism,
DTO, store or coordination was added; no production code or tests were run.

AGP-P04 stays nonblocking and was not separately re-reviewed. The plan bounds
retry claims to confirmed ownership/completed hooks. AGP-P01/P02 stay SUPERSEDED.
Preserve serialization in implementation/docs and verify sequential retry after
provider success before publication. Concrete-plan owner approval is the next
gate; no additional automatic review is required.

## Owner clarification received during review

Only application passwords may be reconciled. Infrastructure user passwords,
including Kafka admin, are excluded. Existing infrastructure admin/default/
superuser/Vault credentials are consumed only as administrative authority and
must never be changed by this feature. This clarifies the proposal's existing
reserved-name/admin checks; no plan file was modified during review.

## Owner-approved path amendment review

After explicit implementation approval, the owner required KV paths and every
Agent secret reference without project ID, e.g. secret/data/sdku-dm/shared.
Independent FULL PLAN review of this new scope returned APPROVE_WITH_CHANGES,
zero blockers, at SHA256
`5595F0668883EE6E33D5005BDEC084708073BD9B261CCDFBC22374823A3A2460`,
baseline unchanged. Original generation/concurrency decisions were not reopened.

AGP-P05 NON_BLOCKING OPEN: document that an old generated value at a legacy
project-prefixed location is not implicitly recovered; selecting a new value
at the new path may also change the application password. That bounded
clarification was added without a new review loop. Preserve old documents,
foreign-owner refusal and authored external vault_ref paths. Native tests now
cover unchanged legacy data, foreign collision before provider mutation and
actual Agent config references. Final FULL DIFF review still covers the code.
