# UI-NET-01 — Provider and virtual-address editor evidence

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

UI-NET-01 is complete. It adds the provider side of the existing canonical
endpoint model to **Topology → Entry points** without adding a local resolver,
PKI workflow, target operation or second persistence path.

## Delivered boundary

- Immutable `project-edit/v1alpha6` carries one complete
  `ReconcileEndpointProvider` tuple or an explicit `ClearEndpointProvider`.
- The existing EditSession, final-state reducer and guarded local writer own
  local Save/reopen. Reconcile requires an exact READY provider-capable catalog;
  Clear remains catalog-independent structural cleanup.
- The Wails Entry points screen uses only typed intents. It renders eligible
  providers, direct-owned legacy states, bounded VIP rows, draft state and the
  existing Core endpoint preview.
- Provider drafts mark preview stale with the neutral local statement that
  configuration changed. React and Go do not infer PKI/SAN effects. Current
  FQDN/VIP data is explicitly labelled as Core evidence; INVALID has findings
  only, without an authoritative preview.

## Acceptance evidence

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#ui-net-01-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
