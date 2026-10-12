# Architecture targeted recheck — UI-01I

## 1. Verdict

**APPROVE — PLAN / TARGETED_RECHECK — UI-01I**

The verdict was formed independently. The recheck covered only
`UI01I-ARCH-001`, `UI01I-ARCH-002`, `UI01I-ARCH-003` and their immediately
affected filesystem/lifecycle boundary. The FULL review was not repeated and
no unrelated architecture questions were opened.

## 2. Review identity

- Plan: `docs/work/ui-01/ui-01i-architecture.md`
- Verified plan SHA-256:
  `4800D5D1C158DB261439FB32B7E46E0836C660D5CF9241F2B74A34CA10C7127D`
- Base/HEAD: `82fcb2ecc4013597271e15fabdf357d83d0eed32`
- Historical FULL review: `docs/work/ui-01/reviews/ui-01i-architecture-review.md`
- Historical review SHA-256:
  `6414A0B0F1B8BBCAE6D62650E468B679ED9F7C794E2E23A245ECBA2FDBCDDF81`
- Scope: retained filesystem identities, handle-relative source observation
  and destination publication, cleanup, and synchronous commit blocking with
  no user interruption API.

## 3. Finding lifecycle

### UI01I-ARCH-001 — BLOCKING / OPEN → RESOLVED

The active in-memory capability retains one no-follow identity-bound source-
root handle. Both preview observations and commit revalidation execute relative
to that same handle. Revision is computed from bytes read through those opened
objects; the source string path is display metadata only.

Implementation must still prove races involving replacement of the root,
intermediate directories and files, O0/O1 drift, absence of mixed manifests,
and no publication after failed revalidation.

### UI01I-ARCH-002 — BLOCKING / OPEN → RESOLVED

The plan retains one identity-bound destination-parent handle. Staging
creation, descendant writes, leaf-absence check, cleanup and atomic no-replace
publication all execute relative to it. Reopening the parent string path as
authority is forbidden; an unsupported platform fails closed.

Implementation must still prove parent/ancestor replacement races,
destination races, no-replace semantics, identity-bound cleanup, Windows
reparse safety and POSIX symlink safety.

### UI01I-ARCH-003 — BLOCKING / OPEN → RESOLVED

User interruption after Export confirmation is removed. Commit runs
synchronously to success or failure, conflicting lifecycle operations remain
blocked, failures before publication clean only owned staging, and successful
atomic publication is the commit point. No background-operation or
interruption framework is introduced.

Implementation must still prove lifecycle exclusion during commit,
pre-publication cleanup and absence of rollback after publication.

## 4. Accepted nonblocking clarifications

- Go owns a dedicated narrow export-directory leaf validator; React validation
  is convenience only.
- Acceptance compares source and exported normalized portable Core semantic
  projections/fingerprints under the same target-free Core/catalog/runtime
  identity. This is evidence after export, not a transaction dependency.

## 5. Mandatory overengineering review

Overengineering findings: **0**.

- One bounded in-memory capability is required to retain the two filesystem
  authorities; a path-only implementation cannot close the TOCTOU boundary.
- No duplicate public contract or persistence layer is introduced.
- Archive/import/templates/overwrite/migration remain excluded.
- The proposed source/destination primitives are narrow platform seams, not a
  generic secure-filesystem framework.
- Removing interruption avoids a background-operation framework that is not
  required by UI-01I.

## 6. Evidence and limitations

The reviewer directly inspected the exact plan/review documents, repository
instructions, current `ProjectRevision`/`copyProject`, F1 POSIX/Windows opened-
object readers, Linux/Windows publication seams, project creation and App
lifecycle locking.

Read-only checks confirmed:

- current plan SHA-256 and HEAD;
- declared worktree state;
- `git diff --check` PASS; and
- zero `cancel`/cancellation tokens in the corrected plan.

No product, OS or UI tests were run because this was a documentation PLAN
recheck and no UI-01I implementation exists. No hosts were contacted and no
secret material was read.

## 7. Review validity

**CURRENT** for plan SHA-256
`4800D5D1C158DB261439FB32B7E46E0836C660D5CF9241F2B74A34CA10C7127D`, HEAD
`82fcb2ecc4013597271e15fabdf357d83d0eed32`, the supplied owner corrections and
the directly affected filesystem/application seams.

The review becomes stale if the plan bytes, owner decisions, source/destination
identity model, transaction/cleanup or lifecycle-interruption boundary changes.
Implementation remains subject to the separate planned FULL DIFF gate.

## 8. Result

- `UI01I-ARCH-001`: **RESOLVED**
- `UI01I-ARCH-002`: **RESOLVED**
- `UI01I-ARCH-003`: **RESOLVED**
- unresolved blocking findings: **0**

This technical approval does not itself authorize UI-01I implementation.
