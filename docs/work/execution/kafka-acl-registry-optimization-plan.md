# Kafka ACL and Schema Registry optimization

Owner request: implement the analyzed optimization in a separate worktree.
Base: `0e739c61` snapshots source worktree `service-runtime-optimization`
at `ee8e35e6` plus its uncommitted changes. Those inherited changes are not
part of this review. Runtime evidence: installer-e448ed0bde79e1d5312ed8db651bd924,
Kafka Apply 1292 seconds; ACL writes 146s, Registry API readiness 135s,
three topic descriptions 50s. No bundle publication or target Apply is planned.

## Scope and invariants

- Reuse the existing ACL inventory and delta writer for compatibility principals.
  Group equal missing operation sets across topic/group/transactional-id;
  preserve principal, host, permission, pattern type and resource identity.
  Keep cluster and all other resource types separate. Identity used for
  deduplication includes resource type and name (wildcard names can coincide).
  Managed Apply alone writes; existing/Verify remains read-only; no removal.
- Registry instance preparation retains ownership, symlink, PKI, configuration
  and unit checks. Do not remove those guards or weaken ordinary Verify.
- Split Registry orchestration into preparation, deployment topic reconciliation,
  activation, and deferred readiness. Preserve instance-specific restart signals
  in run-local host facts, never project state. Activation records form a list,
  replaced on every invocation so hash_behaviour=merge cannot retain old keys.
- Reconcile `_schemas` once per participating deployment after all participating
  instance configurations are prepared, using one selected instance's protected
  client file and its host. Prefer the canonical first instance when participating;
  a partial inventory may read through another member but must not create there.
  Check existing policy; on creation re-read and validate before any activation.
  Failure must stop activation on all participating hosts. No global run_once
  cache across deployments or separate invocations; handle reversed inventory,
  multiple deployments, co-location and partial inventory explicitly.
  The candidate contributes identity only: select the exact prepared instance
  from that host's local projection by deployment/id/host, checking uniqueness
  and its activation record. Use that instance's full host-local context and
  captured CLI directory on the delegated host.
- Start newly installed units before the final readiness loop, allowing their
  startup waits to overlap. Existing units retain sequential restart + readiness
  before the next instance. Classify new only when the immediate unit stat shows
  absence AND systemd reports LoadState=not-found / ActiveState=inactive before
  writing. Loaded, active or ambiguous state stays sequential; command errors
  stop preparation. Reset the runtime list on every invocation. API readiness checks both HTTP
  and HTTPS, CA verification stays enabled. Keep retry bounds unchanged.
- No new Kafka client/helper, desired-state field, transport, UI, source-selection
  policy, persistent cache or generic scheduler. Small ordinary Ansible task files.
- Use the ordinary linear Ansible strategy, explicit in the supplied Registry
  playbook. Standalone callers must also use linear, not free. For serial playbooks
  select the topic candidate from ansible_play_batch; reconcile once per deployment
  in each batch, never through an unprepared future batch. The full preparation
  and activation scope is any_errors_fatal, including distribution preparation.

## Validation

Native Ansible in an isolated RED OS workspace: compare exact expanded ACL tuples
and write counts; same names on different resource types, distinct operation
deltas, principal isolation, existing/Verify, repeated Apply and partial failures.
Registry: real orchestration with isolated command/API fixtures; reverse inventory,
multiple deployments, partial inventory, topic drift/create failure/post-create
readback, preparation barrier, cold start ordering, rolling restart failure, and
readiness timeout. Focused existing Kafka/Registry tests and syntax checks.
No service mutation on the active stand. Real React/Wails installation and actual
wall-time acceptance require a subsequently published bundle and installation;
they will not be reported as passed by this implementation's isolated QA.

Independent FULL PLAN and FULL DIFF review follow the repository review procedure.

FULL PLAN: APPROVE_WITH_CHANGES, blocking0. KRO-P01 (loaded systemd unit without
file) and KRO-P02 (linear/serial batch boundary) incorporated above. Reviewer read
the plan at SHA256 937fd967462895e68b8230885c1d3dcf269cd3517a39509d72a7caacb2a8272c.
