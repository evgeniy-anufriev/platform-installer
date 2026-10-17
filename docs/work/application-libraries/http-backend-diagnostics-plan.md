# Safe HTTP backend diagnostics

Owner request 2026-10-17: expose address, expected and actual HTTP status,
configured timeout and failure reason in normal execution, without secrets,
cookies or response bodies. Owner correction: use Ansible tasks rather than
introducing Python scripts/action plugins where built-in tasks suffice.

Implementation: check_targets.yml includes check_http_target.yml for each
plain HTTP target. The include and builtin uri request use no_log to suppress
original loop metadata and the raw request/response. A separate builtin assert
exposes only host/port, numeric expected/actual status and timeout, plus a closed
reason classification. No raw message, URL path/query/userinfo, headers,
cookies or body is copied to its message. Unknown failures use REQUEST_FAILED;
unavailable status is -1. Existing Host, timeout, no redirects and expected
status behavior remain. A failed assertion blocks publication.

The existing Core callback recognizes only the tagged builtin assertion and a
bounded closed diagnostic grammar, publishing existing DIAGNOSTIC events for
success and failure. No new Python file, DTO, event schema, persistence layer
or UI logic. Explicit no_log still suppresses journal messages.

Focused RED OS QA uses the production tasks with local HTTP200/503, redirect,
timeout and secret sentinels in request metadata, body, cookies and redirect.
Existing HTTPS checks remain unchanged. Callback tests cover journal
success/failure, no_log and rejection of unrelated/arbitrary messages.
No deployment, bundle publication or runtime activation is in this change.

Earlier FULL PLAN review APPROVE_WITH_CHANGES (zero blockers) applied to the
superseded action-wrapper proposal, SHA256
170e6dfc0a9fc43f6ff1e858ecb2b6644a75b97aab5c033386cb475ea8f8c2be.
HTTP-P01 (raw loop item leakage) is addressed by a no_log include and a separate
non-loop assertion, tested at -vvv. HTTP-P02 action-specific restoration and
nested-exception concerns no longer apply: only builtin modules are used.
Final independent FULL DIFF review covers the revised logging boundary.

HTTP-D01 correction authorized by owner reply "разрешаю": removed the assertion's
explicit no_log:false. The private include suppresses its loop metadata without
forcing suppression on the included assertion. The assertion now inherits an
operator's play/block no_log normally. Native production-task + real callback
checks cover ordinary HTTP200/503/redirect/timeout and play/block suppression
for HTTP200/503. Valid private journals ensure actual TASK_COMPLETED events
exist before checking diagnostic presence/absence. HTTP503 still exits2.
RED OS current-tree native tests PASS22.253s (2 tests, including unchanged HTTPS
positive/negative); callback/journal PASS1.582s (27 tests, 4 isolated-root skips).
The temporary source workspace was verified and cleaned with qa-sync.
TARGETED_RECHECK of HTTP-D01 requested; no source activation or deployment.

TARGETED_RECHECK HTTP-D01 APPROVE; zero blockers. See reviews/http-backend-diagnostics-diff-review.md.
