# SERVICE-INSTALL-06 — PostgreSQL / pg_auto_failover

Status: **DONE (2026-09-24)**.

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

The production-shaped Go lifecycle acceptance passed on 2026-09-24 against
three distinct RED OS targets: node1 (`192.168.56.101`) as monitor, node2
(`192.168.56.102`) and node3 (`192.168.56.103`) as database members.

| Cycle | Run ID | Terminal result | Duration | Apply changes |
| --- | --- | --- | --- | --- |
| First | `installer-45943379628ebee4a28716d85b571916` | `SUCCEEDED` | 17m45s | 65 |
| Repeat | `installer-4fcc0cd5afc8689509aea2e2a49935e6` | `SUCCEEDED` | 17m9s | 0 |

Both cycles completed PKI apply, PostgreSQL/pg_auto_failover apply and
PostgreSQL verify successfully. The opt-in Go test
`TestServiceInstall06PostgreSQLLifecycle` passed in 2094.93s. Its operator
event mirrors are retained under the corresponding Git-ignored
`.runtime/executions/<run-id>/events.jsonl` directories.

During acceptance, a valid topology without an explicit monitor member port
exposed a templating defect in the TLS credential probe. The role now consumes
the already-resolved defaultable monitor port; the focused RED OS contract,
deployment-plan, lifecycle, PKI-apply and configuration-resolution suite ran
111 tests successfully. No secret value was written to the project, events,
journal or evidence.
