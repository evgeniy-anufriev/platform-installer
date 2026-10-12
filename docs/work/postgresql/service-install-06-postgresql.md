# SERVICE-INSTALL-06 — PostgreSQL / pg_auto_failover

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-06-postgresql-checkpoint-002).



## Goal

Prove one isolated, Installer-managed `postgresql` deployment in
`pg_auto_failover` mode: monitor on node1 and database members on node2/node3.
The test creates its own Git-ignored project through the public Go
`CreateProject` lifecycle, then configures it only through the existing typed
edit session, review and local Save path. It does not open or change the
cumulative all-services project.

## Boundaries

- Do not hand-edit inventory, host vars, group vars or generated state.
- The isolated project identity has its own persistent generated-state
  directory. It never reuses the cumulative project's generated state.
- Existing target PostgreSQL state is not removed by this test unless a later,
  explicit cleanup step proves it belongs to this exact QA project. Host-wide
  PostgreSQL/Kafka state is never reset.
- Use the Core-derived UI-02F service secret requirements. Values are supplied
  only to the in-memory runtime lease and never to project files, events,
  journals or evidence.
- Each execution is a fresh `CreatePlan -> ApprovePlan -> Start` over the
  isolated PostgreSQL project. No direct playbook run counts as acceptance.

## Acceptance

1. First cycle reaches `SUCCEEDED`, records PostgreSQL apply/verify success,
   monitor membership and two database members on distinct hosts.
2. Second fresh cycle reaches `SUCCEEDED`, PostgreSQL verify passes and every
   apply recap is `changed=0`.
3. The isolated project has exactly three servers, its PostgreSQL deployment,
   PKI foundation, and four runtime SecretRef requirements; it has no
   dependency on the cumulative project.
4. The operator mirror exists, all temporary remote QA workspaces are removed,
   and no secret value is emitted.

## Implementation sequence

1. Add a Go E2E helper that creates or safely reopens the dedicated
   `service-install-06-postgresql-project`, emits three server commands, the
   minimal PKI foundation, one PostgreSQL create command, its three member
   placements and four `runtime:*` SecretRef configurations, then reviews,
   commits and reopens.
2. Add an opt-in SERVICE-INSTALL-06 lifecycle test. It obtains the normal
   target credential plus four runtime values from environment only, proves the
   exact service requirement set passed into the private lease provider, and
   performs both cycles.
3. Run focused Windows Go tests, RED OS Core/playbook tests and the real
   approved QA lifecycle. Record run IDs and observations here only after both
   cycles pass.

## Acceptance evidence

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-06-postgresql-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
