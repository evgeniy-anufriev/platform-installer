# B0 — owner-authorized regression test and fixture repair

Owner request: correct stale tests/fixtures, isolate native PKI from the system
trust store, reach full Core regression PASS without weakening checks or changing
working logic for tests. Scope is tests, valid examples, generated schema ordering
and evidence; no service installation, Go/UI, bundle publication or commit.

## Corrections

- Kafka CLI fixture now supplies the ordinary role name used by the tempfile task.
  Managed Kafka expectations distinguish deployment data roots on separate hosts
  from member subdirectories on co-located hosts; log/config assertions remain.
  Standalone imports explicitly expose the existing module_utils dependency path.
- PostgreSQL resource-default assertion includes the documented /postgres suffix.
- Redis consumer fixture supplies unchanged peer-user/password change observations
  used by the real Sentinel restart condition. File corruption/repeat assertions
  and activation observations are retained.
- Vault template fixture loads actual role defaults. Directory assertions specify
  the exact config/log parent paths, while standalone data_directory is already the
  deployment data root. Root-native proof retains no-write parent checks and adds
  service-user traversal/write checks on its private data/config directories.
- Core valid and PostgreSQL standalone examples use inventory-owned members and
  ordinary platform_desired_state. Valid Kafka examples select the catalog's current
  definitionVersion. No invalid/negative fixture was converted to success.
- PostgreSQL configuration.schema.json regenerated through the standard generator;
  parsed JSON equality asserted before/after. Only key order changed.
- application-libraries README supplies catalog/project roots and required Redis/
  ClickHouse collection paths. With those documented inputs, ordinary validate.yml
  succeeds; no application or provider implementation correction was required.

## Native PKI isolation and retained coverage

The shared test-only pki_test_fixture helper copies the current pki_deploy role into
TemporaryDirectory and redirects only trust_anchors.yml filesystem destinations,
local ownership and the external system-refresh command. Actual Ansible copy,
assert/register/changed_when, deploy, integrity and repair tasks execute unchanged.
No production role defaults, paths, commands, algorithms or contract were altered.
The helper rejects an unexpected refresh command or residual system-anchor path.

The host updater is replaced only in that temporary role with a private refresh
marker. Tests assert exact CA bytes were copied and that integrity-only repeats and
repairs do not refresh trust. Existing corrupt/missing PEM/PKCS12, permission,
fingerprint, inaccessible source and clean-repeat checks remain. This is a file
integrity proof, not acceptance of the operating system's real trust updater.

Before the complete suite, 840 system trust metadata/hash entries were captured
under /etc/pki/ca-trust/source/anchors, /etc/pki/ca-trust/extracted and
/etc/pki/tls/certs. The post-run comparison must be identical.

No new skip, expectedFailure, removed test or relaxed failure return code was added.
Low-risk test/fixture corrections preserve the already reviewed B0 architecture;
the reviewed19-file implementation identity remains unchanged.

## Validation

- Corrected focused set:12 tests,11 PASS/1 existing root-only SKIP.
- Separate affected root-native Vault permission proof:2 PASS,17.231s.
- Catalog and configuration-schema reproducibility:PASS.
- Real target-free validate.yml:Core valid,Kafka single,PostgreSQL standalone,BIND,
  application-libraries with explicit documented provider collections:all PASS.
- Full current Core suite: **PASS**,685 tests,666 PASS/19 existing SKIP,0 failures,
  0 errors,1394.247s; no excluded native PKI cases. All34 B0 cases PASS inside it.
- Fresh offline B0 suite:34 PASS,4.940s under unshare -n.
- System trust store:840 metadata/hash entries byte-identical before/after; PASS.
- Existing skips unchanged:4 gated canonical-journal observability acceptance cases
  and15 root-only Vault filesystem/permission proofs. The affected Vault proof was
  additionally exercised as root and passed; skips are not counted as PASS.

Test/fixture20-file manifest SHA256:
a51c8c360ad5adaaee88a0d45d3579a6f513a817b87c84b531873aa2b3814ada.
Runtime evidence: .runtime/qa/b0/test-fix-identity.txt and the current QA journal.
The original FAILED regression and its attribution remain historical evidence.

## Final evidence and cleanup

[Structured result](b0-regression-repair-summary.json).15 safe evidence files retained
under .runtime/qa/b0/regression-repair and remote/local SHA256 equality verified.
qa-sync final source verification PASS. Reviewed B0 identity and20-file correction
manifest still match. Temporary remote QA source removed with qa-sync after exact
public-root ownership restoration; absence verified,0 owned QA processes remain.
No new review or production-logic change; original B0 review remains applicable to
its unchanged19-file scope. No commit/push or B1–B4/Go/UI work.
