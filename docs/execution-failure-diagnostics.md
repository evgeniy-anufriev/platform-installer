# Bounded execution failure diagnostics

Owner-authorized diagnostic correction, 2026-09-27. No service rules, retry
policy, public protocol, callback result payload or runtime trust change.

The existing controller retains at most 32768 bytes of child output in memory.
An explicit Core error_code remains authoritative for diagnostics. Otherwise,
only the final ordinary, single-line Ansible fatal FAILED/UNREACHABLE JSON
record is inspected. Earlier successful task messages cannot select a class.
Malformed/multiline/unsupported output is not guessed or exposed.

Closed fallback classes: ANSIBLE_BECOME_TIMEOUT, ANSIBLE_BECOME_FAILED,
ANSIBLE_SSH_AUTH_FAILED, ANSIBLE_CONNECTION_TIMEOUT, ANSIBLE_CONNECTION_LOST,
ANSIBLE_FILESYSTEM_READ_ONLY, ANSIBLE_FILESYSTEM_FULL,
ANSIBLE_PERMISSION_DENIED, ANSIBLE_FAILURE_REDACTED and
ANSIBLE_FAILURE_UNCLASSIFIED. These are coarse diagnostic hints, not proof of
root cause or authority for retries. Censored/no_log records remain opaque.
The existing redacted operation DIAGNOSTIC carries the code in its safe summary;
stdout/stderr, result messages, variables and secrets are never persisted.

RED OS current-source QA: 6 new tests PASS (0.070s), task observability 21 PASS
and 4 opt-in SKIP (0.539s), execution lifecycle 39 PASS (1.491s). Coverage includes
closed classes, final-record selection, explicit-code priority, capture bound,
malformed/no_log records and real subprocess drain with synthetic-secret
non-leakage into the journal. Full Go tests, vet and diff check PASS.
qa-sync workspace was cleaned. No target deployment was run during these tests.

Separately, the previously failed audit-directory task was invoked alone in
normal mode via SSH/elevation and NoNewPrivileges: PASS changed=false, 5.724s.
Directory identity, inactive Vault unit and committed journal remained unchanged.
Permanent execution identity was used instead of the removed temporary QA key;
the historical failure therefore remains unexplained.

## Immutable runtime and real React/Wails evidence

Published/activated through supported promotion: runtime
sha256:9752977101218636e21af54fc8ca38fc2689b6b04218cf598a2258874b1bd0db,
isolated project revision
sha256:1b5ac63e9dec173990ef8b063df15c9540d8e18e3a50318d957590fc8fb13c79.
Catalog unchanged. Actual React handlers -> real Wails bindings -> readiness,
fresh plan, approval and Start produced run
installer-6989b0f2fb6c2609515170ece9c9eeb7. The original audit task passed.
Run terminated FAILED at sequence 670 on a later no_log task; the new controller
published ANSIBLE_FAILURE_REDACTED, not raw error or secret material. The known
headless wails/ipc.js error remains; bridge behavior is not a clean-WebView claim.

The newly identified service blocker is seed cluster_id capture before unseal:
sealed initialized health returns HTTP 503 with cluster_id absent. Init output
custody files exist; recovery record was removed. No contents were disclosed.
SI08-E is BLOCKED, not DONE. No new init, reset or full-plan retry was performed.
Temporary RSA admission removed; dev servers stopped; committed journals and
custody retained. No historical error text is claimed recovered.

Additional current-source gates: full Core 393 total / 374 PASS / 19 SKIP,
380.146s; privileged Vault-clear suite 18 PASS, 8.641s; catalog/schema
reproducibility PASS. qa-sync workspace cleaned. Full Go tests/vet and diff check
passed in the preceding focused correction gate.
