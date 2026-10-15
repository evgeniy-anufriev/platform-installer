# Apply performance P2 — owner-approved TARGETED_RECHECK

2026-10-15. Reviewer: architecture-reviewer `apply_performance_p2_diff_review`.
**APPROVE. AP-P2-D01 RESOLVED; unresolved blockers0.**

Owner explicitly authorized the minimal correction and one finding-scoped recheck.
Base `3fcf54c83ec13dcb2fda035862a5305c843a1095`. Two-file manifest
`.runtime/qa/apply-performance/d01-recheck-identity.json` SHA-256
`4397A292650E5DE41D542D305879CDA5B9329C9D11D3F194A018EF27EC664D06`;
both hashes verified. This is not a second FULL review.

Removed duplicate undefined-singular access from HAProxy main. Normalized nonempty
plural, conflicts and each ID remain validated in partial_scope.yml; main phase,
desired-state and deployment guards remain. Native regression invokes production
normalization/main assertion for plural-only, singleton, full/no-partial and rejects
empty/conflicting scopes before mutation. Reported4PASS19.730s; reviewer did not
execute tests or target commands.

No new abstraction/contract/persistence/concurrency. No new blocking regression on
the corrected boundary. Valid for this correction over the prior FULL scope;
full regression, target acceptance and measured Apply are separate pending gates.
