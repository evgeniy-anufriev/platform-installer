# HTTP backend diagnostics — FULL DIFF review

2026-10-17. Independent read-only reviewer: library_common_plan_review.
Verdict BLOCK, one blocking finding. HEAD 8feb047af1c24c70ede737fe03941b9bbf04ac3c.
Five scoped hashes matched .runtime/http-backend-diagnostics-review-scope.json.
Plan SHA256 b9ec71caec9677c61d14146a5e4e32b33322f2bd0cc08582b00d90fb317a0991.

HTTP-D01 BLOCKING OPEN: check_http_target.yml explicitly sets no_log:false
on its diagnostic assertion. This overrides an operator's inherited play/block
no_log:true. The callback sees false and publishes the safe diagnostic despite
the operator's suppression. The synthetic callback no_log unit test does not
exercise that production inheritance.

Smallest recommended correction: preserve inherited operator no_log instead
of forcing false, while keeping ordinary diagnostics enabled by default.
Use Ansible tasks; no Python wrapper is required. Native HTTP200 and HTTP503
cases must exercise outer play/block no_log:true, checking both stdout/stderr
and journal suppression, plus the unchanged failure barrier. Ordinary cases
must continue to expose only the safe fields.

HTTP-P01 RESOLVED: private include suppresses raw loop metadata; separate
assertion is not a loop. Native -vvv tests contain request/item/response sentinels.
HTTP-P02 SUPERSEDED for the removed action wrapper; outer suppression is now D01.
Overengineering: no findings; two builtin tasks and include are appropriate.
No new Python files, DTO/API/store/UI resolver or duplicate HTTP implementation.

Parent QA: current-tree RED OS .102 native HTTP200/503/redirect/timeout plus
HTTPS positive/negative: 2 tests PASS, 18.529s. Callback/journal 27 tests PASS,
0.580s, 4 isolated-root acceptance tests skipped. These checks do not close D01.
Source transfer verified with qa-sync; temporary QA workspace cleaned through
that helper. No bundle activation, deployment or real Wails acceptance of
this new diagnostics implementation. Existing SDKU runtime07 remains active.

Per review procedure, automatic corrective work stopped pending owner decision.
One owner-approved TARGETED_RECHECK may inspect D01 and its immediate boundary.

## Owner-authorized TARGETED_RECHECK — APPROVE

Owner reply "разрешаю" authorized correction and the one targeted recheck.
HTTP-D01 OPEN -> RESOLVED. Remaining blocking findings: 0.
Independent reviewer inspected only D01 and its immediate suppression boundary.
The assertion now inherits outer no_log; no new Python file/helper was added.
Corrected SHA256:
- check_http_target.yml: def2e7ab876a5a2c359717c2e81046a3beee32398eac378863a05d7bef078cfb
- test_backend_https_probe.py: bb92e19989a0d0f3de2d22d3662e58f08ee2c1c45c5d10ff2fe338b6b80490f6
The other three FULL-scope hashes are unchanged. Overengineering findings: 0.

Current-tree RED OS .102 QA: native2 PASS22.253s (eight HTTP cases plus unchanged
HTTPS positive/negative); callback/journal27 PASS1.582s (4 isolated-root skips).
Native tests exercise real production tasks and callback with valid private
journals: ordinary diagnostics present; play/block no_log suppresses console
and journal for both200/503; HTTP503 exits2; -vvv sentinels remain private.
qa-sync Verify and scoped diff check passed; temporary remote workspace cleaned.
Logs retained locally as .runtime/http-probe-tests-d01.log and
.runtime/http-callback-tests-d01.log. Corrected fingerprints retained in
.runtime/http-backend-diagnostics-d01-review-scope.json.

Reviewer directly checked code/tests/hashes, not remote test execution.
No additional review is required for this source-only request. New runtime bundle
publication/activation and real Wails acceptance of packaged diagnostics were
not performed; existing SDKU runtime07 deployment remains unchanged.
