# Vault explicit Ansible clear

Document scope: the original milestone contract and constraints. Historical
results are linked separately; current status and authorization are recorded
only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Owner requested clear tasks analogous to Kafka/PostgreSQL. Scope is explicit
destructive Raft reset, not uninstall, runtime promotion or automatic recovery.
Normal apply/verify remain unchanged. No clear is executed during implementation.

## Entry and authority

`services/vault/playbooks/clear.yml` accepts ordinary documented Vault variables.
It validates/normalizes the existing member model, requires
`platform_vault_confirm_destructive_reset == platform_vault_deployment_id`,
acquires the existing target-side deployment flock, and always releases it.
No Core, PKI, secrets, lease or Installer dependency is needed. The caller must
stop active Installer runs before invoking clear. Lock contention fails closed.

Every selected local member must pass ownership validation before any selected
unit is stopped. Exact service unit identity and configuration path must match;
the root-owned unit must have the existing managed identity header. No glob,
default vault.service stop, package/account removal or process-wide kill.
After exact unit stop/disable, require inactive/failed state, zero MainPID and
no Vault process with the exact member config argument before data mutation.
The config-argument guard is independent of caller-selected argv[0]; another
process mentioning either exact config argument form is conservatively rejected.

## Narrow opened-directory reset

Built-in stat then recursive file deletion cannot prove same opened source
identity under namespace replacement. A Vault-only Ansible module is justified
for this missing operation; it is not a generic filesystem framework.
Its only inputs are deployment/member IDs, confirmation and inspect-only flag.
Paths and unit names derive by the existing role formula, not caller paths.

Walk fixed `/var/lib/platform-vault/<deployment>/<member>` using no-follow
directory-relative opens. Fixed ancestry must be root-owned and not group/other
writable. Member directory must be the service-owned private directory. Read the
bounded regular owner-private marker from that same held directory; require
exact apiVersion/deployment/member/instance identity. Validate the exact unit
through a bounded no-follow regular-file read and expected header/ExecStart.
Inspect-only results are not deletion authority. The destructive invocation
must freshly repeat complete ownership/unit/marker validation on the exact
held directory it uses, even if inspection succeeded before stopping units.

Clear preserves the member root and marker. Remove only immediate children via
the held directory using a Vault-only no-follow fd-relative traversal and
descriptor-relative unlink for non-directories. Check each opened directory's
Linux `mnt_id` against the held member mount before any listing/descent; st_dev
alone does not exclude same-filesystem bind mounts. Do not unlink or rename the
member root by pathname. No fallback if fd-relative operations or mount identity
evidence are absent. This is the owner-authorized DIFF-03 exact correction;
one-shot mount admission and symlink-resistant rmtree alone were insufficient.
Foreign substituted sibling/member directories must not be touched. Refuse
mount points before deletion. If source identity changes during clear, report
safe failure; never chase/retry cleanup through the replacement pathname.
Mount refusal covers the complete traversed subtree, including nested and
same-filesystem bind mounts. If this protection cannot be established, deletion
is blocked. Symlink resistance alone does not prove mount-boundary safety.
Partial deletion is not rolled back: report failure, preserve retained
resources and release the invocation's lock through the existing always block.

The role retains config, TLS/PKI, audit files, systemd unit, package/account,
controller custody, encrypted output packages and committed journals. Clear is
destructive: previous token/shares no longer describe the newly initialized
store. They must not be silently reused or erased by clear. Reinitialization
requires a fresh output namespace and existing bootstrap custody rules.

## QA

Owner approved implementation on 2026-09-27. Linux mount protection uses a
disposable per-module mount namespace (`unshare(CLONE_NEWNS)` followed by
recursive private propagation) before bounded `/proc/self/mountinfo` admission.
External new mount events cannot propagate into the isolated namespace. File
namespace renames are guarded separately by per-descriptor mount checks. No new
mounts or background helpers are created. This implements the approved mount
boundary; permission/runtime failure blocks clear with a fixed safe code.

Test exact confirmation, malformed IDs, unit/config/marker mismatch, symlinked
ancestry/marker, service/root ownership/modes, process guard and unsupported
safe-delete runtime. With synthetic temporary trees prove data removal and
unchanged marker/config/audit/unrelated siblings, repeated empty clear changed=0,
root replacement leaves replacement intact, inner symlinks never affect their
targets, mount refusal, no root removal and bounded safe errors/no secret output.
Cover replacement both between inspect-only and destructive invocation and
during deletion, interruption after partial deletion, nested mounts and
same-filesystem bind mounts with mounted contents preserved.
Run RED OS focused unit/role tests, standalone clear syntax-check, full affected
Core regression and diff check. Independent PLAN and high-risk DIFF review
apply to this narrowly scoped new destructive operation.

## PLAN review

Recorded evidence: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#service-install-08e-clear-reconciliation-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).

The PLAN review does not establish the
implementation as safe or complete; independent DIFF and QA gates remain.
