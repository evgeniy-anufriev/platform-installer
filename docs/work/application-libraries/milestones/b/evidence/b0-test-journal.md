# B0 — implementation and QA journal

Owner approved the B plan and explicitly authorized B0 on 2026-10-14.
Implementation branch: `codex/application-libraries-b0`, base
`cee36a3f737f70eb10347f0e3c50bfed398bf188`. B1–B4/Go/UI are outside this implementation.
The approved [plan](../b-technical-plan.md) and its FULL PLAN review remain the scope.

## Implementation

- Fixed modes in new request/plan/manifest/capability versions; old mixed barrier retained.
- Existing plan action resolves the ordinary complete project first, then projects the
  requested fixed scope. No service resolver or Ansible precedence is duplicated.
- Node-owned bounded infrastructure index, per-run private Verify proofs, terminal
  source result/manifest validation, full configuration model and run-level generation.
- Start admission under the existing active-run lock, plus controller recheck; approved
  host key/account changes invalidate reuse. Local client caches are not authority.
- Explicit Verify-only excludes Apply and PKI materialization; library-only uses only
  runtime Vault input and the existing two application entrypoints.

## Focused RED OS evidence

Current source copied with `scripts/qa-sync.ps1`; persistent platform-automation
identity, strict host-key checking and sudo -n. No target service mutations performed.

Initial focused run exposed a new schema relative-ref/minItems error and a synthetic
metadata fixture missing runId. Corrected, rerun. Expanded lifecycle tests exposed
minimal fixture manifests without projectIdentity and an existing fake Journal lacking
root; fixtures/compatibility guard corrected.

- Expanded affected set: 97 tests PASS (3.770s), no failure.
- Later B0 focused/native set: 23 tests PASS (4.476s), including actual Ansible plan
  action on synthetic localhost data. This proves action/controller-side integration,
  not real infrastructure service verification or Go/UI acceptance.
- Final B0 focused/native set: 25 PASS8.831s; actual fixed controller/trust/projection/
  Ansible fixture Verify-only then independent library-only run. Exact action sets
  show no infrastructure Apply or repeated infrastructure Verify in the library run.
- Offline same25 PASS8.479s under unshare -n, including both native fixtures.
- Catalog reproducibility PASS, digest08cd1f4c1b77104b32d11841c8eab105b14099a636a3577fdfb26b7e7009ccaa.
- Configuration-schema --check reports PostgreSQL stale. Schema and generator blobs
  are identical to base; B0 does not modify service schema/generator inputs.
- validate.yml on legacy ansible-core/examples/valid, root kafka-single and root
  postgresql-standalone fixtures returns BLOCKED on pre-existing version/membership
  inputs. No fixture repair or successful controller validate gate is claimed.
- First broad run on intermediate sources interrupted after later B0 changes.
  Final-source full Core regression was stopped on independent review BLOCK;
  it had reported a failure in test_pki_single_pass.IntegrityTests.
  test_real_ansible_reuses_repairs_and_blocks_missing_source. Attribution was not
  investigated; no whole-suite PASS or final total is claimed.
- [Independent FULL DIFF](../reviews/b0-diff-review.md): BLOCK, four OPEN blockers
  B0-D01–D04, one nonblocking B0-D05. Exact18-file manifest SHA
  235d4596a1d89c3b35600b5c0c59bb86ece0c2781e04130dab10528a4714e970.
  No implementation file changed after that identity. Corrections/recheck await owner.

## Scope and limitations

No canonical Vault bootstrap, shared infrastructure data, images, containers or
existing historical A9 run outcomes changed. No new full infrastructure installation,
Go/UI implementation, runtime bundle publication or commit is part of this request.
QA workspaces are temporary and must be cleaned with qa-sync after evidence is retained.

## Stop and cleanup

On FULL DIFF BLOCK, implementation corrections and further acceptance were stopped.
Both self-launched full-regression processes were interrupted by exact verified PID;
read-only process-cwd audit found no remaining owned QA processes. Intermediate/final
interrupted logs and the immutable review file manifest were retained locally under
`.runtime/qa/b0/`. All nine source-copy workspaces were removed with qa-sync; six
required owner restoration on their exact public source roots after root-run tests
created bytecode directories. No symlink targets were followed by that restoration.
Final remote audit: nine owned QA workspaces, zero remaining. Reviewed18-file hashes
still match; no code correction after review. Whitespace check PASS. No commit/push.

## Owner-authorized B0-D01–D04 corrections

Owner subsequently authorized bounded corrections and revised D01: infrastructure
Verify is independent of SSH username. Current authentication, typed lease, approved
host keys and required privileges remain mandatory; a real resolved configuration
change still changes the infrastructure model. No security finding is waived by
owner acceptance; the corrected implementation undergoes the agreed single recheck.

- D01: remove account storage/comparison from evidence. Full _start_v2 test uses real
  staged host trust + typed lease and two distinct usernames, with one-shot/idempotent
  Start mapping; only systemd process launch is mocked.
- D02: latest Verify attempt supersedes prior success before execution; failed,
  skipped/incomplete or absent recap cannot restore old PASS. A stale publisher in
  the same generation cannot overwrite that newer attempt. Unknown/provider library
  failure revokes evidence before terminal; a trusted callback recognizes only the
  fixed managed instance-state predicate after successful Docker inspect as app-only.
  No stdout parsing or secret payload persistence. Mixed application suffix included.
- D03: begin, revocation and publisher read/check/write reuse .active-runs.lock.
  Deterministic concurrent tests cover new FAILED/CANCELLED generation and late
  publication after newer Verify in the same generation.
- D04: schema-valid bounded UNKNOWN summary when no executable base manifest;
  adjacent D05 closed object/types/enums/bounds added without a second DTO.

Final-source RED OS affected165:161 PASS/4 isolated observability SKIP,12.792s.
Offline B0 suite34 PASS9.968s under unshare -n, including actual localhost Ansible
action and fixed Verify-only→library-only controller fixture. No real infrastructure
installation or target service mutation. Broader bounded Core regression pending;
17 unchanged native PKI cases are explicitly excluded, not marked passed.

Corrected19-file identity SHA256:
5268325927c15fbbe21af4221283dbe98aa35d915a3e83233cd91651566defb1.
Owner-addendum plan SHA256:
a831e85165db407e1300e74f848e0e678a2f281702b21b6b4647230b37b2bce2.
Single TARGETED_RECHECK B0-D01–D04 requested; no new FULL review. Original BLOCK
report and original identity retained. No RESOLVED verdict claimed before recheck.

## Corrected review result and QA limit

Sole independent [TARGETED_RECHECK](../reviews/b0-diff-targeted-recheck.md): APPROVE,
zero unresolved blockers. D01–D04 and adjacent D05 RESOLVED for corrected19-file
identity above. Historical FULL BLOCK retained. Review budget consumed.

Broader bounded regression was interrupted after multiple failure indicators; its
17 excluded native PKI cases are not PASS. The interrupted output does not provide
complete per-failure diagnostics, so no baseline attribution or aggregate verdict
is asserted. Safe log retained locally at
`.runtime/qa/b0/corrections-bounded-regression-interrupted.log`.
Focused161 PASS/4 SKIP and offline34 PASS remain valid, not full acceptance.

Exact self-launched runner stopped after PID/cwd/command verification. Four own
public source workspaces (a46733…,9dd82f…,d06edd…,d13c3d…) cleaned through qa-sync
after safe log retention and exact public-root ownership restoration. No target
service mutations, shared infrastructure changes, commit or push. B0 remains open
for broader QA disposition; B1–B4/Go/UI not started.

## Owner-requested regression attribution and completed B0 QA

Owner explicitly requested investigation of all broad-regression errors and
separation of B0 regressions from existing failures. Current source and base
cee36a3f737f70eb10347f0e3c50bfed398bf188 were copied with qa-sync.
[Attribution](b0-regression-triage.md),[structured summary](b0-regression-summary.json).

Full current RED OS suite reached terminal:685 cases,658 PASS,19 SKIP,8 failing
methods/15 failure records,0 errors; no current-suite native PKI exclusions.
All eight failing methods reproduce before B0 (635-case bounded base plus two
failed native case reproductions). Base-only synthetic Journal.root error passes
with the corrected B0 fixture. No new B0 failure; all34 B0 cases PASS in full discovery.
Previous affected161 PASS/4 SKIP,offline34 and targeted APPROVE remain applicable.
The19 skips are4 explicit isolated canonical-journal acceptance and15 root-only
Vault filesystem/permission proofs, not successful acceptance.

Old failures are incomplete/outdated Kafka/Redis/Vault/PostgreSQL fixtures and
unisolated native system-CA trust tests. Configuration schema differs only by
JSON key ordering; old validation fixtures fail identically. Real current BIND
validate.yml and catalog reproducibility PASS on both trees. No old failure is
retroactively marked PASS; no repository-wide clean PASS is claimed.

B0 standalone Core QA is complete with known baseline defects separated; B1–B4,
Go/UI and service installation remain outside scope. No production/test-source
correction during triage; reviewed19-file identity remains exact.15 safe evidence
files copied locally and SHA256 verified. Final qa-sync source verification PASS.
Two remote QA workspaces and one clean temporary local baseline worktree removed;
remote absence/process audit PASS. No shared infrastructure/canonical custody
mutation, commit or push.

## Owner-authorized regression corrections — PASS

Owner explicitly authorized stale test/fixture repair and native PKI isolation,
requiring no weakened checks and no working-logic changes. Scope/proof details:
[repair](b0-regression-repair.md),[summary](b0-regression-repair-summary.json).

Current full RED OS suite:685 tests,666 PASS/19 unchanged SKIP,0 failures/errors,
1394.247s. No native PKI exclusions; all34 B0 cases PASS inside full discovery.
Corrected focused set12:11 PASS/1 existing root-only SKIP; separate affected Vault
root permission proof2 PASS17.231s. Fresh offline B0 suite34 PASS4.940s under unshare -n.
Catalog and configuration-schema reproducibility PASS. Real target-free validate.yml
PASS for Core valid,Kafka single,PostgreSQL standalone,BIND and application-libraries
with documented provider collections/catalog/project inputs.

No added skips, expected failures, removed cases or softened failure return codes.
PKI test-only copied role redirects only system-anchor destinations/ownership and
external trust refresh; actual copy/deploy/integrity/repair execute. Exact CA-copy
and no-refresh-on-integrity-repeat checks added.840 system trust metadata/hash
entries before/after are identical. Production role/Core algorithms unchanged;
PostgreSQL generated schema differs only in JSON key order (semantic equality proven).

Reviewed B0 19-file identity52683259…66defb1 unchanged; low-risk test/fixture20-file
identitya51c8c36…3814ada separately frozen. Original BLOCK/failed-regression records
remain historical.15 safe evidence files SHA256 verified and retained locally.
Final qa-sync source verification PASS;1 temporary remote QA source workspace
removed with qa-sync and absence verified,0 owned QA processes. No shared service
reset/install, canonical custody change, commit/push or B1–B4/Go/UI work.
