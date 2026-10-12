# SI11-V02 — trusted Execution Node binding from the Servers UI (PLAN)

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Status (2026-10-01): implementation in progress. The owner authorized the
session-only PEM and host-key scope and the bounded DIFF corrections. One FULL
DIFF review found D01/D02; the one authorized TARGETED_RECHECK passed both with
zero blockers. Go/frontend/Wails build gates pass. Real no-flag Wails WebView
opened a saved project, accepted the session PEM identity, displayed a host-key
fingerprint matching the previously trusted QA `known_hosts`, obtained explicit
approval, prepared the selected Execution Node and observed READY. V02 is NOT
DONE: Project Verify on the clean S11-00 node1 fails before Core snapshot
because `/var/tmp/platform-installer/execution-plan` is absent and
`stageProjectArchive` attempts `mkdir` of its child without creating the parent.
This is a Go Execution Node staging defect; S11 remains paused pending owner
direction. The earlier PLAN review history is retained below.

Owner decisions (2026-10-01, after the FULL PLAN review): for SI11 V02,
Execution Node access uses the existing PEM private-key mode only. SSH-password
session credentials may still be used for target hosts but do not authorize an
Execution Node connection; the Servers panel must explain this prerequisite.
Approval of an Execution Node host key lasts only for the current Installer
session. After restart the operator must observe and approve the key again.
No approved host key, private-key path or credential value is written to the
portable project. Password-capable Execution Node transport and persistent
host-key trust are outside V02 and require separate owner approval.

## Problem and goal

SI11 launches the Windows Wails executable without flags and exercises only its UI. `main.go` creates the private `executionNodeBinding` only when all startup SSH/bundle flags are supplied. The no-flag path uses `unavailableProjectReader`. Selecting a project server in the Servers UI changes only `ExecutionNodeContext`; `CheckExecutionNode`, preparation, Core Verify and installation still require a private binding. A saved project therefore cannot reach READY or Verify through the required UI flow.

Goal: connect the existing project-server selection to the existing trusted Execution Node transport and lifecycle, with no Core, project-format or public execution-protocol change. This is a prerequisite repair for SI11 V02, not service installation or a new remote execution design.

## Proposed ownership and flow

1. Installer Go alone resolves the selected **saved** project server's canonical address and SSH port, the current session technical username and supported SSH identity, and the one locally verified immutable runtime bundle. React supplies no transport object, trusted path or raw Core command.
2. Before any authenticated SSH action, a fixed, bounded, unauthenticated host-key probe obtains the selected `address:port` public host key and displays its SHA-256 fingerprint and key type in the existing Servers bottom panel. The operator compares the fingerprint with an independent trusted source and explicitly approves the exact observed public key for that exact address and port. The probe itself never makes the key trusted or reports READY. Unknown, changed, declined or mismatched keys block Check/Prepare/Verify/Plan. The established startup-flag path remains compatible.
3. After approval, Go creates one private `executionNodeBinding` for the selected host ID, verified bundle identity, session SSH identity and pinned host key. It reuses the existing `projectReader`, Execution Node service, plan service and supported Check → Prepare (explicit confirmation) → Verify paths. READY is determined only by real inspection/capability handshake, never by selection or key approval.
4. Project close/change, server address/port or selection change, session credential replacement/clear/expiry, bundle identity change and host-key mismatch invalidate the binding, readiness, verification evidence and any plan/continuation tied to it. In-flight operations must not publish evidence for a different generation. Local Save remains node-free; fresh `BuildDeploymentPlan` remains mandatory before Start.
5. The current session credential UI supports SSH password and PEM key, but `OpenSSHTransport` takes a key identity path. V02 uses only the operator-selected PEM file for Execution Node operations. The existing broker already validates and holds its bytes; it must privately retain the original absolute path and a digest/file identity bound to the same project-scoped lease generation. A narrow private identity resolver, not Wails/React, returns that path to the existing OpenSSH transport only while the lease is current, the mode is PEM and the original regular non-reparse file still matches the lease's verified identity and bytes. Recheck before every SSH/SCP operation and fail closed on replacement, unreadability, expiry or credential change. On the Windows no-flag UI path, hold an opened key-file handle with sharing that permits the child SSH process to read but denies write/delete/rename for the entire child operation; verify file identity and bytes on that same handle before launching SSH, and test parent-path replacement as well. This is a narrow Windows binding guard, not a generic filesystem framework. If identity/path stability cannot be proven, fail closed rather than accepting a check-then-open race. Do not create a second credential store, write a temporary key copy, pass private-key contents on the command line or add a password bridge. SSH-password mode gives a safe explicit Execution Node prerequisite while remaining available for targets.
6. For no-flag launch, use the existing unique verified bundle discovery. Missing/ambiguous/invalid bundle blocks binding with a safe diagnostic; never select latest automatically. Do not contact target hosts while establishing or checking the Execution Node.

### Session-only host-key pin

- The approved identity is the exact tuple `(selected host ID, canonical address, SSH port, public key type, public key bytes)`. The displayed SHA-256 fingerprint is computed from those bytes; approval refers to the current probe result, not a user-supplied fingerprint string or a later network observation.
- Go writes only the approved public key as a single standard OpenSSH `known_hosts` entry for the exact address/port (`[address]:port` for a nondefault port) in a newly created Installer-owned private runtime directory. Use exclusive creation, non-reparse path checks and owner-only permissions/ACL. Neither React nor a caller supplies the file path. This is a derived transport input, not a new trust database or portable project field.
- The private binding retains the approved tuple and the expected exact bytes/digest of the runtime `known_hosts` file. Before each SSH/SCP operation, reject a missing, replaced, reparse-linked, edited or differently bound file; hold the verified Windows file handle with the same read-only/no-delete sharing through the child operation. For this **new UI binding only**, invoke the existing OpenSSH transport with an isolated effective host-key policy: ignore user/system SSH configuration (`-F none`), set `StrictHostKeyChecking=yes`, set `UserKnownHostsFile` to the verified session file, disable `GlobalKnownHostsFile` and `KnownHostsCommand` (`none`). Neither global/user `known_hosts` nor an external command may authorize a key absent from the approved session file. Apply the policy to both SSH and SCP; if the supported OpenSSH binary cannot prove the effective isolated configuration, block the binding. Preserve the established startup-flag transport behavior separately. If the host presents any other key, the connection fails closed and READY/evidence/plan are invalidated.
- Decline, selected host/address/port change, project close, credential replacement/expiry or application shutdown invalidate in-memory approval and the binding, then remove only the exact session-created runtime file/directory when safely identifiable. A crash residue may be cleaned through a separately safe lifecycle, but is **never** rediscovered or trusted on restart; the next session requires a new probe and approval. No global/user `known_hosts` is silently modified.

## Narrow implementation seam

- `main.go`: retain the startup-flag compatibility binding; pass existing verified-bundle discovery to App without treating a mere project-server selection as trusted.
- `app.go`, `execution_node_context.go`, `execution_node_readiness.go`: private binding establishment/invalidation for a selected project server, preserving the existing selected-node/revision checks. Do not expand Wails to arbitrary SSH commands.
- Existing `runtimesecret.Broker`: retain the verified original PEM path and file identity privately with its project-bound lease and expose it only to the narrow identity resolver while current. No credential value or path in project, logs, events, diagnostics or Wails results.
- Existing OpenSSH transport/host-key policy: fixed bounded host-key probe, session-only approved-key `known_hosts` input, strict checking and reuse of the current transport after approval. No second SSH transport stack or persistent trust database.
- `ServersPage.tsx`: fingerprint display, explicit approve/decline and bounded prerequisite status on the existing bottom panel. The UI does not calculate fingerprints or claim READY.
- `App.tsx`: show safe Verify prerequisites rather than a silent `UNVERIFIED` result. No new Installation dialog.

## Acceptance and negative proofs

- No-flag Wails executable → open saved project → select project server → session PEM credential → observe fingerprint → explicit approval → read-only Check → explicitly confirmed Prepare if needed → actual READY/capability handshake → target-free Verify bound to saved revision/runtime. Restart repeats the host-key approval; password-only mode visibly blocks Execution Node Check without blocking local Save.
- Before approval, wrong key, changed key, stale credential, changed server, changed project or changed bundle: no trusted binding, no stale READY/evidence, no plan/start. Decline leaves project bytes unchanged.
- Fault-injection covers original PEM file replacement/expiry between operations and during the validation-to-OpenSSH handoff; altered `known_hosts`, wrong address or port, a changed server host key and stale approval cannot reach SSH or preserve READY. Shutdown/crash residue is never accepted as new-session trust.
- Inspect effective `ssh -G` configuration for the UI binding (and the corresponding SCP invocation) to prove the session file is the only host-key trust source: no user/system config, global known-hosts file or `KnownHostsCommand`. A negative test places a different key for the same address/port in a global trust source but not in the approved session file; SSH/SCP must reject it and clear READY/verification/plan evidence. A control test confirms the legacy startup-flag path remains compatible.
- UI operations are exercised in the real WebView. Read-only tests cover binding lifecycle; no direct Go harness substitutes for SI11 acceptance. Existing flag-based QA continues to work. No target contact for V02 Verify.
- Verify failure displays a safe actionable Russian prerequisite; secrets and raw SSH output are never rendered.

## Review boundary

The PLAN targeted recheck covered SI11-V02-01 (PEM path/lease/transport
handoff), SI11-V02-02 (approved host-key to strict `known_hosts` handoff) and
SI11-V02-03 (the two recorded owner decisions). It resolved 01 and 03 at plan
level but left 02 blocking because the global trust source remained active.
The owner subsequently authorized the exact host-key correction and V02
implementation. During implementation, one FULL DIFF review blocked D01/D02;
the owner authorized the bounded corrections and one TARGETED_RECHECK, which
passed both with zero blocking findings. The DIFF review budget is exhausted.
This is architecture evidence, not a claim that WebView Project Verify passed.

## Реальная приёмка V02 (01.10.2026)

See [historical checkpoint](evidence/documentation-checkpoints-20261012.md#si11-v02-trusted-binding-plan-checkpoint-001). Current status: [CURRENT_STATE](../../../CURRENT_STATE.md).
