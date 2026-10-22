# Generated passwords and managed-password reconciliation

Revision 2 approved for implementation by the owner on 2026-10-21; implementation in progress.
Baseline: `e2b965b4256e22185a4652ef0fb133444a228fd1`.

## Owner decisions

Owner requested Core generation for standalone Ansible with existing UI support.
2026-10-21 amendments: add nothing to Verify; add only generation/generated
support and keep the remaining path; finally make the general change:
«если пароль не подходит, то задать тот пароль который передан».

The final instruction replaces revision 1's early Vault persistence proposal.
No early Vault write, custody namespace, persistent local cache, new Wails API,
Generate button, password reveal, configurable policy or recovery subsystem.
Previous FULL PLAN review (SHA256
`B6EBB92CFB3A195F70AE73A31333B9A1BAEDFB00CA2DE334D6F3FB38E625744D`,
APPROVE_WITH_CHANGES, zero blockers) is STALE for this changed architecture;
early-persistence recommendations are superseded.

For declared managed accounts the selected password is authoritative regardless
of runtime_secret_ref, vault_ref or generated source. Keep the current existing
mode meaning: use/authenticate, never mutate. This interpretation was stated to
the owner. Apply handles PostgreSQL, Redis/Sentinel, ClickHouse and Kafka.
Keep ownership, privilege, grants, TLS and admin checks, except Kafka's
password-possession guard explicitly described below.

Owner additionally clarified that only application passwords are reconciled.
Infrastructure credentials (Kafka admin, PostgreSQL superusers, Redis default,
Vault and other service identities) are consumed for administrative access only;
this feature never changes them.
Owner implementation priority: use Ansible tasks first; keep Python limited to
existing provider primitives, cryptographic generation and necessary validation.

Core runs on the Execution Node without Go/Wails. Ordinary Ansible inventory is
desired state. Relevant current contracts: project-contract, architecture,
application-libraries secrets.md/execution.md and A4 technical plan. Update A4's
generated-deferred/no-password-reset restrictions only for this scope.

## Generated source in the existing delivery path

1. Keep `password.source: {kind: generated}`. Managed passwords only; literal
   usernames and existing-mode restrictions remain. Require the existing Vault
   binding/account publication path; where absent, block rather than add storage.
2. Extend existing target-free provider/Vault projection with distinct stable
   passwordRefs per canonical account location. Hashing `{kind: generated}` alone
   would collide. Project persisted locations as ordinary existing Vault source
   jobs for the already existing read path. No new Verify jobs or Verify change.
3. In existing Apply Vault preflight, read/check document ownership before
   resolving generated values. Extend the existing private document action with
   a small `secrets.token_urlsafe(32)` generator (256 bits, ASCII, no newline).
   Reuse a valid password from the owned saved account document; without a saved
   password generate once per logical account per Apply, not per placement.
   Preserve current foreign-owner/tombstone rejection.
4. Write the chosen bytes to existing invocation-only protected secret files:
   owned private directory, regular 0600 file, no symlink traversal, bounded bytes.
   Reuse validated same-invocation files. Return private file references through
   existing action/facts and pass the combined credential-file mapping to document
   resolution. Apply source delivery skips refs already prepared by generation.
   Other source paths keep their behavior; no public DTO or extra storage.
5. Existing provider hooks use those exact bytes. Existing final Vault document
   reconciliation remains AFTER provider success, followed by policy/AppRole and
   Agent delivery. Keep current CAS/neighbor-field preservation and always cleanup.
6. If Apply fails before Vault publication, retry may generate another password.
   For confirmed managed ownership after a completed provider hook, reconciliation
   installs the new value and then publishes it normally. A crash inside initial
   Redis/ClickHouse creation before ownership-witness persistence remains blocked
   by the existing ownership checks; no automatic recovery is promised there.
   After publication subsequent Apply reuses the saved value. No pre-publication
   password-retention guarantee or early document write is needed.

No plaintext enters project files, snapshots, plans, logs or diagnostics.
Target-free Resolve/Project Verify/Plan never perform RNG or secret/network reads.
Verify playbooks, hooks and task sequence remain unchanged, including their
ordinary existing Vault-source reads where applicable.

## Owner amendment: Vault paths without project ID

During implementation the owner explicitly requested removing project ID from
all managed secret paths and Agent references, e.g. `secret/data/sdku-dm/shared`.
Use `<libraryId>/shared` and `<libraryId>/<instanceId>/accounts/<accountId>` as
KV document paths in the existing mount. Build writes, reads, policies, Agent
templates and runtime source jobs from those same Core locations. No React/Go
path calculator or new editable path setting. Explicit external `vault_ref`
locations are unchanged; never rewrite an operator's external source path.

Keep project identity in ownership markers and opaque identity/ref hashes; it is
not part of KV locations or Agent secret references. Same paths owned by another
project block before mutation. Do not add cross-project adoption or migration
that bypasses ownership. Existing project-prefixed documents are retained and
not deleted, renamed or silently used as fallback. Next approved Apply publishes
the new paths using normal provider/Vault reconciliation; no infrastructure
credentials or paths are changed. Validate both shared/account locations and
actual Agent templates, not just the document projection. This is an explicit
owner-approved public path amendment to include in independent review.
If a generated password was stored only at an old project-prefixed location,
it is not automatically recovered from there: the new location may receive a
fresh generated value and the approved managed-password reconciliation sets
that value. The old document remains untouched. This transition can therefore
change the application password as well as its Vault location.

## General managed-password reconciliation during Apply

Only an established credential mismatch permits a password update. Network,
TLS, provider/admin access, permission, ownership and unknown errors still block.
Confirm login after mutation. Never repeatedly rewrite a matching password,
change unrelated privileges or delete/recreate accounts to fix login.

| Provider | Bounded change in existing Apply hooks |
| --- | --- |
| PostgreSQL | Keep role-marker/attribute preflight. Capture only explicit password-authentication mismatch for owned managed roles; distinguish transport/TLS/HBA/permission errors. In the current locked account SQL session recheck ownership and ALTER ROLE PASSWORD only for mismatches. Keep SCRAM/log suppression/protected inputs and final login. |
| Redis/Sentinel | Keep member lock, private ACL path and witness. Separate password-hash mismatch from flags/selectors/grant drift. Preflight permits pending password changes without mutation; Apply uses resetpass plus the desired hash, retains valid ACL/grant reconciliation, authenticates and ACL SAVE. Existing/verify behavior stays strict. |
| ClickHouse | Keep per-member witness/UUID checks and existing native error codes. Only explicit authentication failure (516) for managed accounts becomes pending update; other errors remain fatal. Existing account batch uses ALTER USER with desired SHA256 verifier and supported cluster scope, then final per-member login. Preserve grants and identity. |
| Kafka | There is no independent persistent ownership marker today: password possession is the existing adoption guard. The new rule replaces that guard for an exactly declared managed principal: administrative credentials plus managed declaration authorize setting SCRAM-SHA-512 on explicit SASL authentication mismatch. This can reset an existing matching-name principal whose old password is unknown. Keep reserved-name, exact identity, supported-mechanism, target/TLS, admin-auth and ACL-scope checks. Unknown/network/TLS errors do not trigger reset. Reauthenticate before grants/publication. Existing mode and Verify remain read-only. |

Kafka's changed authority is a material security-contract decision exposed for
explicit owner approval. Do not claim previous password possession after this
change or invent a Kafka witness store. Extend existing bounded functions/tasks;
no generic rotation framework. Shared helpers may take Apply-only inputs with
defaults retaining current strict behavior, without new Verify-specific branches.

Owner decision (2026-10-21): after the question explicitly covered standalone
Ansible and different Execution Nodes, the owner stated that two simultaneous
installations are not expected. The supported execution contract is one Apply
of a project at a time across UI, standalone and all Execution Nodes, for the
entire password selection -> provider hooks -> Vault publication interval.
The operator/caller serializes invocations; concurrent Applies of that project
are outside supported scope for both generated and manual passwords. This is
an operational prerequisite, not a claim of a new enforced cross-node lock.
Keep existing locks/CAS; no new coordination feature or blocker is implemented.
Do not report success if final login with the selected password fails. A later
serialized Apply converges after partial updates when ownership is confirmed.

## Existing UI

Reuse source selector and draft/Review/Save. Generated has no inline value; explain
creation during Apply and saved-value reuse. No client generator or new API.
Offer generated only for password fields. Session availability must not imply a
generated password exists. Keep Core findings on the existing flow. The Secrets
mockup already offers generated without inline replacement; readiness is the
discrepancy, not a new screen or editable KV mapping.

## Validation and gates

- Focused projection/generator tests: unique refs, logical-account deduplication,
  all providers, unsupported mode/missing Vault/publication path, saved reuse,
  secure files, unchanged other sources and no target-free RNG/network.
- Current-tree RED OS native Ansible QA: first generated Apply, unchanged repeat,
  manual A-to-B change, saved reuse, interruption after account change before
  publication, retry convergence, existing-mode rejection; all four providers
  and Sentinel. Privately compare values; evidence contains booleans only.
- Exercise these flows with serialized invocations under the owner's supported
  execution contract. Do not claim concurrent Apply safety. Distinguish failure
  after a completed hook from interruption before first ownership persistence.
- Negative QA: foreign owner/UUID/witness, reserved principal, wrong admin,
  network/TLS/non-auth errors never authorize password updates. Kafka declared
  managed unknown-password reset is a positive case under the new authority.
- Update old Apply tests expecting password drift to block. Run existing affected
  Verify regressions unchanged; add no Verify functionality or Verify-specific
  tests.
- Real React/Wails handlers: select generated, save/reopen, exact Project Verify,
  fresh plan and approved controlled Apply on disposable accounts, ordinary
  bindings/Agent delivery. No baseline-account reset or infrastructure Apply
  inferred from this plan. Record standalone/UI/visual acceptance separately.
- Follow QA/runtime-bundle procedures, run Core on RED OS, use current-tree
  sources and standard verified bundle publication for Wails tests. Main agent
  runs affected tests. FULL DIFF review is mandatory for password security changes.
- Update existing contracts, current state and journal with actual evidence;
  tests and PLAN review alone do not prove acceptance.

## Review and owner gate

Revision 2 follows a materially changed explicit owner architecture instruction;
review.md permits one new FULL PLAN review for that changed scope. Implementation
waits for concrete-plan owner approval, particularly Kafka authority. BLOCK stops
and returns findings without an automatic redesign/review convergence loop.
