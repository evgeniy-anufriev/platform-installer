# Historical documentation checkpoints

Extracted on 2026-10-12 from the original milestone documents. Recorded statuses,
versions, review verdicts and test outcomes describe their source scope and dates.
They do not override [CURRENT_STATE](../../../../CURRENT_STATE.md), authorize new
work or prove later acceptance. Requirements and planned QA remain in the source
documents. A moved evidence section retains its original wording and title.

## execution-node-password-auth-plan.md

Source document: [execution-node-password-auth-plan.md](../execution-node-password-auth-plan.md).

<a id="execution-node-password-auth-plan-checkpoint-001"></a>

## Targeted recheck outcome (2026-10-08)

Owner authorized EP-D01/EP-D02 corrections and the sudo-password extension, then confirmed the correction works and explicitly requested the recheck. Independent TARGETED_RECHECK BLOCK: EP-D01, EP-D02, EP-D03, EP-S01, EP-S02, EP-S03 resolved; only EP-S04 remains. See [review](../reviews/execution-node-password-auth-review.md). Actual Windows/RED OS SCP upload/download and negative password/pin checks passed. RED OS sudo evidence used NOPASSWD, so password-required sudo positive/negative acceptance remains open. No further automatic review cycle; owner decision needed for remaining evidence.


<a id="execution-node-password-auth-plan-checkpoint-002"></a>

## Owner-authorized EP-S04 evidence recheck — APPROVE

2026-10-08. Owner explicitly requested the reviewer again. Independent read-only evidence-only TARGETED_RECHECK: APPROVE; EP-S04 RESOLVED; zero unresolved blocking findings. Supplemental manifest SHA256 30E48D0EDC8AA308023FD02D417C3ABAECFEFCF72B8C119BCC22279163B6BD3E. Relevant production code unchanged from the preceding review.

Owner-observed real UI results:

- Wrong sudo password: «Проверен: Ошибка узла».
- Correct sudo password: «Проверен: Подготовлен».
- Selected sudo-password requirement and empty value: «Сохранить в сеансе» is blocked.

Reviewer independently checked the snapshot, credential form and immediate implementation, and accepted these precise owner observations as the missing password-required sudo evidence. Reviewer did not operate the UI. Exact timestamps/session IDs were not provided. Previously resolved staging/SCP/cleanup/hold findings remain RESOLVED. No new mechanisms or overengineering findings; this update changes evidence only. Full installation/Start/activation acceptance is not asserted. No further review required for the unchanged scope.

<a id="execution-node-password-auth-plan-checkpoint-003"></a>

Status: owner approved, implemented; FULL DIFF pending. Real React/Wails password information checks passed on node2 and Execution Node node1; readiness returned PREPARATION_REQUIRED, not READY. New installation/preparation was not performed.
Implementation evidence: Windows OpenSSH_for_Windows_9.5p2 (LibreSSL 3.8.2); packaged Windows helper PASS, Linux browser helper PASS on RED OS with OpenSSH_9.9p1 (OpenSSL 3.5.5). Go tests/vet and 74 focused frontend tests/build/lint PASS. Active-run lease-expiry and callback/release wiping covered at broker and App transport boundaries; ordinary/stale scope rejected without revoking active transport. Native race checker unavailable on Windows (CGO_ENABLED=0, no C compiler). Actual password SCP and full preparation/Start require a separately authorized QA flow and are not claimed accepted. OpenSSH ASKPASS behavior: https://man.openbsd.org/ssh.1#ENVIRONMENT.
