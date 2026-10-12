# PKI platform-wide TLS certificate usages — implementation plan

Status: owner-approved implementation direction; PKI-PLAN-01 passed the
targeted recheck. The owner accepted the exact lock correction for the
remaining PKI-PLAN-02 after the review budget was exhausted.

## Goal

Make the existing platform-default managed leaf certificate usable as both a
TLS server identity and a TLS client identity. This is required by services
that use one host-scoped certificate for inbound TLS and peer/client TLS, in
particular ClickHouse Keeper Raft.

“Platform-wide” retains the existing PKI scope model: at HOST scope, each host
has its own leaf certificate, shared by TLS consumers on that host. This does
not copy one private key across different hosts or change HOST/MEMBER/DEPLOYMENT
scope semantics.

## Evidence and current contract

- `platform_pki_policy_defaults.usages` currently defaults to `[serverAuth]`.
- A certificate profile without explicit `usages` inherits that role default
  through the existing PKI resolver.
- The ClickHouse Keeper template configures the same managed certificate and
  key under both its OpenSSL `server` and `client` sections.
- The failed S11 Keeper certificate chain and SAN checks passed, but OpenSSL
  accepted its leaf for `sslserver` and rejected it for `sslclient` as
  `unsuitable certificate purpose`.
- Existing service contracts already require client-purpose material where
  applicable; examples include Redis TLS and Docker/Kafka runtime TLS checks.
- PKI-01 already supports `serverAuth`, `clientAuth`, or both. Ordinary
  reconciliation blocks a changed request fingerprint; the existing explicit
  reissue flow is required for an initialized certificate.
- SI11 run `installer-d471170dcf7d8e11d2325e9596b0364b` stopped before service
  apply at `Require explicit authorization for certificate reissue`. The
  authoritative Execution Node journal confirms the request fingerprint had
  changed while ordinary Wails Start supplied no explicit reissue request IDs.

## Owner decision — UI-triggered reissue (2026-10-03)

When the approved saved configuration changes a managed certificate request,
the normal Installer UI plan/run must invoke the existing
`ansible-core/playbooks/pki-reissue.yml` path. This is not a request to remove
Core's reissue safety guard or to run `pki-reissue.yml` unconditionally.

The Installer must reissue only requests whose current Core-derived
`certificateRequestFingerprint` differs from the persistent request marker on
the selected Execution Node. Initial requests with no existing marker use the
normal issuance path; matching fingerprints do not reissue. A repeated
unchanged plan must therefore retain the current no-op/idempotent behavior.
The existing standalone `pki-reissue.yml` contract remains available and
ordinary standalone `pki-apply.yml` continues to reject an unauthorized
fingerprint change.

## Proposed change

1. Change only the product default leaf usage set from `[serverAuth]` to
   `[serverAuth, clientAuth]`.
2. Preserve explicit certificate-profile `usages` overrides and all normal
   Ansible precedence. Do not add a ClickHouse-specific branch or change
   published project schemas, resolver output shape, or PKI lifecycle.
3. Update PKI documentation and the resolver's default-policy test to describe
   both usages. Add an integration assertion that generated default leaf
   certificates verify for both OpenSSL `sslserver` and `sslclient` purposes.
4. Add a target-free Core planning projection that compares each resolved
   request fingerprint with its protected marker under the canonical project
   identity on the selected Execution Node. It returns a bounded deterministic
   list of exact request IDs requiring reissue or resuming an interrupted
   reissue, each with its observed prior fingerprint when one exists, desired
   fingerprint, and the existing safe target hosts. It reads no target hosts
   and mutates no PKI state. If this evidence is unavailable, inconsistent or
   ambiguous, planning blocks rather than guessing.

   Classify each request state explicitly:

   - No ordinary fingerprint marker and no reissue recovery marker: initial
     issuance through the ordinary path, not a reissue.
   - Ordinary marker equals desired fingerprint and no recovery marker:
     unchanged; no reissue.
   - Ordinary marker differs from desired fingerprint: reissue, bound to the
     exact observed prior fingerprint.
   - A valid recovery marker equals the desired fingerprint: resume the
     existing reissue for that same request ID, including if the ordinary
     marker was already removed during interrupted cleanup. Do not classify it
     as initial issuance or omit it from the approved action.
   - Malformed, mismatched or otherwise inconsistent recovery evidence: block
     safely; never infer a broader request list or discard the marker.

   When resuming, the existing PKI role remains authoritative for validating
   staged backup/recovery state. The projection does not expose certificate or
   key material.
5. Represent the changed-request reissue as an explicit Core-owned plan action
   before service apply. The Plan UI must identify that certificates will be
   reissued and show the affected request/deployment/host scope. Plan approval
   and Start authorize only the exact list bound to that approved
   project-revision/runtime plan.
6. At execution, invoke the existing `pki-reissue.yml` with exactly the
   plan-bound changed or resumable request IDs before ordinary service apply.
   Bind each item to its request ID, observed prior fingerprint, desired
   fingerprint, and approved project revision/runtime in the plan identity.
   Immediately before any destructive PKI cleanup or material mutation,
   recheck the observed marker state on the selected Execution Node while
   holding the existing project-scoped PKI apply lock. If the prior marker
   still equals the expected old fingerprint, proceed. If a matching recovery
   marker proves this exact desired reissue is already in progress, resume
   that same request ID via the existing recovery path. If state changed to a
   third or inconsistent value, fail as stale; never force-reissue based only
   on the previously approved ID. This compare-before-mutate check closes the
   race between planning and execution.

   The existing Execution Node controller helper
   `_acquire_project_pki_apply_lock` currently locks only `PKI_APPLY` at
   `<execution-state-root>/projects/<project-id>/.pki-apply.lock`. Extend that
   same acquisition to the planned PKI reissue action and retain the descriptor
   through the complete `pki-reissue.yml` playbook, including target deployment
   and recovery-marker finalization. Do not nest another acquisition inside the
   playbook while the controller holds this lock, or create a parallel lock
   namespace. For a standalone operation sharing this state root, the supported
   command wraps either whole `pki-apply.yml` or whole `pki-reissue.yml` in
   `flock -n` on the exact same path, as already documented for standalone
   apply. An unwrapped direct playbook invocation does not provide cross-process
   serialization and must not be used concurrently with Installer PKI actions.
   Preserve existing reissue backup/recovery-marker
   behavior, cancellation and terminal evidence. On failure, stop before
   service apply and never silently widen the request list. Once reissue
   succeeds, preserve the existing same-run PKI apply/deploy optimization.

   If execution is interrupted after the recovery marker is written, the next
   target-free plan recognizes the matching marker as a resume action for the
   same request ID. A matching recovery marker takes precedence over a missing
   ordinary marker caused by interrupted cleanup. After successful reissue,
   the recovery marker is cleared and the ordinary marker equals desired, so a
   fresh plan is a no-op.
7. With no changed requests, do not invoke `pki-reissue.yml`; retain normal
   initial-issuance and ordinary `pki-apply.yml` behavior.
8. Regenerate a fresh plan and use the real Wails Start flow for S11 only after
   the new immutable runtime is built and activated through supported
   Execution Node preparation/promotion. The acceptance flow must not use a
   direct Core/Ansible Start bypass.

## Acceptance

- Default resolved PKI requests contain exactly both `serverAuth` and
  `clientAuth`, deterministically.
- An explicitly configured profile usage override remains honored unchanged.
- A test leaf generated under the platform default passes both
  `openssl verify -purpose sslserver` and `-purpose sslclient`.
- Changed request fingerprints still require the existing explicit reissue
  authorization; ordinary standalone apply does not replace existing leaf
  identity. The approved Wails plan can authorize only its exact displayed
  changed/resume request IDs through the existing reissue playbook, each bound
  to observed prior and desired fingerprints.
- An interruption after recovery-marker creation but before restoring the
  ordinary marker is recognized by the next plan as a resume for the same
  request ID. Inconsistent marker/recovery evidence blocks instead of being
  treated as initial issuance.
- A marker change between plan and execution is rejected immediately before
  mutation. `pki-apply.yml` and `pki-reissue.yml` serialize on the same
  project-scoped PKI lock when invoked through the supported standalone
  `flock -n` command or the Installer controller.
- No request mismatch => no `pki-reissue.yml` invocation; changed requests =>
  exact request-scoped reissue before service apply; stale/missing comparison
  evidence => plan blocked.
- An unchanged fresh repeat after successful reissue keeps the same request
  fingerprints and does not reissue again.
- Standalone Ansible behavior remains available and no Installer dependency is
  introduced into Core.
- Run affected PKI resolver/materialization tests, full Core suite, Go tests,
  vet, security/secret checks and `git diff --check` on the current worktree.
- Before retrying S11, prove the reissued PKI through the real Wails flow and
  confirm Keeper TLS logs no longer report certificate-purpose failures.

## Non-goals

- No new certificate profile, schema field, public protocol, Go/Wails API, or
  service-specific TLS exception.
- No global override of explicitly authored profile usages.
- No change to CA usage, identity/SAN generation, certificate scope, store
  password handling, runtime secret transport, target TLS verification, or
  normal reissue guards.
- No new S11 installation attempt as part of this plan review.
