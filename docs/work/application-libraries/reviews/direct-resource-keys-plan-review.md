# Direct resource keys — FULL PLAN

Independent reviewer: `/root/topic_roles_plan_review`; 2026-10-19.
Revision: `a5ce142cfb9f29dbab524d45b0ec6f3cb6ef73fb` plus approved plan.
Reviewed plan SHA256: `5c9a9882fdc139cb7252ca651040e2fb0bed044ee1b68ac7375065e2d08e743b`.

Verdict: APPROVE_WITH_CHANGES, zero blockers. DIRECT-P01 (nonblocking): state
collision precedence explicitly, cover legacy override/removal and direct keys
with native tests, and require removal of old authored bindings during migration.
Bounded clarification added to plan; no repeat review required.

Owner subsequently specified logical key `ef-store` with physical name `ef-store`.
This replaces the draft spelling `ef_store`; the approved isolation stays intact.
No overengineering finding. FULL DIFF review remains required after implementation.
