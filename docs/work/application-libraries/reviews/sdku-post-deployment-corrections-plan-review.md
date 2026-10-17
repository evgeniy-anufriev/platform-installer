# SDKU post-deployment corrections — FULL PLAN review

2026-10-17. Independent read-only reviewer library_common_plan_review using
architecture-reviewer instructions. Verdict BLOCK; blocking findings1.
Base HEAD4314e0b7ff1b9186199502d259f2ee4f668710ed. Reviewed plan SHA256
130bbc90c5f9c7d0f350e09304a237a5715e97f52191ae858f31566764e819dd.

SDKU-PC-P01 BLOCKING OPEN: original image reference startup introduces a mutable
shared tag. Two projects sharing one Docker daemon/account can use the same
original tag with different image locks. Checking tag/imageId before compose
and container.Image afterward does not prevent another project from retagging
in between. The wrong image could execute with application mounts/secrets
before the subsequent mismatch is observed.

Evidence: existing apply_library.yml25-28 lock is per libraryPath;
execution_protocol.py653-668 active-run admission checks equal projectIdentity,
not daemon-wide exclusivity. Plan section2, image_delivery.yml and
activate_instance.yml are the immediately affected source-authority boundary.

Smallest proposed correction: target-side guard serializing tag assignment,
locked image identity check and Compose creation/start for the same daemon and
original reference across projects/libraries. Reuse small acquire/cleanup tasks,
not a scheduler/lock daemon. Fail closed for held/abandoned guards; clean own
acquired guard on ordinary failure; cancellation must not permit an uncertain
still-running child to outlive guard release. Retain actual container.Image
verification. Acceptance: concurrent projects/same tag/different locked IDs;
no container starts foreign image; failure/cancel/repeat/cleanup cases.

Other plan boundaries accepted: shared library projection required for identical
base bytes; existing Registry projection reused; all targets; target-account HOME
and shared Apply/Verify/Vault paths; no automatic old-directory deletion; operation-
stage evidence handling; explicit library-only risky skip bound to fresh approval
and negotiated contracts, with no fabricated PASS and unchanged trust/artifact/
secret/preflight boundaries. UI design discrepancy recorded before implementation.
Overengineering findings0; target guard is justified by this concrete mutable tag.

Reviewer directly inspected plan/code/contracts/UI ownership instructions; no
server access, secret retrieval or test execution. These are plan checks, not
runtime acceptance. Production code and active SDKU runtime remain unchanged.
Automatic work stops per review procedure until owner decision on P01. One
owner-approved TARGETED_RECHECK may inspect the correction and immediate boundary.

Owner disposition: SDKU-PC-P01 REJECTED. Supported executions are sequential;
additional daemon/tag guards are explicitly forbidden. Owner authorized all seven
corrections and implementation under this scope. No targeted recheck of the
rejected blocker is requested; final DIFF review must respect this decision.
