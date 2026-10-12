# SI08-E — bootstrap correction plan, revision 2

Status: owner accepted the revision-1 review correction; implementation and QA
reset are not performed by this document. Review scope is only
`SI08-E-PLAN-01`; `SI08-E-PLAN-02` remains a prerequisite for a separate reset.

## Boundary and evidence

Preserve standalone Ansible, existing protected custody directories, minimal
`init-response.json`, `admin-token`, `unseal-shares`, existing controller output
recovery, no_log and published protocols. No new provider, plugin, database,
generic filesystem framework or full API-response persistence.

Reported run `installer-b095002168ac83f7fb1aa9289f7120cb` failed after init and
before recovery persistence. TLS API reported initialized=true; existence-only
checks found all three custody files absent. Synthetic actual-task execution
failed with `.keys` and passed with `['keys']`. These are prior observations,
not acceptance of this unimplemented plan.

## Exact first-init sequence

1. Before POST init, retain current ownership/no-follow/output checks. Require
   the controller's existing Linux coreutils `/usr/bin/sync -f` support by
   successfully synchronizing the already-created protected output directory.
   Failure blocks init. This is a standard command, not a new helper.
2. POST init through the existing verified TLS API; register the response under
   no_log. No change to Vault initialization parameters.
3. The immediately following task atomically copies the minimal record directly
   from the registered response using explicit mapping indexes:
   `{'root_token': response['json']['root_token'],
   'keys': response['json']['keys']}`. Use existing `ansible.builtin.copy`, mode
   0600, force=false, safe atomic writes, delegate localhost, become=false,
   no_log=true. No intervening set_fact, semantic assertion, unseal, or normal
   output publication. Never overwrite an existing recovery record.
4. Check the fixed recovery file is regular, not a symlink, controller-owned,
   mode 0600, within the existing bounded protected directory. Read back under
   no_log and compare its minimal fields with the registered response without
   emitting values. A pre-existing conflicting record fails closed and remains
   intact. Run `/usr/bin/sync -f -- <recovery-file>` and then
   `/usr/bin/sync -f -- <output-directory>` using fixed argv and changed_when
   false, delegated to the controller. Both must return success. GNU sync -f
   synchronizes the containing filesystem, covering file data and directory
   publication; atomic copy alone is not claimed as durable. No secret enters
   argv. Any readback/sync failure preserves the recovery file and stops.
5. Load material from that saved record, then apply the existing strict token,
   sequence, item-type, share-count and other required validations. All data
   fields named keys use `['keys']`; intentional dictionary.keys() introspection
   is unchanged. Malformed material is retained but never used or published.
6. Publish admin-token and unseal-shares through the existing no-overwrite copy
   sequence. Check both fixed files' regular/non-link/controller-owned/0600
   metadata, read them under no_log, compare the token and exact shares to the
   validated recovery record, then synchronize both files and their directory
   using the same standard sync -f command. A partial/conflicting publication
   stops with recovery intact; no READY claim follows.
7. Only after both files pass readback and synchronization may the existing
   recovery record be removed; synchronize the directory after removal. If
   deletion or its synchronization fails, fail safely: never remove either
   custody file or reinitialize Vault. Duplicate recovery metadata is permitted.
   Unseal/configure proceeds only using validated saved material.

## Reopen and failure semantics

For an initialized seed with a recovery record, perform the existing safe path
checks, synchronization/readback and strict validation, then complete only
missing matching custody files. Conflicts fail closed without overwrite.
Recovery cleanup requires the same verified durable pair as first init.

Crash or response loss between Vault init and the first durable minimal record
cannot be made atomic across the Vault API and controller filesystem. An
unusable response missing required fields has the same limitation. This is
explicit operator recovery, not successful install; never blindly initialize
again, fabricate shares or reset automatically. The plan closes avoidable
intermediate-task loss, not this residual cross-system boundary.

## Required focused proof

- Execute the actual task sequence with synthetic inputs on RED OS under
  Ansible native=False and native=True; prove keys remain an exact string list.
- Inject failure after durable recovery and before normal publication; reopen
  and recover the identical minimal token/shares without another init.
- Inject failure after one custody file; complete the matching missing file.
- Wrong type/count, missing fields and conflicting records fail closed;
  no secret appears in stdout, events, diagnostics or test reports.
- Readback/sync failure retains recovery and blocks unseal/publication success;
  no recovery removal before a confirmed durable pair.
- Cleanup failure retains the durable pair and never reinitializes the seed.
- Existing matching material repeats unchanged; inherited input-file/recovery
  paths use explicit keys indexing. No raw response persistence.

## Separate QA reset prerequisite

This plan does not authorize reset. Reconcile saved revision, exact operation
and runtime role identity, unit/config/marker/data before proposing it. Public
deployment vault-qa-standalone and on-target vault/vault-1 are not presumed
equivalent. Require no active run/lock, exact owned resources and explicit owner
approval. Do not delete committed journals/output packages or unrelated state.
Prefer recoverable quarantine through an existing identity-safe mechanism; if
no suitable mechanism or ownership proof exists, stop and return the gap to the
owner. No new automatic cleanup subsystem is introduced here.

## Later gates

Implementation requires focused tests, full Core and affected Go/vet gates,
catalog/schema reproducibility, secret-safe audit and diff check. Acceptance
requires a new immutable runtime, supported activation and isolated lock update,
fresh plan/start through actual React/Wails, apply/verify, protected delivery
and repeat changed=0. None of these are marked PASS by this plan.
