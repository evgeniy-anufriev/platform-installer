# SERVICE-INSTALL-01A — typed host placement priority

## Goal

Close the single missing Installer edit capability exposed by the
SERVICE-INSTALL-01 Keepalived acceptance: a host-scoped deployment must be
able to persist its explicitly chosen per-host VRRP priority through the
existing Go `CreateProject → EditSession → ReviewStructural → local Save`
lifecycle.

This is a narrow edit-contract evolution. It does not change Ansible/Core
Keepalived semantics, derive a priority, or add a second project writer.

## Evidence and owner decision

The production-shaped Go execution flow already applied and verified the
manual canonical Keepalived fixture twice. Runs
`installer-facb10856cffc26bcb853529dcee48d6` and
`installer-698e9b0a4cb7a91c800618fd7f4859ca` both reached `SUCCEEDED`; the
repeat had no changed task results. The existing role requires
`platform_deployments.<deploymentId>.priority` on every participating host,
in the closed interval 1 through 254.

The owner approved adding the smallest typed edit capability after confirming
that current `project-edit/v1alpha8` can create host placement but cannot
express that required value.

After the implementation review, the owner additionally required UI acceptance
whenever the public UI can exercise the same workflow. The owner therefore
approves the minimal host-placement form change described below. It is a
generic v1alpha9 command field, not a Keepalived-specific control: React does
not inspect a service ID, label, mode or configuration to decide its meaning.

The owner additionally requires the service-install sequence to be
**cumulative**. It uses one runtime-only, Installer-managed QA project for
SERVICE-INSTALL-01 through SERVICE-INSTALL-07. SERVICE-INSTALL-01 creates its
initial Keepalived topology in that project; later milestones open that exact
saved project and append only the service under test through the same typed
EditSession/Review/Save lifecycle. This changes test-fixture persistence, not
portable-project ownership or any service contract.

## Contract: project-edit/v1alpha9

`project-edit/v1alpha9` is the new active command contract for new Installer
sessions. It is an additive, immutable-version evolution of v1alpha8:

- all v1alpha8 operations retain exactly their v1alpha8 semantics;
- `ReconcileHostScopedDeploymentPlacement.hosts[]` adds required `priority`;
- `priority` is an integer in the inclusive range 1 through 254;
- no other host-placement property is admitted; unknown fields fail closed.

The `hosts` list remains a complete, closed replacement for the selected
deployment's host-scoped placement. Every final host entry supplies and writes
one exact `priority`; omission, `null`, a fractional value and values outside
1 through 254 are rejected before Review/Save. `roles` retains the existing
optional semantics. The reducer never infers, retains or deletes priority from
an omitted value because omission is not valid in v1alpha9.

The command is deliberately not a generic key/value placement patch and does
not accept `configuration`, arbitrary properties, raw YAML, service names, or
service-specific variants. The Go writer merely preserves this typed desired
input. Core/service validation remains the authority that decides whether a
given service requires or uses it; there is no `if keepalived` branch in Go.

`v1alpha1` through `v1alpha8` remain immutable compatibility inputs. New
`EditSessionStore.Append` emits v1alpha9 only.
`contracts/README.md` is updated with v1alpha9 as the active closed
server/topology/provider/PKI/configuration/host-priority command contract.

## Ownership and persistence

The existing final-state reducer and guarded managed writer remain the sole
Save path:

```
Go command → final-state reducer → managed host_vars document
                                  → local guarded transaction
```

For a host-scoped placement, the existing source-host ∪ final-server
traversal removes the selected deployment from every relevant owned host
document, then writes the exact final host entry. The entry contains only
existing supported placement fields (`roles` if any) and required typed
`priority`. Existing extension fields outside the edited placement entry retain
the established writer-preservation behavior; the command does not invent a
new generic extension model.

The directly owned `ManagedProjectView` should project required `priority` in
`ManagedHostPlacement` for v1alpha9-created host placements so Save/reopen
presents the exact saved value. Existing pre-v1alpha9 host placements which
lack priority remain readable as legacy direct-owned state, but a malformed
persisted priority (null, fractional or outside 1 through 254) fails closed
before any transaction. This is a bounded local desired-state projection, not
a Core-derived topology model.

## UI boundary and acceptance

The existing host-scoped placement dialog renders one explicitly labelled
integer input per final host entry. It accepts only a whole value in `1..254`;
an empty, fractional, or out-of-range entry does not append an intent. A new
or legacy placement without a stored priority is visibly incomplete rather
than silently defaulted. The form then appends exactly one existing
`ReconcileHostScopedDeploymentPlacement` command containing the operator's
chosen values.

This is deliberately a generic projection of the closed v1alpha9 placement
shape. It has no `if service == keepalived` branch, does not derive priority
from host order, and does not claim that every Core service consumes the
field. Core remains the final authority on service semantics. The Wails model
only transports the direct saved field; it creates no parallel desired-state
DTO.

## SERVICE-INSTALL-01 acceptance update

The Keepalived acceptance fixture will be constructed as follows:

1. the Wails placement dialog is exercised against the public EditSession
   backend: it rejects an incomplete priority, accepts explicit values, and
   saves/reopens the same direct-owned placement through Review/Save;
2. the public Wails `CreateProject` flow creates the controlled, Git-ignored
   cumulative QA root from the fixed immutable bundle source; Go reopens and
   accepts only its `EMPTY_MANAGED_PROJECT` state;
3. one v1alpha9 Go `EditSession` with three `CreateServer` intents, one
   `CreateServiceDeployment`, one `CreateEndpointGroup`, one
   `ReconcileHostScopedDeploymentPlacement` with priorities 150/120/100, and
   one `ReconcileEndpointProvider` for VRID 61 / VIP `192.168.56.121`;
4. `ReviewStructural` and the existing guarded local Commit;
5. reopen and assert the owned servers, placement priorities and provider
   tuple without Core or target contact;
6. run the existing Go `CreatePlan → ApprovePlan → Start → observe → Sync`
   lifecycle twice against the three RED OS targets, retaining the resulting
   canonical project as the sole input to SERVICE-INSTALL-02.

The first milestone fails closed when the cumulative root already exists;
replacement is a separate, reviewed cleanup operation and is never an
implicit local reset. Each later milestone must open the same root, verify its
saved revision before appending its own commands, and prove its additions do
not rewrite previous service state. The final milestone builds one fresh plan
from that same accumulated revision. The test retains the existing
deployment-scoped cleanup/isolation rule. It must not reset hosts or touch
active Kafka units. Core remains responsible for the final target-free project
validation, deployment plan, apply and verify.

## Bounds, compatibility and non-goals

- The common Review limit remains 16 commands; the listed Keepalived setup
  needs seven.
- No priority is auto-generated, defaulted, inferred from host order, or
  derived from service identity. The UI shows an incomplete input rather than
  manufacturing a desired-state value.
- No member-scoped placement, endpoint/provider, catalog, Core schema,
  Ansible role, Execution Node, credentials or runtime-source behavior changes.
- The minimal existing host-placement dialog is in scope solely to collect and
  transport the closed v1alpha9 field. Rich service-specific priority UX,
  metadata extensions and new editor pages remain outside SERVICE-INSTALL-01A.

## Required proof

1. Schema: v1alpha9 requires a valid priority and rejects absence, zero, 255,
   fractional, null, and unknown host fields; v1alpha8 stays unchanged.
2. Go: v1alpha9 is the active session version; inherited operations normalize;
   the reducer performs exact placement replacement and Save/reopen preserves
   valid priority.
3. Safety: stale source-host placement cannot survive a move/delete; malformed
   priority is blocked before transaction; failure retains existing guarded
   rollback behavior.
4. UI acceptance: the real Wails form, where the local compatibility source is
   available, and the deterministic frontend seam both reject incomplete input
   and append/saves only explicit priority; the test does not contact Core or
   targets.
5. Execution acceptance: a newly Go-created Keepalived project passes
   target-free plan, then two protocol-mediated apply/verify cycles, with the
   second cycle `changed=0`.

## Overengineering check

The smaller alternative is to retain hand-authored host vars in every service
acceptance fixture. It does not meet the owner's stated requirement that Go
create topology and services, and it leaves a real gap in the active edit
contract. A generic placement-properties map would cover hypothetical future
fields but would widen the public writer surface and duplicate service
semantics. One required bounded integer on the existing host placement is the
minimum current contract extension.
