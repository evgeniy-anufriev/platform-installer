# UI-01A — architecture and safety review

Status: PASS, 2026-09-05. Both reviews were independent and read-only. Final
blocking findings: **0**.

## Core/contract review

The first pass found four blockers: v1alpha1 EditPlan could not represent an
absent first-save document, artifact-lock provenance was undefined, validation
was not obligatorily bound to the selected Execution Node, and new commands had
no versioned contract. It also found incorrect member-override physical origin.

The accepted remediation freezes:

- `project-edit/v1alpha2` with PRESENT/ABSENT document preconditions and a fixed
  path allow-list;
- the UI creation profile `artifactLock.digest = executionbundle.Verified.Digest`
  and catalog/service locks from that same verified bundle;
- the operator-selected READY Execution Node as the only production Core
  validation runtime;
- versioned lifecycle, edit-session and fixed snapshot-request contracts;
- the member-origin defect as a mandatory UI-01F gate, with editing disabled
  until Core reports the actual managed/user/inline origin;
- an exact project-local `ansible.cfg` and a UI-01D standalone proof that runs
  from the project root without `ANSIBLE_CONFIG` or explicit inventory override.

Final result: **PASS, 0 blocking findings**. Ansible project ownership remains
canonical, Core remains semantic authority, and no mutable snapshot or generic
SSH bridge was introduced.

## Safety review

The first pass found four blockers in the implementation prerequisites: Windows
reparse handling around writer runtime/recovery, unbounded candidate transfer,
weak SecretRef value checks, and an unresolved target credential transport. A
second pass reduced this to ambiguity between target credentials and local SSH,
plus insufficient Windows ACL requirements.

The accepted remediation freezes:

- OS-specific reparse checks, handle/root identity rechecks, protected Windows
  DACLs and safe exact-child recovery/removal;
- canonical-only regular-file candidates with file/path/archive byte limits and
  fail-closed extraction;
- opaque `runtime:` references with no path segments and common Go/Core schema
  validation;
- one write-only target credential lease, no workstation-to-target SSH, and a
  separately gated fixed Execution Node secret-lease operation for UI-02;
- OS no-replace create publication and bounded, identity-checked orphan cleanup;
- a narrow Wails bridge, CSP/raw-HTML restrictions and lockfile/audit/SBOM gates.

Final result: **PASS, 0 blocking findings**. These are implementation gates, not
claims that UI-01C/D/E or UI-02 already implements them.

## Accepted residual risks

- UI-01D must implement and prove the writer/path/archive/SecretRef safeguards
  before any UI mutation is enabled.
- UI-01F must correct member configuration provenance before member editing.
- `PutRuntimeSecretLease/v1alpha1` remains UI-02 work; installation using an
  unmaterialized credential mode remains blocked while UI-01 save is unaffected.
- Dependency vulnerability/license/SBOM checks begin when UI-01B creates the
  first lockfile; UI-01A generated no frontend dependency tree.
- Linux/macOS packaging remains a later platform acceptance item.
