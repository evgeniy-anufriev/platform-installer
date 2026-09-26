# SI08-C — Core and Execution Node secret-input path

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

RED OS QA, current working tree:

- focused input/lease/Core/Vault tests: 71 passed;
- full Ansible Core suite: 337 passed, 4 skipped;
- contract tests: 31 passed;
- Vault role tests: 15 passed;
- catalog reproducibility: PASS, `sha256:a460d77a38b7134f9a1639871eeb925a3ce8d673df3bfa5dcc1a40a22ada86d3`;
- configuration schema reproducibility: PASS;
- Vault apply playbook syntax-check: PASS (no target execution);
- `git diff --check`: PASS.

Secret-scope regression proves Apply receives manifest-bound shares and Verify
receives none. Schema and decoder tests reject Verify in the shares operation
list. The contract correction was owner-authorized before any immutable
runtime release advertised these versions; previously published capability,
lease and payload versions were not changed.

The initial full DIFF review found one blocking interruption-cleanup gap and
one nonblocking over-broad Verify scope. The single authorized targeted
recheck passed the cleanup finding. The owner then authorized the exact
operation-scope correction; its Core, lease, schema and service tests pass.
No further review cycle was run. No Vault target or QA server was mutated.
