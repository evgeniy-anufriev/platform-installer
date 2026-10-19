# Direct resource keys — evidence

2026-10-19, current working tree based on `a5ce142c`, master/origin/master 0/0.
Earlier uncommitted ENV/ports/topic work preserved. Before-image retained locally
under `.runtime/qa/direct-resource-keys-before` for scoped review.

Owner approved direct keys, PostgreSQL `ef-store:ef-store`, and PostgreSQL
`alarms_db` to avoid collision with Kafka `alarms` in the existing flat resources.
No installation, SQL/Kafka writes, automatic project migration or new lock.

Implementation uses existing resource_defaults and standard Ansible context tasks.
Legacy explicit role maps override colliding direct keys; SDKU no longer declares
them. PostgreSQL accounts and JDBC use the same selected resource ID. Existing
database-wide grant behavior remains unchanged. ClickHouse parameters preserved.

Initial focused evidence:

- Frontend focused14 and full260 tests PASS; build and lint PASS.
- SDKU27 package schemas/digests, two prepare jobs,26 Compose renders and one
  shared base PASS on RED OS; no target execution.
- RED OS current-tree workspace:
  `/var/tmp/platform-installer-qa-f22c6cf10c684edaa23174c4cb864a19`.
- `go test ./...` and `go vet ./...` PASS.
- Final full Core suite:81 tests in316.265s,80 PASS/one existing skip;
  `qa_application_libraries`, `test_application_libraries`,
  `test_application_providers`, `test_application_runtime_contract`.
  New native coverage includes two libraries/two hosts, PostgreSQL aliases,
  package/instance/resource precedence, legacy collision/reset and missing or
  wrong-provider keys. Selected resources alone feed the normalized projection.
- All26 SDKU applications: native resolver and Compose rendering PASS,
 440 tasks, changed=1 only for a synthetic QA artifact, failed=0.
- An initial broader run exposed an uppercase account-ref/missing second-library
  default in the new fixture and stale expectations of previously owner-removed
  field-name restrictions. Fixtures corrected; security test payloads now exercise
  retained private-key rejection instead. Production security policy unchanged.
- Explicit ef-backend YAML parse on RED OS plus local/remote SHA256 equality PASS:
  `environment`, `image`, `ports`, `provisioner` are siblings under `defaults`;
  `provisioner` is not an environment variable. Schema validation PASS.
- Runtime42:907 components, digest
  `sha256:2dbefe8b035d3d00664e4be8fb33b2737d12b9d5a3307458f6d3713456d72af3`.
  Standard build on node2, local component hashes/validation and standard active
  cache publication PASS. Runtime41 retained locally. Four changed runtime files
  match current frozen source. No hand-copy into active cache.
- Real Wails staging initially returned
  `EXECUTION_NODE_PREPARE_STAGE_FAILED`: node3 had2.4GiB free, below the archive
  plus extraction footprint of the1.9GiB bundle. Handler completion is now awaited
  explicitly by the QA driver instead of accepting a transient READY observation.
  Runtime39 was revalidated locally, its manifest hash matched the inactive remote
  release, and current symlink was checked before removing only that old QA release.
  Runtime40 and active41 were retained. Owned node2 build/input42 removed after
  local907-component verification; shared acquisition input preserved.
- Successful actual React/Wails flow used an isolated project
  `.runtime/qa/direct-resource-ui-project`, real bindings and Core42 on node3.
  Preparation returned PREPARED; Verify returned VERIFIED. Resources: select
  ef-store from defaults without copying name, override to custom-ef-store,
  clear back to ef-store; change alarms_compact to sdku-alarms-direct-2 then
  clear back to sdku-alarms-compact. Five Save/Verify points PASS; both KNP topic
  ENV consumers followed the resource name. Unused topicBindings controls absent.
  No node rebind was needed during the successful CRUD flow.
- Save/reopen preserved exact revision
  `sha256:73736eea45b9197015911666af14e8414de81b7caf26b3dae751d31990ebcc99`;
  authored resource-name overrides and topicBindings remained absent after reset.
- Fresh real UI plan `plan-92ab0cae0c53795159d68260`: EXECUTABLE,
  skipInfrastructureVerify=true, exactly APPLICATION_LIBRARIES_APPLY plus
  APPLICATION_LIBRARIES_VERIFY. approved=false; no Start/run/result. No server
  application installation, database/table/topic mutation or working-project edit.
- Previous context-loss observations remain historical limitations; no production
  lifecycle change/fix is claimed. Initial transient READY was not accepted as
  completed preparation; successful evidence awaits actual handler return.
- Owned RED OS source/test workspace cleaned with qa-sync; verified local bundles,
  nonsecret evidence and the isolated UI project retained. Shared acquisition
  input and active runtime preserved.

Final reviewed subset31 (excluding docs/CURRENT_STATE):
`881ce20a2eed2d9be0b0e7ba00fbe49daad6aa1cc219d1275b521a5a0d9c18cf`.
Initial frozen subset hash was38ba2130; only README ownership-preserving migration
clarification changed afterward. No production-code delta after the frozen review.
Hash is SHA256 of compact JSON `[path, sha256]` pairs in reviewed manifest order.

Visual inspection and target installation are outside this acceptance.

Independent [FULL DIFF](../reviews/direct-resource-keys-diff-review.md): APPROVE,
zero unresolved blockers; DIRECT-P01 RESOLVED, no new findings/overengineering.
Final source identity rechecked after evidence/state updates; unchanged.
