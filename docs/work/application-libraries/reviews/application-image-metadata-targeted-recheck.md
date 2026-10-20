# APPLICATION-IMAGE-METADATA-01 — TARGETED_RECHECK

2026-10-20. Independent read-only reviewer. **APPROVE**, exclusively for
owner-approved AIM-D02, AIM-D04 and AIM-D05 corrections. No new blocking
regression was found in their immediately affected boundaries.

## Identity

Checkout: `C:\Users\AnufrievEV\.codex\worktrees\application-image-metadata\platform-installer-v2`.
Base HEAD: `930d5f71a83e3be99901ea40e2af6464394526f5`.

- Targeted manifest: `7AE2B734EA276DBF81E73775625844D1894464A5FFE47C93D1F353379EC5EA79`.
- Targeted diff: `0C3873D1F940014E9F11ECA2E4A92E616F9AE3B0AC396CA6F3534C405B11BADE`.
- Acceptance summary: `8A58B8E902A38A4635D47997D481ADE48FD806107D42319ABA00221A560F19CA`.

All 82 current files matched the manifest before and after review. Scope:
D02/D04 corrections, D05 evidence, required Broker promotion correction and its
immediate secret boundary. Inherited SDKU work was excluded.

## Finding lifecycle

**AIM-D02 — BLOCKING, OPEN → RESOLVED.**
`ansible-core/playbooks/application-images-prepare.yml:7`: redundant secret map
assignment was removed from add_host. Private global extra-vars retain required
value propagation. New native success/failure tests with -vvv assert absence
of sentinel credentials/token/Basic encoding in output. Parent-reported focused
and offline PASS confirm execution of those checks.

**AIM-D04 — BLOCKING, OPEN → RESOLVED.**
`contracts/application-libraries/v1alpha1/deployments.schema.json:15` and
`internal/installer/application_library_save.go:11`: canonical schema and managed
writer consistently require the declared host[:port] form. Scheme/path/userinfo/
wildcard and unsupported forms have negative tests; localhost:port has positive
coverage. No React resolver was added.

**AIM-D05 — BLOCKING, OPEN → RESOLVED within approved plan-only acceptance.**
Public raw artifacts and real Review/Save/reopen handler drivers were inspected:

- Registry plan `plan-f9f1520ba8377bab44457b39`, revision428babe5…,
  EXECUTABLE, approved=false.
- Incorrect password: BLOCKED, APPLICATION_IMAGE_PREPARATION_FAILED.
- Corrected session inputs: fresh preparation and another EXECUTABLE plan.
- Offline plan `plan-6340d8fe7b73106db6ff02eb`, revisionc74e2613…,
  EXECUTABLE, without additional registry reads.
- Separate actual override/reset → Review/Save → reopen, retained references
  and unchanged project.yml.

The original cycle navigation race remains recorded as FAILED. It was not used
as proof of successful reopen; separate synchronized reopen and current-code
roundtrip close that segment.

`internal/desktop/application_image_preparation.go:41` now uses existing Broker
promotion after current Core descriptor/scope checks. Preparation payload copies
only requested registry requirements. Regression test, exclusion of unrelated
application values and rejection of a foreign library scope were inspected.

**AIM-D01/AIM-D03 — REJECTED_BY_OWNER**, per the 2026-10-20 disposition in ADR-046
and the original FULL report. They were not rechecked and are not declared
reviewer-corrected or technically reapproved. This scoped verdict does not
rewrite the original FULL report or waive secret-safety requirements.

## Overengineering

Confirmed new unnecessary abstractions, duplicate contracts/DTOs, premature
scope, speculative features and missed simpler mechanisms: **0** in scope.
D02 removes redundant propagation; D04 uses existing schema/writer boundaries;
D05 reuses Broker promotion. No new broker, store, DTO or planning lifecycle.

## Evidence and limits

The reviewer directly inspected the targeted diff, current bytes, corrections
and tests, existing Broker binding/expiry logic, public UI artifacts, roundtrip
driver and final QA log endings. The reviewer ran no tests.

Provided logs: Core: 734 tests, 22 skips, 0 failures/errors; final Go tests PASS.
Parent-reported focused12, offline13, Go/vet and frontend265/build/lint PASS;
source verification and skip reasons are in the journal. Registry counters
demonstrate separate successful/rejected requests.

Application Approve/Start/pull/load were not performed. Visual inspection:
NOT_PERFORMED, never reported as PASS. Actual secrets and targets were not read.

## Validity and next action

Review validity: CURRENT for this snapshot and scope. Changes to schema/writer
admission, secret propagation/promotion, payload preparation or substitution of
the inspected UI/Core runtime invalidate affected conclusions. Evidence-only
updates do not change implementation bytes.

Unresolved BLOCKING in requested D02/D04/D05 scope: **0**. Excluded D01/D03
statuses are unchanged by this targeted verdict. Return this report and closure
of D02/D04/D05 to the owner; retain the original FULL verdict and owner
dispositions separately. No further automatic review is required or initiated.
