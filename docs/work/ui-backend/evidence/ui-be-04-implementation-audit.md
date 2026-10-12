# UI-BE-04 implementation checkpoints

Historical implementation snapshots from [the milestone plan](../ui-be-04.md).
The word current below refers to the source audit snapshot; consult
[CURRENT_STATE](../../../../CURRENT_STATE.md) for current status.

## Current implementation audit

The accepted EXEC-01A implementation provides a pre-Core bootstrap and a
narrow synchronous service acceptance path:

```text
Go workstation
  -> explicit host-key-checked SSH/SCP
  -> /var/lib/platform-installer/runtime/releases/<bundle-digest>
  -> atomic runtime/current activation
  -> Core capability check
  -> target repository probe
  -> existing artifact resolver
  -> target-filtered RuntimeProjection
  -> fixed Kafka/Keepalived playbook allowlist
  -> shared Ansible artifact source gate
  -> service role
```

`executionnode.Service` owns readiness and digest-bound preparation plans.
`ServiceExecutionService` performs one target repository probe per requirement,
uses `artifactsource.ResolveForNode` as the sole source-selection authority,
builds an ephemeral target-filtered projection and stops a `BLOCKED` result
before transport. `platform.core.artifact_source_gate` independently blocks an
invalid projection before service mutation, while
`platform.core.artifact_delivery` verifies offline bytes on the target.

The current `OpenSSHTransport.ExecuteService` is synchronous. It stages a
project and runtime extra-vars under `/var/tmp`, maps Kafka and Keepalived to
specific playbook and collection paths in Go, waits for `ansible-playbook`,
and returns only a Boolean. It has no deployment plan, run identity, machine
events, terminal result, durable process ownership, journal, replay, reconnect
or cancellation. It remains an EXEC-01A regression path and is not the future
UI-BE-04 execution API.

The published `DeploymentPlan`, `ExecutionEvent` and `DeploymentResult`
schemas are unused architecture foundations. The activated runtime currently
advertises only `validate`. Core has target-free validation and snapshot
entrypoints, but no `BuildDeploymentPlan`, private execution manifest or fixed
execution controller.

## UI-BE-04D implementation checkpoint

The accepted implementation uses a separate public deployment-plan store. It
keeps plan metadata, public runtime-release identity and acknowledgement codes;
the private ExecutionManifest is never decoded or retained. Approval is an
exact-set one-shot. Start rebuilds immediately through the Core adapter,
compares the complete Core fingerprint, and only then calls semantic
StartExecution. Sessions use bounded sequence-ordered replay/reconnect and
semantic cancellation. Slow subscribers are closed deterministically; Go owns
no polling goroutine or process/systemd implementation.
