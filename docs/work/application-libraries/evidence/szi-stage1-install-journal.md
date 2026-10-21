# SZI stage 1 installation QA

Owner-authorized installation on the existing 101/102/103 infrastructure,
with `SkipInfrastructureVerify=true` and application containers on 102/103.
This journal records observed results; it does not mark installation accepted.

## Project and inputs

- Worktree: `szi-stage1-implementation/platform-installer-v2`.
- QA project: `.runtime/qa/szi-full-services-project`.
- Project ID: `project-f364f51aa0414d02`.
- Desired revision after QA heap overrides:
  `sha256:b7f1418036b59e91278fff11efd369e52dfbd15c072c92bbfdf0024b634f8d79`.
- Ten infrastructure deployments copied from the owner's
  `.runtime/qa/sdku-cspa-alarm-view-project`; all five SZI applications have
  placements on node2/node3 and none on node1.
- Execution Node explicitly selected as node2, `192.168.56.102`.
- Nginx image:
  `evoscada-docker.artifacts.tn.tngrp.ru/lawellet/nginx-lua-resty:1.0.3-redos3-certs`.
  The archive was exported from 107 and its transfer digest checked.
- Keycloak heap: 256/512 MiB, container limit 1 GiB. QA project overrides
  grant-access heap to 512 MiB and audit heap to 384 MiB.
- Keycloak restore database is `szi_keycloak_stage1`; the pre-existing manually
  imported `keycloak` database is a separate input and is not overwritten.

## Authorized cleanup

Removed the four confirmed stale QA directories on 102:

```
/var/tmp/platform-installer-qa-d1a6b31cc5f24c218d737a918e4dfb2e
/var/tmp/platform-installer-qa-01667a0011084407951b6c555635206d
/var/tmp/platform-installer-qa-2c3502eb694a43178744300f085d439d
/var/tmp/platform-installer-qa-b893518891e3445caf54ad46e81c544f
```

Removed only `messages-20260927`, `messages-20261004`, and
`messages-20261011` from `/var/log` on 101/102/103. Exact real paths, regular
files/directories and absence of open files were rechecked before deletion.
Observed free space immediately afterward: 4.7/11/5.7 GiB respectively.

## Checks and corrections

- Target-free snapshot passed with ten application placement rows, using the
  application names as IDs. Seven snapshot-action and five image tests passed.
- Go package admission now accepts the approved generic `scripts` manifest
  field. Its focused import regression passed.
- Full `go test ./...` and `go vet ./...` passed. After timeout changes,
  `internal/desktop` and `internal/installer` tests/vet passed again.
- RED OS current-source run of application plan, mixed execution, package script
  runner, image protocol and infrastructure verification: 64 tests, two skips,
  no failures.
- Runtime preparation originally exceeded the desktop's five-minute deadline
  during extraction. The generic preparation deadline is now twenty minutes;
  the repeated real Wails preparation completed, and node2 reported READY.
- Planning includes offline image preparation, so the original two-minute
  desktop deadline expired while Core continued. The generic planning deadline
  is now ten minutes. Staging run
  `installer-340243612862045098706218294797327395613` subsequently produced a
  plan and manifest, but its timed-out desktop call was not approved or started.
- Staging run `installer-156972579693907036844008655616354136884` reached
  executable Core output but failed manifest admission. Script inputs used an
  unsupported separate purpose and repeated runtime references. The planner
  now uses the existing `APPLICATION_SECRET` transport and emits one requirement
  per runtime reference across script/application consumers. No additional
  secret purpose or manifest schema extension is required.
- The actual SZI project was replayed with current source, its prepared image
  metadata and the same deployment/library order: `EXECUTABLE`, controller
  manifest admission passed, four application secret requirements.
- Browser QA sessions explicitly open and assert the SZI project ID before
  binding the node or planning. This prevents the UI's saved-project auto-open
  from selecting another QA project in a newly opened browser context.

## Runtime bundle and remaining acceptance

Initial bundle `szi-stage1-20261021-01`, digest
`sha256:6f3e53b35f1d847f6cb859a199ef07871832c7f3a2c9922f0b82f53194efe511`,
was validated, published and rebound through Wails, then prepared on node2.
Corrected-source bundle `szi-stage1-20261021-02` was built on node2 from the same
verified offline artifacts. Its 957 components and five images passed the
standard local validator; digest
`sha256:d28a612c2ae5b7d7f511661a2860c9b852f29e67b890d84fe9da6f0a31c6896d`.
The Wails rebind returned UPDATED, project revision
`sha256:a314971d915f4702b35dec9d3b6a6b3665a46c8335fc58b6339b28a676f6df3c`.
Previous local bundle source was preserved before the standard publisher replaced
the cache. Own temporary build input/output on node2 were removed after complete
local validation. Node2 preparation is in progress; fresh Wails plan,
approval/Start and terminal Apply/Verify result remain to be recorded.

Actual React/Wails Start attempts are recorded below; none has completed Apply/Verify successfully.
Visual UI acceptance has not been performed.

## Owner scope correction and first execution, 2026-10-21

Fresh plan `plan-d1a17b60622987f5379e830c` was approved and started through
real React handlers/Wails, application-libraries-only with SkipInfraVerify.
Run `installer-7ad70a9c3c539375807d1099d37b73f3` FAILED at the Vault projection
preflight before target contacts. The Keycloak package was missing the ordinary
`provisioner.secrets.mount: secret` setting; this is now supplied in examples
and the QA project. No containers were started and no database restored by this run.

The owner subsequently narrowed stage 1 to Keycloak only on 102/103: clean
DB import, scripts and admin bootstrap. Other four SZI application slots are
optional and are absent from the QA deployment selection. The unused audit DB
resource was removed from this deployment. Internal grant-access client bootstrap
and other application deployments are deferred to stage 2. Redis credentials for
grant-access were explicitly rejected as legacy. No grant-access credential or
bootstrap implementation is added as part of this scope correction.
Keycloak-only plan `plan-c5377b9bfca544cf6fd258a0`, revision
`sha256:3dd8109989ea3e21199ded72d539527f6ebb0fde187124981020b8d1ae834d37`,
was approved and started through real React/Wails. Run
`installer-cced6af76c77d8cfdfe69cb3f68ff1d0` FAILED at standalone runtime authority
preparation before target mutation. Source replay identified `projectId` being
attached after script argv resolution. The generic script projection now obtains
that existing field from the snapshot before resolving argv. The regression
starts with a job lacking projectId and resolves it from the snapshot. Focused
RED OS SZI/runtime suite: 25 tests, one skip, no failures. Repeated standalone
preflight of the exact Keycloak-only project passed. A corrected immutable bundle
is required before another authoritative plan/Start; installed runtime was not
patched in place.
Corrected bundle `szi-stage1-20261021-03`, digest
`sha256:7dae07b25cb25863da2f62ff7ad67483c2b379dd29e85ffa27ae1d70332ad4f0`,
was built on the trusted existing-runtime node2 from the current generic script
projection and the same verified offline artifacts. Standard Go ValidateRoot
passed. The previous local v2 source was preserved; the standard Wails publisher
and rebind returned UPDATED, revision
`sha256:c1d1f38fe2e1a612b0887e792846904ef1ecbef5fd05432ce68f3b19e19c3c00`.
Node2 preparation is running through the established runtime preparation flow.
Node2 preparation of bundle v3 returned PREPARED; its check returned READY.
After confirming current=v3, no active run references to v2 and no open files,
removed only the owned prior v2 runtime release and own v3 build staging on
node2. The complete prior bundle source remains local under `.runtime/qa/szi-bundle-v2`.
Free disk space on node2 returned to about 7.4 GiB. A new real React/Wails
Keycloak-only installation flow is in progress.
Plan `plan-d50e0dd2e91a3da86350a83e` was approved and started on bundle v3.
Run `installer-21969f3e217737b6d8e035db20deee9d` passed runtime authority and
configuration/namespace preflights, then FAILED at free published-port checking
before file/provider writes. On node3, port 9000 was held by the earlier owned
manual test container `szi-keycloak-production-check-20261020` (same Keycloak
image, rootful Docker). The exact test container is being stopped without removal
or DB changes; the ordinary library port/placement configuration is retained.
A fresh plan is required for the retry.
## Current blocker: existing infrastructure PKI identity

The earlier manual production/bootstrap test container on node3 was stopped;
port 9000 is now free. A new React/Wails Build/Approve/Start produced the same
plan fingerprint `plan-d50e0dd2e91a3da86350a83e` for unchanged desired state and
runtime, then run `installer-5a3738dbc495dff9f76053da70975ae2`.
The free-port gate passed. The run FAILED at Vault discovery task
`Read the selected provider CA from its exact PKI materialization`, before DB
restore, account provisioning or application materialization/start.

The new project's expected public CA file is absent on node1:
`/etc/platform-installer/pki/project-f364f51aa0414d02/qa-tls-profile--node1/ca-chain.pem`.
Existing infrastructure PKI belongs to the source project
`project-b46aa3f5f57a495f`; that project's PKI directory exists on node1.
SkipInfraVerify suppresses infrastructure Verify, but does not provide missing
provider TLS material. No Core change or identity/path fallback is introduced.

Owner decision requested: continue from a separate copy preserving the source
installation project ID and existing PKI, or retain the new ID and separately
prepare its PKI through existing mechanisms. Until resolved, clean DB restore,
Keycloak scripts/admin bootstrap and final Verify remain NOT PROVEN. No SZI
application containers have been started by these runs. Other four application
deployments and grant-access client bootstrap remain stage 2.
Owner selected a separate QA copy preserving source installation identity and
existing PKI. The QA copy at `.runtime/qa/szi-full-services-project` now uses
`project-b46aa3f5f57a495f`; the original source project directory is unchanged.
The previous new-ID manifest and failed-run evidence were preserved locally.
Only Keycloak remains selected, on node2/node3, with database `szi_keycloak_stage1`
and bundle v3. A fresh real React/Wails plan/Start is being exercised with this
owner-approved identity. The earlier new-project-PKI blocker is no longer the
selected deployment path; successful restore/bootstrap remains to be proven.
## First restore proof and Compose package correction

With the approved source installation identity, real React/Wails plan
`plan-ee9c861af063236bdd0dd9e1`, revision
`sha256:4a27bee2c2796daf3d7cb3de3e1fa8f03a801ede1a284674c601867c9589696e`,
started run `installer-c4c2c54bdea207ea850a0833428e85cd`.
Vault CA reading/discovery and the provider stage passed. The clean dump was
restored into `szi_keycloak_stage1`; Core confirmed ordinary tables and recorded
ownership only after successful restore. PostgreSQL account/grants and Vault
provisioning completed. Thus restore_on_create is exercised on the actual cluster.

The run FAILED at `Check only Core-projected Compose values`, before image
startup/bootstrap. The package used a different Vault Agent argv spelling and
omitted the generic `/opt/application/pki` directory bind expected by the existing
validator. Keycloak Compose now uses the standard Agent launch and generic PKI
mount while retaining its Keycloak-specific PEM file aliases. No Core guard was
changed. An actual Docker Compose config/render check against validate_compose
was added and passed on RED OS; all six SZI tests passed.

Removed the obsolete `KC_SPI_TRUSTSTORE_FILE_FILE` reference to an unmounted
cacerts file; the already configured PEM `KC_TRUSTSTORE_PATHS` remains the trust
source. Official configuration reference: https://www.keycloak.org/server/keycloak-truststore
A fresh plan/Apply retry now tests discovery of the restored DB without another
restore, then scripts and admin bootstrap. Their success remains unproven.
## Repeat restore skip, native script invocation and JDBC target correction

Plan `plan-e5dd433c03dbbb7fbc6cb3aa` started run
`installer-02f3a0a060960aa175d781b078365d96`. PostgreSQL restore and its ownership
write were SKIPPED for the existing managed DB. Actual Compose projection checks
passed, both rootless Docker daemons loaded the locked Keycloak image, and the
generic runner delivered argv/private secret files and invoked the before_start
script on node2. It FAILED after 303862 ms against the existing 300-second runner
limit. The temporary --rm container was removed; admin/bootstrap client were not
created. No new Core timeout or runner context was introduced.

Read-only login against actual DB targets 102/103 with the runtime application
credential passed: admin=0, temp-admin client=0, Liquibase lock=false. The QA
JDBC list had incorrectly included node1, which is the monitor and is excluded
by Core's PostgreSQL connection projection. A probe starting with node1 failed
authentication; the identical credential works on the projected database nodes.

Keycloak now consumes POSTGRES_ADDRESS assembled by the ordinary SZI base Compose
from library_runtime.connections.postgres.targets, preserving each target port.
Database name comes from application_databases.postgres['keycloak-db'].name.
Removed duplicate POSTGRES_JDBC_HOSTS/POSTGRES_KEYCLOAK_DB parameters from the
package/QA deployment. Native Compose regression exercises 102:15432/103:25432
and excludes node1; all six SZI tests passed. Structural project read passed.
Configuration expression reference: https://www.keycloak.org/server/configuration
A fresh real React/Wails retry is in progress with this package-only correction.
The corrected-JDBC retry plan `plan-e3f7b6943ecd561fc1ca823c` started run
`installer-24d4cfaaef517d92eb701ec58cfbb47a`. Container inspection confirmed
POSTGRES_ADDRESS=102:5432,103:5432 and the intended DB name. Quarkus provider
augmentation still exceeded the existing 300-second runner limit; Docker recorded
SIGTERM, exit143 and automatic --rm removal, with no OOM event. No admin or
bootstrap client was created; DB remains reachable and unlocked.

Package resource configuration was adjusted for the initial provider build:
JAVA_OPTS_KC_HEAP=-Xms256m -Xmx1g; memory limit is now a normal package parameter
KEYCLOAK_MEMORY_LIMIT=2G rather than a Compose literal; readiness uses the existing
settings contract (60 retries, 5-second delay). Generic script runner/timeout and
Core contracts are unchanged. Native SZI suite6 PASS after the adjustment.
Reference: https://www.keycloak.org/server/containers#_specifying_different_memory_settings
A fresh plan retry is in progress. The QA observer retains only redacted bootstrap
logs in runtime QA, with exact known runtime-secret values removed before writing.

The resource-adjusted real React/Wails plan `plan-cd6052181abe1caf1be89e1b`
started run `installer-c8dd23ed2d4f40c601f31073206dc728`. Providers,
materialization and image discovery passed. Quarkus augmentation completed in
137847 ms with the supplied plugins; the subsequent bootstrap command failed
after 220189 ms overall, below the runner timeout. Captured Docker usage was
about 541 MiB / 2 GiB and 31% CPU; node2 exposes one CPU and was heavily loaded.
Read-only DB state after failure: admin=0, temporary client=0, Liquibase unlocked.
No permanent Keycloak container started. The polling log observer missed final
lines before automatic container removal. A fresh unchanged plan retry uses
continuous redacted Docker log capture to diagnose that final CLI failure.

Unchanged-plan retry `installer-bb3b5762bb30732df619f9385c2f6468` captured the
final error continuously: PostgreSQL JDBC could not open
`/usr/lib/keycloak/ssl/ca.pem` because it was a directory. Owner independently
identified the same error and requested the working alarm-view-service PKI
pattern. The SZI package had not declared the existing shared PKI credential,
so its identity job had no pkiPlans; Docker created missing per-file bind sources
as directories. Standard delivery supplies keystore.p12, truststore.p12 and
ca-chain.pem, not leaf.crt/leaf.key.

Keycloak now mounts only the standard `/opt/application/pki` directory. JDBC
and KC_TRUSTSTORE_PATHS use its ca-chain.pem; HTTPS uses its keystore.p12 with
PKCS12 type. The SZI library declares java_keystore_password from application-pki
using the existing pki_credential contract, and Vault Agent injects it into
KC_HTTPS_KEY_STORE_PASSWORD. The admin script already uses ca-chain.pem.
No Core contract/identity delivery change. Six native SZI tests PASS, including
Compose PKI path and binding regression checks. Removed only the three empty
Docker-created source directories and their empty parent on node2. A fresh
real React/Wails plan retry is in progress with the corrected package.
Keycloak TLS reference: https://www.keycloak.org/server/enabletls

Plan `plan-5bd3fb5a8fb4a12d4ec895e8`, run
`installer-9793d010756f1e6a1077381f9c318230`, delivered the actual three PKI files
with mode0600 to the mapped container UID (directory0700). Docker inspection
confirmed the sole standard PKI directory mount. JDBC progressed past the former
CA error. The offline CLI then failed when starting its enabled management
interface: keystore password was incorrect. This temporary CLI bypasses Vault
Agent and therefore had no HTTPS keystore password. Permanent containers still
had not started. Read-only DB state remained admin=0, temp client=0, unlocked.

Owner requested bootstrap without SSL/dev behavior. The package bootstrap
wrapper now unsets HTTPS key-store/PEM options and uses KC_HTTP_ENABLED=true,
KC_HTTP_MANAGEMENT_SCHEME=http only in its transient CLI process. No ports are
published by compose run. Production configuration is unchanged and its password
is delivered by Vault Agent. No generic runner, Core or PKI delivery change was
made. The dedicated bootstrap-admin service command remains because the restored
master realm already exists; start-dev startup bootstrap options apply only when
master does not yet exist. Reference:
https://www.keycloak.org/server/bootstrap-admin-recovery
Native shell syntax and six SZI tests PASS; a fresh real plan retry is underway.

HTTP bootstrap plan `plan-4b60cc0b438d93066e2d0205`, run
`installer-407a618dfaee2fa006cce9772a9f878b`: restore tasks SKIPPED; temporary
service account successfully created, CLI stopped cleanly. Read-only DB query
confirmed admin=0, temp client=1, unlocked. Bootstrap management listened on HTTP,
no published ports. Both permanent containers then became healthy in production
on HTTPS8051/managementHTTPS9000 through Vault Agent. An independent OpenSSL
read-only probe confirmed the current runtime PKI password opens delivered P12.
The 1-second JDBC acquisition setting produced startup warnings (and a transient
JGroups connection warning), but both nodes started and passed readiness.

Run FAILED at after_ready create-admin; admin still absent. Source inspection
of Keycloak26.4.0 BaseConfigCredentialsCmd proved that --secret '-' is literal
for service-account authentication (stdin special handling is only in the user
authentication branch). Corrected package wrapper to pass KC_CLI_CLIENT_SECRET
only in the CLI process environment, retaining private file transport and no
secret argv. Shell syntax and all six native SZI checks PASS. The permanent
containers and temp client are retained for the next normal Apply to reconcile.
Source: https://raw.githubusercontent.com/keycloak/keycloak/26.4.0/integration/client-cli/admin-cli/src/main/java/org/keycloak/client/cli/common/BaseConfigCredentialsCmd.java

Independent read-only API checks with the temporary client PASS on both
102/103, including certificate/name validation and access to master Admin API.
The imported user profile has no mandatory missing fields. Plan
`plan-b74aef4293deae8a7b55882d`, run
`installer-7c1596586b43f8d5a78ddc86cdbb31c4`, confirmed before_start
changed=false and kept the running containers. After_ready failed in 1837 ms,
before the CLI. Inspection isolated an earlier host-side CA readability guard:
the mapped container UID owns pki directory0700/files0600, intentionally unreadable
to the host platform-docker account. Native test as that account returned
readable_rc=1. Thus the prior actual failure was earlier than client-secret auth;
the client-secret compatibility correction is still necessary based on source.

The admin wrapper now inherits the standard PKI directory mount and reads CA
inside the CLI container at /opt/application/pki/ca-chain.pem. Removed the
host readability check and redundant individual CA bind. No permission widening
or generic runner/Core changes. Added a host-wrapper regression with inaccessible
PKI and a stub Docker command (no target mutation); seven native SZI tests and
shell syntax PASS. A fresh actual plan retry is in progress.

Plan `plan-295449782156ccdc52b53d89`, run
`installer-f8a016ae0abd372c0216d196c686cdc2`, progressed past the host CA issue:
the after_ready script created admin, assigned admin access and set the runtime
password. Independent password-grant and master Admin API checks PASS on both
102/103 with TLS certificate/name validation, one admin, no required actions.
The script failed before temp-admin removal; temp client remains1, DB unlocked.
Its bootstrap CLI config had the private CA truststore, but permanent.config
used to authenticate the new admin did not. The wrapper now configures the
same generated CA truststore for both CLI configs. This preserves the existing
admin/password; the next Apply can finish the partially completed bootstrap.
Shell syntax and seven SZI tests PASS; fresh actual plan retry is in progress.

Read-only user detail confirmed that the imported user profile did not retain
the undeclared platform.installer.bootstrap attribute. The next UI observer was
stopped with its exact owned browser descendants before approval/Start; no new
installation was started by that observer. Existing-admin recovery now accepts a
successful login with the requested runtime admin password before relying on the
optional profile marker. It does not reset that working password. If login fails
and the marker is missing, the script still blocks without password changes or
client deletion. A native inner-wrapper regression covers both cases with stub
CLI commands and proves no create/set-password calls. Eight native SZI checks
PASS; a fresh actual plan retry now tests finishing the retained partial state.

Plan `plan-c651bbabe899a0680a685a6b`, run
`installer-59408184db56196e6bfe6f8d119c37f5`, completed the after_ready bootstrap.
DB query confirms one admin, no temp-admin client and no Liquibase lock.
The password credential created_date stayed1792605948403 before/after cleanup:
the existing runtime password was not reset while finishing the interrupted run.
Independent password login, master Admin API, TLS certificate/name checks PASS
on both102/103 after cleanup; requiredActions is empty and temp client count0.
Safe runtime evidence: szi-admin-api-after-cleanup.jsonl and
szi-admin-before-final-cleanup.json / szi-admin-after-cleanup.json.
Terminal Apply/Verify is still being observed; these checks do not claim it PASS.

That run later FAILED before HAProxy candidate activation at
`Require the expected status on the verified TLS connection` on all three
HAProxy hosts. Direct verified-SNI HTTPS probes to both Keycloak backends proved
root '/' returns302, while '/realms/master/.well-known/openid-configuration'
returns200. The package and QA endpoint override now declare the latter as the
ordinary endpoint.probe (expected200, timeout10). No Core/TLS guard change.
Eight native tests PASS. A fresh actual plan repeats Apply after completed
bootstrap and should exercise both scripts unchanged, then full Apply/Verify.

## Final Keycloak-only installation result, 2026-10-21

Actual React/Wails plan `plan-97d8f5bc64f6ae3435ee9dc1`, revision
`sha256:c533f5579d0a59e18bca5c202ffd89ab4c08dbebe7f6738737aa88f9b375bf2c`,
run `installer-96693c7318c5f2d69c8416ff56ea7e20`: **SUCCEEDED**.
Authoritative events confirm applications:apply SUCCESS,
applications:verify SUCCESS and zero FAILED events. The approved scope was
Keycloak only on node2/node3, infrastructure excluded with SkipInfraVerify.
Project identity remains project-b46aa3f5f57a495f in the separate QA copy.
Runtime bundle remains szi-stage1-20261021-03, digest
sha256:7dae07b25cb25863da2f62ff7ad67483c2b379dd29e85ffa27ae1d70332ad4f0.

- Both keycloak-node2 and keycloak-node3 are running/healthy.
- Before-start and after-ready report changed=false (event912 and1008).
  The existing admin was not recreated or reset; its password credential
  created_date remains1792605948403 across cleanup and repeat Apply.
- Final DB state: users1 (admin), service clients6, groups3, temp client0,
  Liquibase unlocked. No new dump with the runtime admin password was made.
- Independent runtime-password login and master Admin API PASS with verified
  TLS/name on both direct placements and public https://keycloak.evoscada.internal.
  Admin requiredActions is empty; temp-admin absent. Public OIDC probe passed.
- Eight focused native SZI tests PASS. This result does not claim a new full
  Core/Go/frontend regression or visual inspection. Four other SZI applications
  and their integration remain explicitly deferred to stage2.

Safe local QA evidence: szi-install-ui-evidence-succeeded.json,
szi-final-run-summary.json, szi-admin-final-db-state.json,
szi-admin-after-repeat.json, szi-admin-api-after-cleanup.jsonl and
szi-admin-public-api.jsonl under .runtime/qa. They contain statuses/counts,
not credentials or tokens. Installation logs remain in the ordinary runtime.
The temporary RED OS QA source workspace was removed using qa-sync cleanup
(only its remaining root-owned diagnostic directory ownership was corrected).
Owned Wails34117/Vite5174 QA processes were stopped; implementation worktree,
QA project, verified bundle inputs and established runtime secret files retained.

## Master integration, 2026-10-21

Owner authorized committing stage1 and integrating it into master. Implementation
commit3dda665 was merged with origin/master e2b965b4 in e4dbd1fe. The examples/szi
README now describes the observed Keycloak-only installation and required ignored
assets. The main checkout's unrelated generated-password changes were preserved
in recoverable stash fe7c4bd6ec593b80f8f3f7500cf4b5ca9c173607 plus runtime patches,
then restored with staged/unstaged distinctions. Its UI assets were rebuilt from
combined sources; those unrelated changes are excluded from SZI commits.

Post-integration checks on the clean implementation branch:

- Full Go tests and go vet PASS; frontend295 tests, typecheck, lint and build PASS.
- RED OS focused Core110:109 PASS/one existing skip. Registry preparation and
  application-plan20 PASS. Offline unshare46 PASS. SZI native8 and generic
  context-free script runner1 PASS. Catalog/configuration schemas reproducible.
- Regression exposed a lost registry-secret scope argument in the stage1 helper.
  Commit4dbab390 restores existing scoped identities while retaining script-secret
  deduplication. The twenty related tests passed after the correction.
- Full Core regression is not claimed PASS: initial runs failed with the scope
  defect; a final-source fail-fast restart was interrupted before completion.
- Broad PostgreSQL33 tests failed11/errors7. Their stale lifecycle assertions
  target tasks formerly inline in postgresql/tasks/main.yml; both the test and
  that role are unchanged from origin/master e2b965b4. Native provider fixtures
  also failed13 (one assertion/eleven errors), chiefly missing serviceType in
  split_provider_jobs; that dispatcher/fixture mismatch predates this stage.
  These broader gates remain open; no unrelated infrastructure repair is included.

No new installation, password reset, database restore or replacement runtime
bundle was performed during this integration. Previous real Wails/Core install
acceptance remains bound to the exact run and revision recorded above; visual
inspection and final full regression remain unperformed. Clean no-admin dump,
full themes archive and nine JARs were copied into the main examples/szi tree
and remain gitignored as previously requested.
- Native configuration directory/archive reconciliation PASS (six applies,
  changed=0 on repeats, stale file removal and interrupted archive recovery).
- Preservation check:29 otherwise unchanged staged files retain exact original
  blobs; partially staged journal and untracked review retain original bytes.
  All11 ignored binary inputs (nine JARs, themes archive, clean dump) match the
  tested implementation checkout. Backup stash is retained for recovery.
