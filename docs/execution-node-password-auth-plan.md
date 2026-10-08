# EXECUTION-NODE-PASSWORD-AUTH-01

## Owner scope

2026-10-08: owner explicitly requires SSH password authentication for the Execution Node as well as target servers. Extend the existing session credential selector and common SSH/SCP transport, including information, readiness, preparation, planning, Start, polling/recovery and output delivery. Keep the existing PEM path. No new installation, target password change, sudo policy change or bundle activation is authorized by this request. Core/Ansible stays on the Execution Node.

## Existing limitation

Broker accepts SSH_PASSWORD but CurrentExecutionIdentity, active-run holds and the dynamic transport require PEM path/FileInfo. OpenSSH uses BatchMode=yes and -i. The informational facade and Servers buttons inherit this restriction. Existing target credential staging already represents SSH passwords; do not duplicate it or change desired inventory.

## Transport and credential design

1. Extend private ExecutionIdentity with SSH mode. Password identity has no file/path and remains bound to project, username and credential generation. Do not export password or password hash to Wails/logs. PEM file identity/digest checks remain unchanged.
2. Add a synchronous broker callback exposing only the password of the exact captured identity. Copies are wiped on callback return. The existing STARTING/RUNNING hold retains a private password copy when password mode is selected; retain until authoritative terminal observation, release/clear/shutdown wipe it. No hold for information/readiness/preparation. Ordinary expiry still blocks new checks/starts. Binding/mode/generation changes reject stale connections; a run hold permits only the already-bound active run transport, as with PEM.
3. Preserve existing OpenSSHTransport commands, SCP, static scripts, bounded output and cancellation. Password mode selects password authentication explicitly (no key/agent fallback, no keyboard-interactive, one password prompt), still with isolated StrictHostKeyChecking=yes and the confirmed exact key. PEM behavior remains unchanged. The private transport holds a broker callback, never a captured persistent password string.
4. Use the standard SSH_ASKPASS helper supported by OpenSSH, SSH_ASKPASS_REQUIRE=force. Reuse the current Installer executable in an early helper mode before flag/UI/browser initialization. No password in argv, environment, files or scripts. Per child command, a loopback listener on 127.0.0.1 supplies the password only after a random 256-bit one-use capability token; only endpoint/token/helper mode metadata is inherited by the SSH child/helper. Do not enable an application RPC or arbitrary command bridge. Token is command-scoped, bounded request length, constant-time comparison, short request deadline, bounded attempts, one successful retrieval, listener owned by command context, close/wait on child completion/cancel/error. Wipe copies and close accepted sockets. Exclude helper metadata from normal inherited environment; unrelated children cannot reuse it. Synchronous helper fails silently if called without valid capability. Never log helper response or command stdin.
5. Existing command guard validates broker identity and the pinned known_hosts for both methods. Only PEM additionally holds the key file stable. IdentityFile lookup and base SSH/SCP options must accommodate password mode without -i or missing-file errors; centralize this in the existing transport rather than parallel implementations.
6. Include helper early dispatch in Wails and browser entrypoints. Do not start Wails/browser services in helper mode. Packaging uses the existing executable; no new external dependency or downloaded sshpass.

## UI and errors

Enable unified «Проверить сервер» for a present password or PEM session, including Execution Node. Keep a single fingerprint confirmation and installation pin handoff. Russian safe errors describe unavailable credentials or authentication failure without erroneously demanding PEM for password mode. Information success and runtime readiness remain independent. Keep accepted 50 px row, centered primary text and lower single-line observations.

## Gates

HIGH-RISK secret/transport/lifecycle change: one independent FULL PLAN review, then one FULL DIFF. BLOCK stops and returns findings to owner; no automatic redesign cycle. Owner already authorized password support; this document makes implementation reviewable. Existing review budgets belong to separate SERVER-INFORMATION-CHECK-01.

Tests: real OpenSSH ASKPASS with a local SSH test server or supported QA account where credentials are available; password provider exact-binding/expiry/active hold/release/zeroing; wrong token/replay/no helper args/startup side effects; deadline/cancel cleanup; SSH/SCP no password in argv/env/logs; no key fallback; pinned mismatch; PEM regression. Go test/vet and focused frontend gates. Real React/Wails password information and Exec readiness required; preparation/Start semantics must be tested without authorizing a new production install. Actual mutating acceptance needs separately authorized QA targets/run. No credentials available is a prerequisite failure, not a mock replacement.

## Independent FULL PLAN review

APPROVE_WITH_CHANGES, no blockers. EP-01: distinguish live-lease identity/password lookup from lookup scoped to an exact captured STARTING plan or RUNNING run. A matching project alone never authorizes retained password after TTL. Existing slot is reused; unknown Start remains reserved. Expiry tests must show existing-run polling/cancel succeeds while new information/readiness/start and another plan/run/generation fail.

EP-02: QA must record exact packaged Installer and SSH/SCP versions on Windows and supported browser host, exercise early helper dispatch and password authentication for SSH and SCP separately. If installed OpenSSH does not support ASKPASS, return a safe prerequisite error without password file/environment/argv fallback.

EP-03: ASKPASS response is one nonempty password byte sequence, at most the broker password limit, followed by one framing LF. Reject password values containing LF, CR or NUL before launch with a safe code and no content. Preserve original supported bytes, wipe buffers, do not retain strings. Include malformed/oversized/replay/cancel tests.

Status: owner approved, implemented; FULL DIFF pending. Real React/Wails password information checks passed on node2 and Execution Node node1; readiness returned PREPARATION_REQUIRED, not READY. New installation/preparation was not performed.
Implementation evidence: Windows OpenSSH_for_Windows_9.5p2 (LibreSSL 3.8.2); packaged Windows helper PASS, Linux browser helper PASS on RED OS with OpenSSH_9.9p1 (OpenSSL 3.5.5). Go tests/vet and 74 focused frontend tests/build/lint PASS. Active-run lease-expiry and callback/release wiping covered at broker and App transport boundaries; ordinary/stale scope rejected without revoking active transport. Native race checker unavailable on Windows (CGO_ENABLED=0, no C compiler). Actual password SCP and full preparation/Start require a separately authorized QA flow and are not claimed accepted. OpenSSH ASKPASS behavior: https://man.openbsd.org/ssh.1#ENVIRONMENT.

## Preparation failure correction (2026-10-08)

Owner reported PREPARE_STAGE_FAILED after password login. Read-only node1 evidence: /var/tmp/platform-installer/bootstrap belongs to platform-automation with mode 0755; admin cannot write there, and admin sudo -n requires a password. Free space is about 9.8 GiB. The generic stage error does not distinguish these prerequisites.

Bounded correction: readiness/plan blocks preparation with EXECUTION_NODE_ELEVATION_REQUIRED when non-interactive sudo is unavailable. App projects a Russian actionable message. SSH password authentication and sudo elevation remain distinct; this does not configure sudo or implement a new sudo-password transport.

For authorized sudo-capable accounts, bundle staging claims a fresh nonce directory under the established bootstrap parent, mode 0700 owned by the current SSH uid/gid. The existing parent owner/mode and earlier staging directories are preserved; reject symlink parents, require exclusive mkdir, no preemptive rm. Upload the archive inside that private directory instead of beside it (the shared parent can be unwritable). Existing activation, bundle verification, trust and cleanup boundaries remain. No account/policy change or runtime activation performed during diagnosis.
## Owner-approved sudo correction (2026-10-08)

Owner explicitly confirms using the entered sudo password for execution-node operations, preserving exact active-run authorization after TTL, correcting EP-D01 staging and real SCP QA with one targeted recheck. No sudo policy/account change, full installation or bundle activation is authorized by this correction.

Implementation proposal: add one operation-scoped broker callback for the existing sudo bytes, matched to identity generation/binding and exact STARTING/RUNNING hold, including PEM+sudo sessions. Retain and zero sudo alongside the existing run hold. Public session/desired-state contract stays unchanged. Capture only a boolean indicating supplied sudo credentials in the transport; renew credentials invalidates the captured binding.

Use the existing pinned SSH stream for sudo credentials. A fixed remote shell wrapper reads one password line from SSH stdin (never interprets it as shell source), authenticates sudo with sudo -S -p '' -v, then invokes sudo -n for the actual command in the same shell parent. Script-mode calls use a fixed sudo function; direct sudo protocol calls preserve the subsequent JSON stdin verbatim. Validation has its own pipe so neither password nor framing enters Core/Ansible input. No password argv/env/files, remote helper installation or sudo policy changes. Reject LF/CR/NUL and oversized sudo values, disable tracing before secret read, generic errors suppress raw child output. Commands without sudo (information/keyscan/SCP) do not acquire elevation credentials.

Remove privileged staging claim entirely: create a fresh private directory directly under the existing root-owned sticky /var/tmp, using a random prefix /var/tmp/platform-installer-bootstrap-<nonce>. Validate /var/tmp ownership/type/mode; plain exclusive mkdir mode0700 as SSH user; no sudo mkdir/chown or foreign-controlled ancestor. Upload bundle.tar inside that directory; update fixed activation/extract/cleanup path guards to this namespace and remove only the owned attempt after failures. Existing shared bootstrap folders remain untouched. EP-D03 cleanup starts after successful claim.

QA: actual sudo/cache-parent behavior and preserved protocol stdin on RED OS; injected format/error/expiry/wipe tests; exclusive mkdir, symlink/existing-directory refusal and no cross-path mutation; real password-only pinned SCP upload/download small nonsecret fixture with cleanup, no runtime activation. Real React/Wails information/readiness must use the entered SSH and sudo credentials. If real UI session is unavailable, ask only to enter credentials in UI, never chat. New sudo transport is architecture-sensitive; obtain independent plan assessment before coding and include it in the owner-approved targeted review boundary.
## Targeted recheck outcome (2026-10-08)

Owner authorized EP-D01/EP-D02 corrections and the sudo-password extension, then confirmed the correction works and explicitly requested the recheck. Independent TARGETED_RECHECK BLOCK: EP-D01, EP-D02, EP-D03, EP-S01, EP-S02, EP-S03 resolved; only EP-S04 remains. See [review](execution-node-password-auth-review.md). Actual Windows/RED OS SCP upload/download and negative password/pin checks passed. RED OS sudo evidence used NOPASSWD, so password-required sudo positive/negative acceptance remains open. No further automatic review cycle; owner decision needed for remaining evidence.
## Owner-authorized EP-S04 evidence recheck — APPROVE

2026-10-08. Owner explicitly requested the reviewer again. Independent read-only evidence-only TARGETED_RECHECK: APPROVE; EP-S04 RESOLVED; zero unresolved blocking findings. Supplemental manifest SHA256 30E48D0EDC8AA308023FD02D417C3ABAECFEFCF72B8C119BCC22279163B6BD3E. Relevant production code unchanged from the preceding review.

Owner-observed real UI results:

- Wrong sudo password: «Проверен: Ошибка узла».
- Correct sudo password: «Проверен: Подготовлен».
- Selected sudo-password requirement and empty value: «Сохранить в сеансе» is blocked.

Reviewer independently checked the snapshot, credential form and immediate implementation, and accepted these precise owner observations as the missing password-required sudo evidence. Reviewer did not operate the UI. Exact timestamps/session IDs were not provided. Previously resolved staging/SCP/cleanup/hold findings remain RESOLVED. No new mechanisms or overengineering findings; this update changes evidence only. Full installation/Start/activation acceptance is not asserted. No further review required for the unchanged scope.