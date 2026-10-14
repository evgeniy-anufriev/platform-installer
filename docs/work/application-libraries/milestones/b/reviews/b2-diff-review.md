# B2 — independent FULL DIFF review

2026-10-14. Independent read-only `architecture-reviewer`, agent
`/root/b2_diff_review`. **BLOCK**, **2 open blocking findings**.

Base `3fa42182892eac0583925d6f6a31b1e124ae2115`.
All 18 files in `.runtime/qa/b2/diff-identity.txt` verified before/after review.
Manifest SHA256:
`c5e7271b9ca79405071a76766cdef0ab1f280f4208090c4d03b06bcc10ba326b`.
Scope: approved B plan section10, v11 edits, local writer, import, revision/export
and existing transaction/recovery. B3/B4/UI/infrastructure execution excluded.

## B2-D01 — BLOCKING / OPEN: single override loses key context

`internal/installer/application_library_save.go:88–125`, `:360`.
SetApplicationLibraryOverride with property=environment, setting=PASSWORD and an
ordinary string passes because safeApplicationInput sees only c.Value, not the
setting key. Reducer stores the value under PASSWORD; canonical YAML can persist
plaintext. Subsequent managed read rejects this newly saved subtree.

boundedDiff emits paths/digests, so a value leak through ReviewDiff is not alleged.
The blocker is credential persistence in canonical/transaction files.

Smallest correction: key/context-aware single override check using the existing
guard, plus checking the changed library subtree before publication. Negative
slot-environment and host-parameter credential-name cases must leave canonical
bytes/revision unchanged. Ordinary overrides and runtime/Vault refs must work.

## B2-D02 — BLOCKING / OPEN: incomplete package secret checks

`internal/installer/application_package_import.go:136–177`.
Defaults receive structural secret checks; other approved files receive size and
PRIVATE KEY checks, with a special assignment/name check only for files/.env.
A manifest-listed configuration/client.conf containing a synthetic password
assignment can pass with a matching digest. validateExportPackages reuses that
incomplete check. Digest proves bytes, not their admissibility.

Impact: plaintext can enter portable package files and subsequent exports.
Smallest correction: a shared import/export closure guard rejecting literal
credential assignments across supported configuration/assets/templates, retaining
valid reference/template placeholders. Explicitly refuse a secret-bearing format
if safe support is unavailable. Add negative tests for each route, a positive
reference-template test and safe diagnostics checks.

## B2-D03 — NON_BLOCKING / OPEN: overlapping edit intents

`internal/installer/topology_save.go:128–137`.
Conflict keys catch exact addresses but not parent/child writes: deployment
applications patch plus SetApplicationLibrarySlot, or whole-slot overrides plus
leaf override. Sequential reduction makes the result order-dependent while the
contract promises overlapping-intent refusal. Atomicity remains intact.

Smallest correction: a small ancestor/descendant check for fixed command addresses,
or an explicit owner decision narrowing the promise. Test two parent/child
negatives and independent-slot positive.

## Overengineering

Unnecessary persistence/lifecycle mechanisms:0; material duplicate DTO/contracts:0;
premature B3/B4/UI scope:0; speculative frameworks/extension points:0.
PlanStore, transaction/recovery and sessions are reused. The missed simpler
mechanism is reuse of key-aware secret checks rather than partially duplicated
traversal losing context; covered by D01, no separate complexity blocker.

## Evidence and validity

Reviewer read current instructions/procedure/state, approved plan section10,
ADR040, writer contract, affected contracts, all 18 files, adjacent writer/export/
transaction functions and Save/Review UX. Tests were not independently run; Windows/
native/offline results and two baseline regression failures were parent-provided.
The five B2 tests do not cover the reported secret entry routes.

CURRENT for the frozen identity; no approval for a corrected implementation is
implied. Original files remain unchanged after report. Next action: present
D01/D02 to owner and stop automatic B2 completion. Corrections and one possible
TARGETED_RECHECK require owner authorization; no new FULL review is requested.


## Owner decision after FULL review

Owner superseded D01/D02 heuristic requirements: arbitrary user parameters,
environment and file assignments are allowed, including PASSWORD names. Original
BLOCK remains historical evidence. D03 correction accepted; targeted review
will assess corrected code against the amended contract.
