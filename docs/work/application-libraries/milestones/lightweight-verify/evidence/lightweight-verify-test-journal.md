# Lightweight application Verify — 2026-10-10

Owner authorized only image identity, project/library/instance/host ownership,
Running and configured healthcheck, with minimum tasks. Runtime Verify now has
one native command task per instance (bounded retries only for readiness).
Standalone Verify resolves existing controller inputs and discovers passwd once
per target, without target preflight, registry probes, archives, filesystem,
port checks or Compose processes. Apply keeps full preflight and activation.
File/config drift detection is intentionally outside ordinary Verify.

Independent FULL DIFF: APPROVE_WITH_CHANGES, zero blockers. Base ae3002907842bcdf8700bfb78305fe64d7c7e3c9;
five-file review fingerprint 0358a801734cb1abb86804fd4aa62ba536b130f32edd5276816c041f814ef1c7.
LV-D01 documentation synchronization completed (Core contract and A2 plan).
LV-D02 remains nonblocking: combined inspect conditions for missing/stopped,
wrong-image and foreign-label native negatives were reviewed but not all
exercised in this bounded QA. No repeated independent review.

RED OS current-source workspace a48516a562584625b8cda0a51d3baecd,
verified using scripts/qa-sync.ps1; platform-automation identity and sudo -n.
Native test_01 PASS (73.557s): Apply 36.384s, standalone Verify 2.531s,
repeat Apply 31.474s; two containers, changed=0 Verify/repeat, IDs preserved.
One measurement; no 10/30-container SLA or cross-run performance ratio claimed.
Initial test_06 FAILED (172.733s): unhealthy Apply incorrectly succeeded because
readiness was only in until while failed_when could overwrite failure.
Corrected the same task: all identity/readiness failures in failed_when;
until uses the resulting failure flag. This bounded QA correction is after the
review fingerprint; no repeat independent review claimed.
RED OS six-case actual Ansible task predicate check PASS: healthy, wrong image,
foreign ownership, stopped, unhealthy and missing command result. Command output
was substituted; this supplements real Docker QA, not native identity acceptance.
Fresh verified source 779ba1554ed64e9ca7cdeb692396859d; real healthcheck re-run
PASS: test_06 172.830s; healthy Verify 3.344s, unhealthy Verify correctly fails
18.873s, remains read-only (container states unchanged). Both temporary remote
source workspaces cleaned via standard qa-sync cleanup; fixture-owned containers
and runtime roots cleaned by test lifecycle. IDs: test01 a2qa-796xoyaf, initial
failed healthcase a2qa-igsi7ocz, corrected healthcase a2qa-kgylqu4u.
Scoped diff --check PASS. No Go/UI or release acceptance.
