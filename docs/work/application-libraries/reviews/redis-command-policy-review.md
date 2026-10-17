# Redis/Sentinel operator-owned command policy — independent reviews

2026-10-17, reviewer /root/library_common_plan_review, read-only.

FULL PLAN APPROVE, zero findings/blockers. Plan redis-command-policy-plan.md SHA-25643469f9db5594a083a09bb3d227bfd11778e5d01c1a5fbe61f5011d1688bc27e.

FULL DIFF APPROVE, zero findings/blockers. Base HEAD8feb047af1c24c70ede737fe03941b9bbf04ac3c; manifest .runtime/redis-command-policy-review-scope.json SHA-256a4aad2f3185eadf6632af7af851f974f1dda69258c9d2634866e3bdf26868422. Eight before/after hashes verified, zero mismatch. Scope isolates this operator-requested permission-policy change from preceding dirty work.

Core/module command policies and Sentinel-only fields restrictions removed; typed syntax/bounds retained. Existing ACL helper unchanged: ownership, witness, TLS, private input custody, managed/existing and drift/Verify retained. No category interpreter or new revocation algorithm. Contract/ADR044/roadmap agree. Overengineering findings0, no new helper/API/DTO/store.

Reviewer checked incremental diffs, call sites and hashes, plus saved RED OS providers17/native ACL3 PASS logs; did not execute tests or contact hosts/secrets. Native tests prove explicitly assigned Sentinel SET/RESET and client ACL WHOAMI/CONFIG GET, rejection before assignment, repeat/Verify ACL preservation. Actual SDKU health remains a separate deployment gate.

Validity CURRENT for this identity. Previous SDKU-SENTINEL-MASTER-only approval is SUPERSEDED by the owner's explicit policy amendment; PostgreSQL CREATE review is unchanged/outside scope. Deployment continues through a fresh authoritative approved plan only.