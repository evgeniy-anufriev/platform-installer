# Vault clear implementation evidence — 2026-09-27

Owner approved `docs/service-install-08e-clear.md`. Scope: explicit standalone
Ansible Raft clear only, not uninstall or automatic recovery. New tasks/module
are not wired into ordinary apply/verify or service execution.

## Implementation

- `services/vault/playbooks/clear.yml`: linear standalone entry, fatal errors.
- `roles/vault_tls/tasks/clear_entry.yml`: existing validation/normalization,
  exact deployment acknowledgement, existing deployment flock/always release.
- `roles/vault_tls/tasks/clear.yml`: inspect every selected local member before
  stopping only their exact units, then freshly revalidate and clear contents.
- `plugins/modules/clear_member.py`: fixed role paths/unit formula, no-follow
  held directory/file ownership validation, bounded private marker and matching
  config/unit/loaded-systemd evidence. Stop/process guard before deletion.
  Linux private mount namespace prevents external mount propagation; complete
  bounded mountinfo inspection rejects subtree mounts, including bind mounts.
  Only Vault-specific no-follow fd-relative traversal with opened mount-identity
  checks is permitted. Root,
  marker, config, TLS, audit, custody, packages/accounts and journals are kept.
- Exact confirmation default is empty; missing or wrong acknowledgement blocks.
  Check mode inspects only; no lock or unit mutation. README documents usage,
  prerequisites, stale custody and non-transactional partial-clear failure.

## Tests/gates

Current source transferred by scripts/qa-sync.ps1 to
`/var/tmp/platform-installer-qa-ab91cdc1261d4f55bcf77b2b35020d6c`.
No production Vault clear occurred. Tests use temporary synthetic data in /run
and disposable subprocess mount namespaces. No tokens/shares/private keys read.

- `sudo -n env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s ansible-core/tests -p test_vault_clear.py -v`:
  15 PASS, 1.819s. Exact identity/confirmation, real Ansible negative admission,
  ownership/type/mode/size, marker/unit/config mismatch, loaded-unit mismatch,
  source replacement before/during deletion, inner symlinks, partial failure,
  namespace/deletion capability refusal, actual nested bind/tmpfs mounts,
  retained resources and empty repeat changed=0 are covered.
- Vault role contract: 15 PASS, 0.422s.
- Standalone clear syntax-check: PASS. Inventory without platform_targets emits
  the expected unmatched-host warning; syntax check is not deployment proof.
- Independent QA full Core: 384 total, 380 PASS, 4 opt-in skips, no failures or
  errors; 177.032s. Catalog and service configuration schema --check PASS.
- `go test ./...`, `go vet ./...`, `git diff --check`: PASS.
- Scoped secret-safety inspection: helper diagnostics are fixed codes, do not
  return config/marker contents or tracebacks; clear consumes no secret input.
- Actual existing member module inspection through sudo/Python:
  deployment `vault`, member `vault-1`, inspect_only=true -> changed=false,
  no unit stop or data deletion. This is inspection only, not reset acceptance.
- Frontend/Wails/RED OS Go race: unaffected by this Ansible-only change. No
  React/Wails acceptance is claimed; SI08-E still requires its existing real
  integration and deployment gates after the reset prerequisite is satisfied.

## FULL DIFF review stopped on envelope identity

Reviewer: architecture-reviewer, base
`3e1f711ca6b8c6c0445c88e6739a4fd40884dbdb`, reviewed plan
`7035a2f9c1f3e6004b053c170947b24853405fb49444ed103df3704e914b4ebb`.

SI08-CLEAR-DIFF-01 BLOCKING/OPEN: parent supplied an eight-file fingerprint
computed with cultural PowerShell Sort-Object while declaring ordinal sorting.
Reviewer computed ordinal fingerprint twice. Read-only parent reconciliation
with `[Array]::Sort(paths, [StringComparer]::Ordinal)` matches reviewer exactly.
All individual file hashes are unchanged; independent remote QA verified the
seven transferred implementation files match their local hashes.

Correct ordinal fingerprint:
`86df9179819d462aaa11813072c70ec9645be9a643a522b7e8e7ef3a872f37e3`.
It is SHA-256 over UTF-8 LF-joined ordinal-sorted relative `path:sha256` rows,
without trailing newline. Scope: test_vault_clear.py, clear plan, helper,
defaults/main.yml, tasks/clear_entry.yml, tasks/clear.yml, playbooks/clear.yml,
Vault README. README/defaults review scope excludes earlier unrelated changes.

This explains the envelope error but does not mark the review finding resolved.
No automatic re-review, commit, promotion or actual clear. Owner authorization
is required to continue the incomplete DIFF review using corrected identity.

## Owner-authorized continuation of SAME FULL DIFF

Owner requested commit and continuation. The reviewer completed the interrupted
review on the same unchanged eight-file fingerprint above. No new PLAN cycle.
SI08-CLEAR-DIFF-01 OPEN -> RESOLVED: ordinal fingerprint and individual hashes
are established. Verdict BLOCK, two unresolved implementation safety findings:

- SI08-CLEAR-DIFF-02: process scan checks exact config arguments only when
  basename(argv[0]) is vault. Alternate caller-selected argv[0] can bypass the
  stopped-member prerequisite. Smallest correction: reject either exact config
  argument form independently of executable name. Add real scanner tests with
  normal/alternate argv[0], both config forms and unrelated config.
- SI08-CLEAR-DIFF-03: private mount propagation plus a one-time mountinfo check
  does not prevent filesystem rename of an enclosing directory with an inherited
  nested mount into the deletion subtree afterward. Recursive traversal does
  not check descriptor mount identity. This is a static reviewer counterexample,
  not an experimentally reproduced deletion. Smallest correction: enforce
  mount identity on every opened directory before descent and bind traversal to
  those descriptors; st_dev alone is insufficient for same-filesystem bind
  mounts. Add synchronized nested bind/tmpfs movement test after admission.

Zero overengineering findings. Parent-reported tests were not re-executed by
the reviewer. No actual clear, commit or automatic correction/re-review; owner
approval of these bounded corrections is pending. Regression PASS is not proof
of the two missing safety cases.

Separate read-only QA reset identity proof confirmed failed run
installer-b095002168ac83f7fb1aa9289f7120cb belongs to project-76b046511af5faed,
operation apply:vault-qa-standalone, member vault-1. Existing role deployment is
vault, yielding the exact marker/config/data/unit identity; public and role names
were not presumed equivalent. Active Installer runs and Vault lock holders were
zero at inspection. Journals, packages, custody and Raft data were not changed.

## Owner-authorized exact corrections and targeted recheck

SI08-CLEAR-DIFF-02 now rejects both exact config forms independently of argv[0].
The real process scanner test launches temporary children, confirms actual
normal/renamed argv[0], blocks both config forms and accepts an unrelated config.
SI08-CLEAR-DIFF-03 replaces unchecked recursive rmtree with the same Vault-only
module's no-follow fd traversal: opened inode and Linux mnt_id are checked before
listing/descent, recursion stays descriptor-relative, and directory identity is
rechecked before removal. Root and marker remain retained. Missing/malformed
mount evidence fails closed. No new framework, arbitrary path API or lifecycle.

The synchronized bind/tmpfs movement regression runs entirely in a disposable
mount namespace: after initial mount admission, a worker renames an enclosing
directory with an inherited nested mount into the deletion subtree. Clear fails
before mounted contents are traversed and retains mounted sentinels. Existing
symlink/root replacement/partial-failure/preservation/repeat tests remain.

Corrected source was synced to
`/var/tmp/platform-installer-qa-b2ee3af8cb094158bae01feeaacd5105`:

- Focused clear: 18 PASS, 1.839s.
- Vault role contract: 15 PASS, 0.515s; standalone clear syntax PASS.
- Independent full Core: 387 total, 383 PASS, 4 opt-in skips, 0 errors/failures,
  174.730s. Catalog/schema reproducibility PASS.
- Full Go tests/vet and git diff --check PASS; Go code was not changed.
- Helper SHA-256: `4fb63760360410dfe30df6e0b39aef0f1a0615a5c484cd703b55afcd0f295e31`.
- Test SHA-256: `6a60d77db9ac89356374e00d0517f0663992e9c4ce4d1b4064c0df49fde1fd40`.
  Remote QA verified these hashes after suite completion.
- QA workspace cleaned using scripts/qa-sync.ps1. No actual reset occurred.

One architecture-reviewer TARGETED_RECHECK: APPROVE. DIFF-01 stays RESOLVED;
DIFF-02 and DIFF-03 OPEN -> RESOLVED; no new adjacent blockers, zero blocking
or overengineering findings. Base `3e1f711ca6b8c6c0445c88e6739a4fd40884dbdb`,
reviewed amended plan SHA-256
`cf09415485c8ab3346752035238e17179deeba04f63efd9ba17c15dd364d5206`, reviewed
eight-file ordinal fingerprint
`1f30018aa7b9db71f591dfe54b28117608b38e73bc50bb359163301a7baead5a`.
This approves the corrected implementation boundary, not actual reset or
SI08-E deployment acceptance. No further review cycle is requested.
