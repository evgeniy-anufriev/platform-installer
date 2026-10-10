# A3 FULL DIFF review — 2026-10-10

Independent architecture-reviewer verdict: **BLOCK**. Initial FULL DIFF;
TARGETED_RECHECK not performed. Corrections require owner decision.

Worktree: `codex/application-libraries`, HEAD
`f3ba74c9133582cad21ecc794ee09dd709214571`.
Reviewed uncommitted fingerprint:
`d48e8b173cf3d340f82ff2ce9da857f945e7c31feb8a36533d15de1ca8cea1f3`.
Method: sorted 70 changed/new files, `relative-path SHA256(file-bytes)` lines,
UTF-8/LF with final LF. Later review/journal/state documentation is excluded
from this historical fingerprint; production templates remain unchanged.

Owner scope: additive explicit grants, no global ACL audit/revocation;
one resource batch/library and one account batch/instance; shared discovery;
no benchmark. Consolidated preflight template was reviewed.

## Findings

- **A3-D01 BLOCKING OPEN:** `tasks/login.yml` uses maintenance `postgres` for
  existing-account authentication. Accounts only probe newly created users
  after grants; Verify has no application-database authenticated probe.
  Existing users limited to their application DB can be rejected, and differing
  per-database HBA can invalidate credential proof. Smallest fix: existing-mode
  authentication on declared DB and final declared-DB login for all accounts,
  reusing login.yml. Test limited CONNECT and differing HBA/wrong password.
- **A3-D02 BLOCKING OPEN:** full Core resolve → preflight → apply → verify
  entrypoint and native primary/standby acceptance remain absent. Role harness
  is supplementary. Provide functional one/zero/two writable and unavailable
  candidate evidence; benchmark/full pg_auto_failover installation not required.
- **A3-D03 NON_BLOCKING OPEN:** openssl prerequisite probe has no deadline.
  Bound it with standard existing command facilities; test stalled TLS peer.
- **A3-D04 NON_BLOCKING OPEN:** prepare_application_providers.py computes
  candidate.roleVariables without a current consumer. Remove unused projection
  or identify a concrete consumer; avoid speculative future abstraction.

Overengineering blockers: zero. Existing Ansible, psql, templates, markers and
session locks are appropriate. Shared database.sql.j2 is justified; no new
architecture layer is needed. Reviewer did not run tests or contact targets.

Recommendation: resolve D01 and supply D02 evidence after owner approval,
then request the single owner-approved targeted recheck. No automatic fixes
performed after BLOCK.

Owner approved D01–D04 corrections and one TARGETED_RECHECK for D01–D02 on 2026-10-10. Corrections implemented; functional evidence/recheck pending.


## Owner-approved TARGETED_RECHECK — 2026-10-10

Independent verdict **APPROVE**, zero unresolved blocking findings in scope.
A3-D01 and A3-D02 RESOLVED. No second FULL review performed; FULL + one
TARGETED_RECHECK automatic budget exhausted.

Final reviewed content fingerprint:
`c9633b054ff1a22f0fd95a132b6b5cb6dd313620f2714a54c29bad2beb1bad76`.
Same sorted path/hash method, 72 changed/new files, HEAD f3ba74c.

Reviewer inspected declared-DB login branches, authenticated SELECT1 after Apply
and in Verify, existing PKI owner convention with postgres administrative SQL,
full production entrypoint fixture and native primary/standby fixture.
Native results were supplied by parent, not independently rerun by reviewer.

D03/D04 are outside formal recheck IDs; timeout and unused-projection fixes are
implemented, without a claim of a separate formal re-review. No new complexity
mechanisms or adjacent blocking auth/PKI regression found. Bounded regression
and cleanup remain separate completion gates. No Go/UI/master/release permission.
