# SI08-C — Core and Execution Node secret-input path

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

SI08-C implements the target-free Core descriptors and plan/private-manifest
projection, plus the Execution Node capability, typed lease admission, Start
binding and operation-scoped Ansible forwarding. It does not implement the
workstation Go provider, age-protected files or UI; those remain SI08-D. It
does not publish or activate an immutable runtime release and does not install
or initialize Vault; real service acceptance remains SI08-E.

Implementation and acceptance gates pass. SI08-C/D are recorded together in a
focused implementation commit. Unrelated shared-worktree changes are not
included; runtime publication and real Vault acceptance remain separate.

Typed inputs are bound to the exact deployment, manifest requirement, payload
and allowed operation. The Vault administrative token is available to
`SERVICE_APPLY` and `SERVICE_VERIFY`. Unseal shares are available to
`SERVICE_APPLY` only; Core descriptors, the private manifest, lease validation
and the runtime filter all enforce this scope. Verify therefore does not
receive unseal shares.

Ansible receives typed values through an operation-scoped mode-0600 temporary
extra-vars file, not process arguments. The controller removes it after normal
operation completion. If a run is interrupted, recovery/cancellation cleanup
removes only exact-name, owned regular files inside the verified private run
directory; matching symlinks and non-regular entries are not followed or
removed. Get retries cleanup for terminal runs once their controller is
inactive.

## Verification

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-08c-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
