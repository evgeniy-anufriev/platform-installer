# B4 transport corrections — independent FULL DIFF review

2026-10-15. Reviewer: architecture-reviewer `b4_target_transport_review`.
Base: `707a69d0a082d2216d9aab70d19a34ee09519483`.

Verdict: **APPROVE_WITH_CHANGES**, zero unresolved blocking findings. Nine frozen files were checked against `.runtime/qa/b4/transport-correction-identity.json` before and after review. This gate covers runtime activation quoting, project/package transfer, candidate package path admission and capability protocol selection; other B4 work is outside this review delta.

The reviewer found no new persistence/DTO/lifecycle/framework layer. Go reuses the B2 data-path predicate; Core retains its standalone candidate admission and link/type/size/ownership guards. The v1alpha4 capability request matches Core dispatch.

B4-TC-D01 (nonblocking): the new shell/Python parsing test compiled only the outer payload, so it did not prove rejection of malformed inner `exec()` input. Resolved after review by AST extraction and compilation of the constant inner payload, plus a negative check of the former malformed command. RED OS native test PASS. The reviewer explicitly did not require another architecture review for this test correction.

Review did not execute tests or contact targets. Parent verification: Windows executionnode/installer suites PASS; native RED OS candidate-path tests 2 PASS and execution lifecycle tests 59 PASS; native activation parsing test PASS. Actual library Apply/Verify remains a separate acceptance gate.
