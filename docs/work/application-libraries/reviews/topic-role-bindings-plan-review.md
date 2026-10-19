# Topic role bindings — independent FULL PLAN review

2026-10-19, reviewer `/root/topic_roles_plan_review`, architecture-reviewer,
read-only. Verdict **APPROVE**, zero blocking/nonblocking findings.

Reviewed the entire [plan](../topic-role-bindings-plan.md), SHA-256
`9b0c5e2ea5043df65d71b5b211593787bfde7e14c4c6f84abb6f357ab3a96d05`,
at HEAD `a5ce142cfb9f29dbab524d45b0ec6f3cb6ef73fb`; identity checked before/after.
Scope includes existing resource_defaults, named roles, early Ansible context,
provider projection, guarded writer, UI and legacy list compatibility.

Reviewer confirmed: defaults do not create resources; raw placement context is
bound before ENV expansion; one normalized resource set goes to existing Core
projection; wrong-provider/missing/cleared references fail without fallback;
UI saves differences and Reset deletes them. No extra persistence, lock,
defaultsRef, startup lookup or unnecessary abstraction was proposed.

Read AGENTS/current state/review procedure, scoped Core/Go rules, Core review
skill, canonical project/Core contracts, schemas, relevant tasks/actions,
projection, guarded writer and affected UI/design/mockup. Tests not run in PLAN
review. No implementation acceptance, deployment or Kafka mutation authorized.
FULL DIFF remains required after implementation.

Subsequent direct owner corrections retain the reviewed architecture: physical
names use sdku-alarms*; template/resource IDs and application binding values use
main/main_compact/alarms/alarms_compact. Prefixes remain in library name fields
so the application packages are reusable in CSPA. These data-name changes are
included in the original FULL DIFF; the original PLAN identity above is preserved.
