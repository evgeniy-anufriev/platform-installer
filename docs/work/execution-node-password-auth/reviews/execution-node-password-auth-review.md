# EXECUTION-NODE-PASSWORD-AUTH-01 — targeted review

2026-10-08. Independent architecture-reviewer, owner-authorized TARGETED_RECHECK.

Initial targeted verdict: BLOCK; superseded by the owner-authorized EP-S04 evidence recheck below. Base HEAD f6522aa1d52c38be33b84fb77b4663311a73b1ea; snapshot manifest SHA256 806EF60B1395CF7C9B8C087B6B4298E403DBC820C1CDB737BBF99FA5045DEF79. Source hashes were independently checked. Scope: previous findings and directly affected sudo/staging boundary; unrelated dirty changes preserved.

## Resolved

- EP-D01: privileged staging mkdir/chown removed. Root-owned real sticky /var/tmp, fresh ordinary exclusive mkdir0700, strict 32hex name; foreign paths not reused.
- EP-D02: installed OpenSSH password-only SCP upload/download, wrong password and missing pin rejection through production transport. Isolated SSH endpoint executes actual SCP server subprocess. Windows and RED OS PASS reported by implementer; no production account/policy changes.
- EP-D03: bounded cleanup covers failures after successful claim and retains operation scope.
- EP-S01: per-invocation sudo authentication, shared shell parent, no tail-exec, direct JSON stdin preserved; password-required authentication evidence remains EP-S04.
- EP-S02: strict stage path and protected-parent checks implemented.
- EP-S03: exact identity/binding/plan/run sudo hold for PEM/password modes; callbacks and release wipe copied bytes.

## Former evidence blocker

EP-S04: the RED OS sudo test uses the established NOPASSWD account with synthetic input. It proves framing/substitution/pipeline behavior, but cannot prove password-required authentication or rejection of wrong/missing sudo passwords. Owner confirmed “Работает” after the sudo correction; exact positive flow was not recorded, and negative authentication cases remain unproved. This is an evidence gap, not a finding that the current password wrapper necessarily fails.

Smallest next step: real password-required sudo success and wrong/missing rejection with preserved direct JSON stdin and nested invocation, on an explicitly authorized isolated environment or a precise already-completed UI flow. Record only safe result codes; no credential values and no production sudoers/account changes. Full installation is not required for this evidence.

At that checkpoint, one blocker remained and the automatic review budget was exhausted. The owner subsequently explicitly authorized the evidence recheck below; no automatic cycle continued after BLOCK.

## Overengineering

No confirmed unnecessary mechanisms. Standard sticky staging, existing broker hold and fixed sudo function are sufficient. Tagged SCP test uses the existing x/crypto dependency at the unchanged version. No new desired-state persistence or public DTO/framework.

Go test/vet, Wails build and Windows/RED OS SCP PASS were implementer-reported; reviewer independently inspected code and manifest but did not run tests. This review does not prove full preparation/Start/installation acceptance.

## Owner-authorized EP-S04 evidence recheck — APPROVE

2026-10-08. Owner explicitly requested the reviewer again. Independent read-only evidence-only TARGETED_RECHECK: APPROVE; EP-S04 RESOLVED; zero unresolved blocking findings. Supplemental manifest SHA256 30E48D0EDC8AA308023FD02D417C3ABAECFEFCF72B8C119BCC22279163B6BD3E. Relevant production code unchanged from the preceding review.

Owner-observed real UI results:

- Wrong sudo password: «Проверен: Ошибка узла».
- Correct sudo password: «Проверен: Подготовлен».
- Selected sudo-password requirement and empty value: «Сохранить в сеансе» is blocked.

Reviewer independently checked the snapshot, credential form and immediate implementation, and accepted these precise owner observations as the missing password-required sudo evidence. Reviewer did not operate the UI. Exact timestamps/session IDs were not provided. Previously resolved staging/SCP/cleanup/hold findings remain RESOLVED. No new mechanisms or overengineering findings; this update changes evidence only. Full installation/Start/activation acceptance is not asserted. No further review required for the unchanged scope.