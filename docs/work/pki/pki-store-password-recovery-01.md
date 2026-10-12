# PKI-STORE-01 — Recoverable PKCS#12 password rotation

Status: owner-approved; implementation IN PROGRESS; real React/Wails/Core acceptance pending.

## Goal

Allow an operator to enter a new Java keystore/truststore password in the
Certificates page when the old password is forgotten. If the supplied password
does not unlock the existing derived PKCS#12 stores, Core regenerates those
stores from the already validated persistent PEM key/certificate material.
The certificate identity is not reissued by this operation.

This is a narrow PKCS#12 recovery milestone. It does not change the portable
project contract, PKI plan semantics, password persistence, certificate
issuance policy, or the standalone Ansible interface.

## Owner decisions

- The field is on **Certificates**, labelled in Russian as the password for
  Java PKCS#12 `keystore` / `truststore` files.
- Installation shows whether the required PKI password is present and where to
  change it; it does not collect the password.
- The password stays in the existing project-bound in-memory credential lease.
  It is not written to the project, portable files, project backups, plans,
  events, diagnostics, or a new persistent credential store.
- No password encryption or encrypted-project-secret feature is added.
- A newly entered password may replace the current in-memory value before
  execution. Closing/clearing the credential session removes it; the operator
  can enter a new value and regenerate derived stores again.
- QA may keep its dedicated reusable test password in a local ignored file
  under `.runtime/secrets/`, with restrictive workstation permissions. Normal
  repeat runs reuse that value. A test whose explicit purpose is to create a
  new PKI/password may create and use a separate test value. The QA file is
  loaded only at test runtime, never printed, copied into the project, or
  committed; this exception does not add product password persistence.
- Existing PKI identity and reissue guards remain authoritative. This
  operation is not `pki-reissue` and does not bypass
  `CERTIFICATE_REISSUE_REQUIRED`.
- Services that consume changed stores use their existing changed/restart or
  reload behavior. No per-service restart orchestration or service-specific
  PKI rotation logic is introduced.

## Existing ownership and source

The Execution Node owns persistent managed CA/leaf PEM and derived PKCS#12
files under its existing protected execution-state root. The plan and request
fingerprints remain the source of the expected certificate identity. The
runtime password is supplied through the existing PKI SecretRef/password-file
boundary and is never passed as a plaintext command argument.

Current `pki_materialize` creates `keystore.p12` and `truststore.p12` only
when absent, then checks them with `keytool -list`. As a result, a different
password currently fails validation rather than rebuilding the files.

## Apply behavior

### Concurrent apply ownership

The fixed Execution Node controller takes a non-blocking POSIX advisory lock
scoped to the canonical project identity before it launches `pki-apply.yml`.
The lock remains held until that single playbook has completed both PKI
materialization and target deployment (or has been cancelled/terminated).
Another Installer run for the same project fails safely with
`PKI_APPLY_ALREADY_RUNNING` before launching Ansible; it cannot rotate stores
or deploy a mixed pair concurrently. Different project identities use
different lock files and remain independent. The lock is machine-owned under
the Execution Node state root, outside the portable project and ephemeral run
workspace. OS advisory ownership releases automatically when the controller
process exits, so an interrupted run does not leave a stale lock to clear.

Standalone Ansible remains usable. When an operator may run more than one
`pki-apply.yml` manually for the same project, invoke it under `flock -n` on
the same state-root path
`<execution-state-root>/projects/<project-id>/.pki-apply.lock`; do not remove
the lock file after use. As with any direct standalone invocation, the
operator supplies the project identity and state root consistently.

For each resolved PKI request, preserve this order. The existing explicit
reissue path keeps precedence and must not be mistaken for store-password
recovery:

1. Run the existing authority fingerprint, request-fingerprint, and explicit
   reissue authorization/resume checks. A changed request fingerprint without
   an authorized reissue remains `CERTIFICATE_REISSUE_REQUIRED` and cannot
   reach store recovery.
2. For an initialized request that is not resuming an authorized reissue,
   require `leaf.key` and `leaf.crt` to exist as regular, protected files.
   Validate the leaf certificate against the authoritative CA certificate and
   prove that the public key derived from `leaf.key` matches the public key in
   `leaf.crt`. Reject malformed PEM, a missing key or certificate, a failed
   chain check, or a key/certificate mismatch before creating or replacing
   either store. Initial issuance and authorized reissue continue through their
   existing creation/recovery branches.
3. Treat `keystore.p12` and `truststore.p12` as derived outputs, not required
   authoritative request files. When the request fingerprint marker and valid
   authoritative PEM pair exist, a missing, unreadable, or identity-mismatched
   PKCS#12 file is repairable. Narrow the current all-four-files partial-state
   guard accordingly; continue rejecting missing or invalid authoritative PEM
   and unauthorized/incomplete reissue state.
4. Validate existing stores with the supplied runtime password. Prove password
   readability and expected contents: expected aliases are present, the
   keystore certificate corresponds to the validated leaf PEM/private key,
   and the truststore certificate corresponds to the validated CA PEM.
5. If both stores match the password and expected content, leave them
   byte-for-byte unchanged (`changed=0` for store materialization).
6. If either store is missing, cannot be opened with the supplied password, or
   does not contain the expected certificate material, stage a complete new
   keystore/truststore pair from the validated PEM inputs.
7. Create both private staging files in the protected destination request
   directory, on the same filesystem as the final files, with restrictive
   permissions. Before replacement, verify that the destination directory and
   any existing destination files have the expected type and ownership and are
   not symlink substitutions. Do not replace either persistent file until
   both staged candidates have been independently validated with the new
   password and expected aliases/content.
8. Publish each validated file through same-directory atomic replacement. The
   target-deployment phase must not begin until both replacements complete.
   If the process stops between replacements, no target copy starts; the next
   apply validates the pair and regenerates both from the authoritative PEM
   inputs. PEM inputs and request fingerprints remain intact.
9. Mark PKI material changed when a replacement occurs. Existing
   `pki_deploy` then updates target stores. A retry with the same password and
   unchanged PEM/request identity converges to no further changes.

An unreadable or mismatched derived store is recoverable only while the
authoritative PEM files, CA chain, key/certificate pair, and request identity
pass the ordered preflight above. Missing, malformed, or identity-mismatched
authoritative PEM remains a failure; it must not be used to create replacement
stores. A changed request identity remains blocked by the current reissue
guard. An authorized reissue recovery marker follows only the existing reissue
recovery path; it is never consumed or bypassed as store-only repair.

## Kafka consumer handling

Services consume the derived stores through their existing contracts. When
PKI deployment reports changed files, each service's existing configuration
and restart/reload behavior applies them; this milestone adds no new
per-service lifecycle logic. Kafka is the currently relevant consumer and its
existing PKI-change signal, managed configuration render, and restart path must
be exercised by acceptance.

The persistent target `server.properties` currently contains the store
password. This milestone does not redesign Kafka credential consumption or
its existing restart behavior. The existing render task must suppress task
output and diffs (`no_log` and `diff: false`), retain restrictive file
permissions, and never emit the value in task events, journal, diagnostics, or
result output. This is output protection for an existing secret-bearing task,
not new service lifecycle logic. A rotation acceptance must prove that the
on-target configuration uses the new password without printing it.

## UI behavior

### Certificates

- Add a password input labelled **«Пароль Java-хранилищ PKCS#12 (keystore / truststore)»**.
- Explain briefly that it protects generated Java stores and is kept only in
  the active Installer session.
- The field is available before building a plan, uses the existing setter and
  credential broker, permits replacing a previously entered value, and never
  displays the value after submission.
- Show only `не задан` / `задан в текущем сеансе`; do not expose the value or
  infer that existing on-node stores have already been rotated.
- If no project-bound SSH credential session exists, show the existing safe
  prerequisite state and do not create another credential mechanism.

### Installation

- Remove the password input from the approved-plan/start area.
- Show only whether the active plan requires PKI store password and whether
  the current credential session contains it.
- Provide navigation to Certificates to enter or replace it.
- Keep Start blocked when required password is absent.

No plan, generated PKI preview, or project file contains the password. Update
the UI design mockup and text to reflect this placement before acceptance.

## Scope and non-goals

In scope:

- safe recovery/replacement of derived PKCS#12 stores on password mismatch;
- exact-content validation against already validated PEM identity;
- protected pair staging, per-file atomic publication, and retry recovery;
- preserving existing PKI identity/reissue rules;
- moving the existing input to Certificates and retaining only a status in
  Installation;
- using existing consumer changed/restart/reload behavior when stores change;
- narrowly preventing secret disclosure from existing password-bearing Kafka
  configuration task output;
- focused Core/Ansible, Go/Wails, frontend, and secret-leak regressions.

Out of scope:

- storing the password in the project or encrypting it;
- adding any product persistence for the QA password or general operator
  password;
- introducing a new password broker, SecretRef, protocol, project field, or
  persistent credential database;
- generating a new CA, leaf key, or certificate to recover a store password;
- changing PKI request/materialization fingerprints or public plan schemas;
- changing Kafka's TLS contract or moving password ownership into React/Core;
- running the SI11 all-services acceptance before this milestone is complete.

## Acceptance

1. Existing pair + correct password + matching PEM identity: no store rewrite.
2. Existing pair + different password + valid authoritative PEM: both stores
   are rebuilt with the new password; CA, leaf key, leaf certificate, request
   fingerprint, and certificate identity remain unchanged.
3. One missing, unreadable, or wrong-content derived store with valid
   authoritative PEM: stage, validate, and publish a complete pair; no partial
   pair is deployed to targets.
4. Failure during candidate generation/validation leaves existing persistent
   stores and targets unchanged.
5. Injected interruption between the two atomic replacements starts no target
   deployment; a retry repairs the pair from authoritative PEM and converges.
   A same-password retry after interrupted publication also converges without
   changing authoritative PEM identity.
6. Missing/malformed authoritative PEM, a leaf key/certificate mismatch, or a
   failed CA-chain check blocks before store publication. A changed request
   identity remains blocked unless it follows existing explicit reissue
   authorization and recovery.
7. Authorized reissue recovery marker behavior remains intact and takes
   precedence over store-only repair.
8. After rotation, existing PKI change handling reports changed store files;
   consumers apply them and perform their already implemented restart/reload.
   Repeating the apply returns no changes.
9. With diff enabled, password does not appear in Ansible stdout/stderr,
   journal/events, Wails result, or diagnostics. Target configuration file
   permissions remain restrictive.
10. Through actual React → Wails → Go methods, set/replace the password on
   Certificates before plan creation; Installation presents status only and
   blocks Start when absent. No secret is added to portable project bytes.
11. Entering a new password against an existing pair whose password is unknown
    is proven through the supported Wails/Core apply flow; no direct Go/Core
    harness substitutes for the UI acceptance gate.
12. Two overlapping Installer `PKI_APPLY` operations for the same project are
    serialized by rejection: the first retains the project lock through
    materialization and deployment; the second returns
    `PKI_APPLY_ALREADY_RUNNING` without starting Ansible. Different projects
    are not blocked, and process termination releases the advisory lock.

## Review findings carried into this revision

- `PKI-RP-01`: resolved in this revision by this pinned plan artifact and its
  SHA-256, submitted to the independent reviewer with the exact owner scope.
- `PKI-RP-02`: addressed by exact alias and certificate-material identity
  validation before existing stores are accepted as unchanged.
- `PKI-RP-03`: addressed by explicit persistent-target behavior, `no_log`,
  `diff: false`, restrictive permissions, and a diff-enabled no-leak rotation
  acceptance.
- `PKI-RP-04`: addressed by the ordered PEM/key-pair preflight, repairable
  derived-store classification, reissue precedence, same-directory protected
  staging, and failure/retry acceptance.

The architecture reviewer remains advisory. A BLOCK verdict stops automatic
implementation and returns the finding IDs to the owner; it does not authorize
automatic redesign or additional review cycles.
