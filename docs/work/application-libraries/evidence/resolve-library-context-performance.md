# Library context and same-operation resolution reuse

Date: 2026-11-07. Owner requested avoiding a second application calculation
after image preparation and reducing repeated defaults evaluation. Implementation
is submitted for owner-authorized scoped branch publication. The initial native comparison below used temporary source trees;
the subsequent real Wails run used a standard-built, verified and published bundle.

## Changes

- Resolve common defaults once per library/host inside each role invocation,
  including Jinja defaults. Clear this state at the next role invocation.
- Publish typed values using ordinary Ansible facts. Assemble rows from those
  values through the existing preparation action and Ansible merge semantics;
  avoid expanding the entire source defaults namespace again.
- Reuse image-input application rows and their original findings in
  `stages/resolve-runtime.yml` only when the project identity, runtime identity,
  project/catalog paths and plan context still match. Missing/legacy/malformed
  results fall back to the role. Keep the fresh final snapshot, validation and
  existing plan fingerprint proof. No second persistent cache was introduced.

## Same-input measurements

RED OS QA node: 192.168.56.101, platform-automation, persistent SSH identity.
Baseline source: HEAD b4eeb122 for the affected files, workspace
`/var/tmp/platform-installer-qa-ad2c7ea77eb74c148877c73acc0ac11f`.
Changed source: current working tree, workspace
`/var/tmp/platform-installer-qa-4ea7b16390e9493d8a920924b85991f9`.
Both used the same `complex-project` under the baseline workspace, inventory,
catalog path and selected inputs. Runs were sequential on the same node.

Project: SZI keycloak, grant-access, grant-access-audit, grant-access-front,
nginx; SDKU alarm-view-service, alarm-service, data-manager, evo-manager,
evo-scheduler. Both libraries on node1/node2: 20 placements. Actual example
Jinja/defaults and group-role template lookups were retained. This was a
target-free calculation fixture. Empty placeholders for absent Keycloak package
payloads satisfied structural file checks only; they were never installed.

| Scope | Baseline seconds | Changed seconds | Tasks before / after | Role calls before / after |
| --- | ---: | ---: | ---: | ---: |
| Standalone resolver | 116.529, 106.660 | 59.747 | 392 / 332 | 1 / 1 |
| Image-input resolution then runtime resolution and fresh snapshot | 479.293, 529.397 | 75.874, 63.103 | 791 / 343 | 2 / 1 |

The second row measures the calculation/snapshot sequence, not registry network
I/O, image transfer, provider writes or complete Apply. Mean 504.345 -> 69.489
seconds (7.26 times faster). Common-default calls per resolver fell 20 -> 4.
In the final standalone run, common defaults took 8.587 seconds across 4 calls;
row publication took 2.785 seconds across 20 calls. Baseline first run: 33.95
and 41.07 seconds respectively across 20 calls each.

All 20 typed standalone rows matched the baseline exactly. Both final public
snapshots matched baseline, canonical SHA-256
`bacd821c11105aa3d7fa9ebcfebbea59ee7b9d53f895ee7ae8a5ec004bee4114`.
The timing fixture retains existing unrelated project validation findings;
matching snapshots do not imply a valid full installation project.
Timing scripts/JSON are local under `.runtime/qa/verify-record-research/`.

## Regression checks and limits

Execution-node tests passed: application connections native (3), application
libraries (36), project resolution (11), snapshot output (7), playbook
entrypoints (6), project resolution native (5). Eight selected standalone
library scenarios passed, including isolation, typed values, overrides/reset,
failed-first-application reuse and target-free validation; the Redis case was
rerun after correcting a stale expectation, also reproduced on baseline.
Private-key projection test passed. Total: 77 distinct tests.

Regression assertions cover role invocation counts, common-library call counts,
input/runtime/path/plan-context changes, missing findings in legacy results and
original blocked findings. Public snapshot contract is unchanged.

Initial real Wails bridge preflight returned `QA_WAILS_BRIDGE_PREFLIGHT_FAILED`
(exit 1). It was subsequently restored for the separate test below. The native
comparison itself did not modify target services or provider resources.

## Real React/Wails: SZI 5 + SDKU 5 on two hosts

2026-11-07, real Wails development bridge `127.0.0.1:34269`, current working-tree
Go backend and React handlers. Flow: Open -> runtime bind/prepare -> independent
host trust checks -> runtime secret setters/file import -> Project Verify ->
fresh Plan -> ApproveAndStart -> resource preparation -> UI cancellation.
No mocked backend or direct Ansible Apply substituted for this flow.

Project: `C:/devops/qa-resolve-1107/project`, retained project identity
`project-50a1100000000001` to use its established PKI materialization.
Execution Node: node3 / 192.168.56.103. Both libraries are placed on node1 and
node2 / 192.168.56.101-102: ten logical applications, twenty placements.
Infrastructure installation and Verify were skipped through the existing
APPLICATION_LIBRARIES_ONLY flow and its explicit acknowledgement.

The applications are the same SZI five and SDKU five listed above. Actual ENV,
Jinja, resource definitions, scripts and template payloads were retained. Owner
authorized artificial images after the original registry failed DNS resolution
on both application hosts. All applications use one approved local image with
an overridden sleep command; its archive is indexed in the immutable bundle.
No external registry access or application runtime health is part of this case.

Fixture isolation/configuration: library IDs `qa5-szi`, `qa5-sdku`, separate
runtime directories, qualified instance IDs in the copied SZI definition,
separate PostgreSQL names, required endpoints enabled, SDKU KV mount unified to
`secret`. In the copied Keycloak defaults the database password reference matches
the bootstrap script's static reference. Repository example packages were not
changed by this setup. Protected input values never entered project files or
these evidence files.

Bundle: `sha256:aae9d38eed3f468bb679a80d2103964976f017b30c385568b17ed31e5ad04673`,
built on trusted node2, validated and standard-published to active cache, then
bound/activated through Wails. Identical existing payload bytes were reused for
local transfer; complete bundle validation proved the builder manifest matched.

Final saved revision:
`sha256:c37f96c9429d135eaa9ec1561d93af3e049b8d7b45feedc7d5d39feabf0fb9cc`.
Fresh plan: `plan-5bba669be99c3b985dec0e90`.
Run: `installer-10d697fef85c3d261a87bebffb87a12b`.

| Measurement | Time | Result |
| --- | ---: | --- |
| Project Verify RPC through the real React handler | 61.555 s | VERIFIED |
| Fresh plan RPC | 82.014 s | EXECUTABLE |
| Combined approval / Start RPC | 156.196 s | STARTED |
| Resolver inside resource preparation | 143 s | 1 invocation, 20 rows |
| Full applications:prepare | 1575 s (26:15) | SUCCESS |

Resource preparation contains 1746 task starts and 1755 host results, with zero
failed host results. Counts differ because tasks can return on multiple hosts.
Common-default calculation runs 4 times and row publication 20 times. The second
resolver is skipped in the actual execution path, not merely in a native test.

Nonoverlapping wall-time boundaries from journal events:

| Section | Seconds | Time |
| --- | ---: | ---: |
| Initial resolution and snapshot/projection preparation | 263 | 4:23 |
| Placement / image preflight | 529 | 8:49 |
| Provider preflight and runtime input preparation | 201 | 3:21 |
| Resource/provider writes through preparation completion | 582 | 9:42 |

These sections sum to 1575 seconds. The resolver's 143 seconds are included in
the first section. This is a current-code measurement, not a same-context Wails
before/after comparison; native timing improvements must not be presented as
the full Apply speedup. Fifty-app scaling estimates remain unmeasured here.

Canonical stage completion: sequence 3509, 2026-11-07T15:41:26Z, SUCCESS.
Cancellation was requested through the actual UI after this marker; status.json
and result.json both confirm CANCELLED. Six metadata/order tasks of the next
library block started before cancellation. No container launch task started;
full library installation/Verify and visual acceptance are not claimed.

Earlier attempts safely stopped on fixture/environment prerequisites: registry
DNS, incompatible KV mounts, foreign container names, bootstrap password
reference mismatch, and a Vault token returning HTTP 403. The final protected
token was confirmed with HTTP 200 on the exact provider's sys/mounts and sys/auth
using its validated CA, without exposing token values or changing Vault policy.
The final successful stage used fresh namespaced resources; these QA resources
are retained. Temporary source/build workspaces on node2 were cleaned.

Safe local evidence: `.runtime/qa/verify-record-research/wails-results.json`,
`final-metrics.json`, `final-run-profile.txt`, `final-run-diagnostics.jsonl`.
The journal profile uses canonical sequences, avoiding duplicated Wails event
delivery. The observer sampled run state every 30 seconds alongside normal UI
subscriptions. The owner subsequently authorized a scoped commit and branch push; unrelated provider and generated UI changes remain excluded.

## 50 applications: Verify bottleneck analysis

2026-11-07. Owner selected SZI 5 + SDKU 45, each on node1/node2: 100 placements.
SDKU has nine slots for each of the same five application packages. Only ten
application packages are used, preserving the actual package ENV/Jinja and
structured SSO parameters. Slot-based identities were separately fixed and
pushed to master as efe77b5c; the optimization branch carries 0bf425a5.
No other optimization or Go timeout change was made during this analysis.

Execution Node: node3 / 192.168.56.103. The full bundle was built on trusted
node2, validated, standard-published and activated through real React/Wails:
`sha256:e0cdd2fe28574b7cd0129291259a929f75af93294cf1ffc068bea35336c7b071`.
Its components differ from the preceding aae9d38e bundle only in the four
slot-identity/script-selector source files. Current working-tree provider
changes remain included in the QA bundle, and are not part of the master fix.
Saved revision:
`sha256:55263a2b33247d7665de15ab2daeff26362e00bd62aae2bcea269870633520f4`.

Real Wails Prepare returned PREPARED in 454.980 seconds including its automatic
verification attempt. Manual Verify returned UNVERIFIED after 301.231 seconds,
with EXECUTION_NODE_READY_REQUIRED. Go projectCoreResolutionTimeout is five
minutes; timeout/transport failure is presented as readiness failure. The UI
then disabled Services pending its first projection. 149 pending application
inputs had been accepted through the existing Broker, but no Plan/Start/resource
stage was reached. The timed-out read-only Ansible process was explicitly
terminated and the owned Wails process stopped. The owner requested measuring
Verify and proposing optimization rather than increasing the timeout.

### Exact native Verify path, same node and project

The existing measurement script was copied into the ignored QA workspace and
pointed at project-snapshot.yml, matching the Wails BuildProjectSnapshot path.
The copy used the exact saved project, active published runtime, same inventory
and hosts, with no shared-resolution cache paths or runtime secret values.
Two sequential, uninstrumented full calculations took 469.77 and 477.92 seconds
(mean 473.845 seconds, 7:53.845), 1298 task headers each, exit code zero.
These are Core timings, not successful Wails RPC timings.

| Task | Calls | Mean total seconds |
| --- | ---: | ---: |
| Parameters after placement identity binding | 100 | 111.285 |
| Native application-default rendering | 100 | 110.310 |
| Shared library defaults after resources | 4 | 50.565 |
| Identity/context binding | 100 | 22.720 |
| Resolved-row publication | 100 | 17.210 |
| Public-result fact publication | 1 | 16.105 |
| Typed inherited/settings assembly | 100 | 14.560 |
| Resolution store task | 1 | 14.145 |

Resolver-prefixed header intervals total 421.085 seconds (88.9% of Core).
The first three rows total 272.160 seconds (57.4%). Header intervals include
Ansible orchestration between tasks and are not pure module CPU times.

### Causal diagnostics, excluded from baseline timings

A third, temporary standard-library cProfile/TaskExecutor observer captured
selected calls and only parameter SHA-256/lengths, never parameter values.
This instrumented run took 490.079 seconds. Both snapshot observations were
PASS, with no findings and fingerprint
`sha256:5ecd46757dec5ba11e87fa7c6f15bbcc4d04d2371fa065416ba4131224b4debb`.
All 100 seed/second-parameter pairs were observed: 76 equal, 24 different.
Differences were the 18 data-manager placements and six SZI grant-access,
grant-access-audit and grant-access-front placements, expanding IDENTITY_CLIENT.
Deleting the second parameter stage without replacing its work is unsafe.

The selected shared-default task spent 42.168 / 42.735 profiled seconds in
copy.deepcopy (6,041,772 calls), through four template lookups. File-content
reads totalled 0.000479 seconds. Profiler overhead makes these CPU durations
unsuitable as uninstrumented task timings.

Installed Ansible copy_with_new_env copies environment globals without rebinding
lookup/query/q to the copied Templar. A scoped Templar with one variable still
had lookup bound to its original Templar and its full _application_inputs.
Thus the existing library-scope cleanup does not constrain lookup('template')'s
deepcopy context. This was independently reproduced without changing Ansible
or the immutable runtime.

On the same fixture, serialized preparation jobs grew from 461,170 UTF-8 bytes
for 20 placements to 4,237,826 bytes for 100. Repeated library definitions account
for 1,768,400 bytes and deployments for 1,649,050 bytes in the latter.
A tiny, isolated template lookup with those expanded job structures had medians
0.174524 seconds using copied/original-bound globals and 0.001148 seconds using
a fresh scoped Templar. Outputs matched. This is an isolated mechanism probe,
not a measured whole-Verify speedup or a production implementation.

### Proposed next changes

1. Correct the scoped native Templar/lookup binding in the existing preparation
   action. Keep the intended library/host or placement variables, and ordinary
   operator variables/precedence. Exclude unrelated internal job/result payloads
   from template lookup context, preserving documented host-dependent inputs.
2. Render the parameter subtree in its required context without expanding the
   whole application-package alias/ENV. Preserve the seed and typed dependency
   resolution needed by the 24 non-equal cases; render ENV in its own stage.
3. Subsequently avoid full-result Jinja copies in store/publication, using the
   existing reference-based action pattern. Keep persistence and fingerprint
   checks. Those two tasks currently account for another 30.250 seconds.

No new software, persistent cache, process bridge or relaxed proof is proposed.
Validate any implementation with equal typed rows/public fingerprint, the same
100-placement project and two hosts, repeated native timings and real Wails
Verify. A whole-Verify speedup has not yet been measured.

Safe local evidence: .runtime/qa/complex50-1107/final-profile.json,
verify-profile.log, lookup-cpu.json, templar-binding-proof.txt,
lookup-probe-results.jsonl, job-payload-comparison.jsonl and cpu-profiles/.
The temporary native profiling workspace is cleaned after evidence collection.

### Scoped rendering implementation under validation (2026-11-07)

Owner accepted the three scoped-rendering/reference-publication changes. The
implementation stays in existing actions and role tasks; no timeout increase,
new persistent cache or relaxed plan/snapshot fingerprint proof is introduced.
Native template lookup globals are bound to a fresh Templar with the intended
scope. Application parameters retain their seed/dependent rendering stages;
unrelated ENV is not expanded while preparing parameters. Resolution storage
uses an allowlisted variable reference; CLI publication returns a small summary.

A first attempt excluded `_application_inputs` from placement templates. This
is incompatible with existing SZI templates: Keycloak and Grant Access use its
jobs to calculate peer addresses/ports. That attempt produced PARTIAL and is
rejected; its 228.837 seconds is not a successful optimization measurement.
The complete placement inputs are retained. Only previous rows/results and
internal caches are excluded from the placement lookup scope. Library-only
contexts continue to forbid placement-dependent inputs.

Exact same project/hosts/operations on node3, baseline runtime e0cdd2fe:
new baseline capture 504.537 seconds, 1298 task headers, exit0. Changed rendering
330.162 seconds, 1298 task headers, exit0/PASS. All 100 private typed rows and the
public snapshot compare equal, including fingerprint
sha256:5ecd46757dec5ba11e87fa7c6f15bbcc4d04d2371fa065416ba4131224b4debb.
This is a 34.56 percent reduction; the unchanged 300-second Wails limit still
requires further reduction. No real Wails acceptance is claimed at this point.

Remaining task intervals: native defaults 83.951s/100, parameter preparation
75.159s/100, placement context24.322s/100, row publication18.362s/100. These
include Ansible overhead between task headers. A follow-up uses the already
available raw placement's defaults path inside the existing action instead of
passing it through another Jinja expansion of the full application job.

Thirty focused RED OS tests passed (native context isolation, required parameter
ENV, multihost precedence, inherit/reset, snapshot publication, and resolution
identity/mutation proof). Master merge960757fb preserved; affected resolution
production files did not change in that merge. Current optimization remains
uncommitted. Safe evidence is under `.runtime/qa/scoped-verify-1107/`; comparisons
report paths/status/counts without secret values. Raw capture files stay in the
protected temporary Execution Node QA workspace.

### Approved compact placement context

Owner approved a runtime-only `application_placements` context and equivalent
peer-discovery template updates. Existing `prepare_application_connections`
computes the compact map once in its already existing invocation. It reuses
native topology ports for nonliteral/exported placements; only the already
proved literal inputs use standard recursive merge_hash with slot, instance and
host override precedence. Sorted members contain hostId, inventory address and
ports. Existing context-binding task selects only the current library/slot.
No new role, process, persistence, host_vars/group_vars block or per-placement
Ansible task is added. SZI Keycloak/Grant Access and five SDKU templates now
consume the same compact shape. Saved/imported package copies need updating;
repository examples are not automatically written into saved projects.

The same 100-placement project with the two approved SZI peer templates updated
was used for a controlled comparison. The QA control retains the old jobs payload
inside the scoped Templar while otherwise using the same compact-context code
and identical project inputs/hosts/operations. This is an explicit mechanism
control, not an unmodified historical runtime. Its native Verify:327.125s.
Final compact runs:225.832s and219.306s, mean222.569s (31.962 percent less than
control). All three runs contain1298 task headers, PASS/exit0. Private typed rows
and the entire public snapshot compare exactly equal; fingerprint:
sha256:b5a2d044b857a2b48c7198b2849458bc2173a70b5ba9abf051f1de633cfadaa7.

Against the original-template baseline, all100 resolved records still match
when excluding only packageIdentity: the two explicitly changed source defaults
necessarily change their package-content digests. No runtime settings, peer
addresses, port values or credential/resource declarations differ. The old
snapshot fingerprint cannot stay identical across this desired-state source
change; fingerprint validation itself is unchanged, and the identical-input
control/repeat comparison proves deterministic new snapshot identity.

The second compact run's largest intervals: native defaults24.815s/100,
placement context24.359s/100, parameter preparation21.484s/100,
row publication17.570s/100, inherited settings12.817s/100.
Sixty-five focused RED OS tests pass, including seven native/context tests,
38 application-contract tests,12 resolution-identity tests and8 snapshot-output
tests. Tests cover all seven actual peer templates, one/two-host SDKU behavior,
native port reuse, override order, sorted peers, multihost/library isolation and
bounded invocation counts. Seven production Core component hashes match the
verified published bundle exactly. Bundle:
sha256:b07606986949af30b07e58f16ef8046883127ecf399fd735461a49c676d2b2dd.
Real React/Wails acceptance and Plan/Start/resource measurements remain running;
no visual acceptance, completed installation or new commit is claimed.

### Real Wails response-size gate and follow-up

The first real Wails pass activated b0760698 but reported READY_REQUIRED for
Verify. Existing runtime timing proves Core completed in205.558s; the public
snapshot was4,883,525bytes. Both the snapshot SSH response and Core adapter
previously imposed2MiB. Transport truncation was mapped to node unavailability;
this was not a five-minute Core timeout. The transport/decoder now share the
existing16MiB execution-protocol budget via one Core-adapter constant. Event-page
limits, timeout, trust and fingerprint checks are unchanged. New Go tests accept
a valid5MiB snapshot, preserve its fingerprint and reject over-budget input.
Full `go test ./...` and `go vet ./...` pass. SDKU five package digests were
refreshed through the existing Core package loader after the template changes.
The SDKU validation fixture now supplies the compact peer context;28 package
schemas/digests and26 Compose renders pass. The existing missing SZI themes
fixture was restored byte-identically from the already approved QA project to
its ignored expected path; it is not a new download or committed artifact.

After rebuilding Installer (same active runtime, no repeated preparation), real
React handlers/Wails methods returned Verify VERIFIED in217.432s. Saved project
revision:sha256:a2ad38816d72ab2ea5a064acd2619cd3f05728c16de676d6760698a8bb534c2b.
Project identity and100 placements are unchanged. Plan via the ordinary UI
returned EXECUTABLE in323.646s, plan-5d64b97e1005fa2470297df5, application-library-only
mode with infrastructure Apply/Verify skipped. Existing operation timings:
PrepareApplicationImages236.834s (fresh resolve200.626s), BuildDeploymentPlan
80.048s (same-request resolution hit, read0.558s). Combined approval/Start is
still running; the fresh descriptor operation completed234.801s, including
197.557s resolution, followed by image-input preparation. No new optimization
of these Start calls is included in this test. Run/resource timings remain
pending. Evidence: `wails-results.json`, `wails-cap-failure.json` and native profile
and comparison JSONs in `.runtime/qa/scoped-verify-1107/`.

### Closed package inputs across Plan/Start (2026-11-08, uncommitted)

Owner accepted removing duplicated resolution while retaining authoritative
fingerprint comparison. FULL PLAN review PSR-P01 blocked unconditional reuse of
unconfirmed external Jinja inputs. Owner clarified: detect project-local source
changes, keep fresh resolution for truly external inputs. The narrower correction
uses only the existing private resolution cache; no Go lifecycle, operation,
descriptor API, prepared workspace reuse or Start authorization changes.

Root causes: the eligibility check rejected every lookup, including builtin
file/template reads of hashed package assets; it also parsed raw YAML as Jinja,
so YAML-escaped quotes in ordinary SDKU scalars caused parse failures. Canonical
planning disabled shared reads even for a proved closed desired-only result.

The correction decodes YAML for eligibility (Ansible still evaluates values),
proves only literal project-root or current application-defaults-relative builtin
file/template paths, checks containment/no symlink/hashed closure before reading,
and recursively inspects dependencies. Unknown calls/globals, external sources,
dynamic plugins/paths and unproved contexts remain fresh. Dictionary get is
limited to resolver-owned _application_shared data; append/index
are limited to template-local lists, update to local dictionary literals. Package
code may use the documented resolver data contexts and template-local variables;
request operation/selection names remain excluded. Service deployment identity is
the existing service-defaults-only invariant. No new work per placement is added.

Private envelope v1alpha2 prevents older, differently qualified entries from being
accepted. Shared identity includes all actual source bytes, immutable runtime and
controller. Local envelopes additionally retain the original planContext and
stagedProject. A shared result containing its absolute staging path is rejected.
Selection/order/Vault-source changes still reach the existing fresh planner;
they cannot affect the eligible desired-only template context. Start still runs
the existing plan builder and compares project identity/revision/fingerprint.

17 focused RED OS tests passed including the controller-identity assertions;
they include the actual SZI5/SDKU5 package definitions and library assets, YAML
escaping, transitive external lookup, escaping/untracked/symlink paths, source
mutation, shared reuse across contexts and external-source fallback. A final
dynamic-inventory regression was added afterwards. Additional path guards reject
transformed staging paths and symlink/../ traversal before normalization.
The repeated exploratory same-node100-placement Core chain (before those final
eligibility-only restrictions): fresh190.361/186.469s,1298 tasks and1 resolver;
shared25.121/25.649s and24.388/25.063s,9 tasks and0 resolver. All six public snapshots
are identical, fingerprint91d6ef1af7d46d533b757e4bb466e525126f167e7bdc11f2e28b7551c7d7dbbf.
These are native Core measurements, not new Wails Plan/Start timings.

7 native connection tests and8 snapshot tests PASS. The wider30-case library
suite has28 PASS and2 failures in existing path/Kafka topic fixtures. Both failures
reproduce with the pre-change resolution modules in the same QA source tree;
they are not reported as a successful full suite or changed here.

The earlier Wails resource run retained its original immutable runtime and ended
FAILED on node2, alarm-view-service-07-qa5-sdku, application_identity_files preflight
(ANSIBLE_FAILURE_REDACTED). Its wall interval includes an overnight VM pause and
is not accepted as resource-stage timing. A subsequent read-only identity check
with the same account/user/path/PKI source succeeded (mapped UID/GID590823), so the
original hidden failure is not claimed diagnosed. This source change did not
alter that run.

Final version:18 focused RED OS tests PASS, including dynamic/executable inventory,
controller binding, transformed path rejection and traversal before normalization.
Independent TARGETED_RECHECK PSR-P01: APPROVE_WITH_CHANGES, blocker resolved;
PSR-P02/03 superseded with the discarded same-staging/descriptors-v3 design.
Reviewed source/test/ADR patch SHA256:
EFF5EAF4E1BC6AD61E0FF4F4933B8061BAAEE53074AF315C70A6D13AAF0ACAAF.
No further production change was made after review.

Final repeated native100-placement runs on the same node2/source/project/inputs:

| Query | Run1 seconds | Run2 seconds | Task headers | Resolver calls |
|---|---:|---:|---:|---:|
| Empty cache |261.027|256.664|1298|1|
| Shared result, different plan context |36.524|32.578|9|0|
| Shared result, descriptor-style context |31.984|33.901|9|0|

All six complete public snapshots match exactly (same fingerprint91d6ef1...).
Copying the portable project into another staged directory and replaying the
shared result also returns the identical full snapshot:38.024s,9 tasks,shared hit.
These final timings supersede the exploratory prototype numbers above; they
measure the resolution/publication path, not complete Wails Plan/Start.

The final bundle was built on trusted node2, verified/published by the standard
publisher into active cache and rebound/activated through React/Wails. Both
changed production files match the bundle byte-for-byte. Prior bundle b0760698
remains preserved. Current runtime:
sha256:9cc95724061715e32955e87cc7dbe39d43a37b96e54d8ae5488db91b1cda200b.
Saved revision:
sha256:a9554ca6d7d35fbca30c5d693003ca7a8bb07e6dbd50cb20c8e1ecd8b32d7b3c.

Actual React handlers/real Wails Go/Execution Node Core, SZI5+SDKU45,
100 placements, same node3, APPLICATION_LIBRARIES_ONLY:

| Stage | Previous runtime | New run1 | New run2 |
|---|---:|---:|---:|
| Explicit Project Verify |217.432s|47.705s|38.133s|
| Prepare plan |323.646s|173.424s|131.379s|
| Combined approval/Start |570.973s|226.548s|197.313s|

The previous-runtime column is the earlier same-project/node measurement,
not a new interleaved baseline; host/timing variability remains visible in the
two new runs. The stable regression evidence is zero resolver calls after the
initial qualified result, unchanged results and preserved fingerprint checks.
The fresh automatic Core call304.622s exceeded the unchanged five-minute budget
and preparation returned PREPARED with verification error EXECUTION_NODE_READY_REQUIRED.
The explicit repeated Verify succeeded. Cold resolution remains a separate issue;
do not label preparation/first Verify unconditionally successful.

Existing Core timing files were observed read-only during Wails operations:

| Phase/operation | Run1 seconds | Run2 seconds | Resolution |
|---|---:|---:|---|
| Plan: PrepareApplicationImages |60.824|45.000|shared hit|
| Plan: BuildDeploymentPlan |103.994|79.788|request hit|
| Start: BuildRuntimeSecretDescriptors |60.574|51.964|shared hit|
| Start: PrepareApplicationImages |49.028|45.976|shared hit|
| Start: BuildDeploymentPlan |87.634|76.757|request hit|

Runs installer-a2d6284dcd1266ec1d6da212702f6ed3 and
installer-a16518bd96f5d523d8b4d8c6f842e1f2 both returned STARTED and were immediately
cancelled through the real UI to authoritative CANCELLED. Both manifests match
the approved plan fingerprint:
sha256:84702af12a5155d7e20cf0e43d6174df7df98b283c13a30e1ddb7eadf70b64f8.
No full application installation/Verify or visual acceptance is claimed.
Evidence is retained under `.runtime/qa/scoped-verify-1107/`: closed-final-*-results,
closed-relocation-result, wails-closed*-results, wails-closed-core-timings,
closed-run-bindings and closed-reuse-summary JSON files, plus the original
portable input copy. No runtime secret values are included in these summaries.
No commit/push performed.

### Cold placement calculation consolidation (2026-11-08, uncommitted)

Owner requested only removal of unused per-placement namespace loading and
consolidation of the existing placement calculation. No host/base Compose ENV
redesign, cache policy change, timeout increase, Go/UI or Plan/Start change.

The production delta is restricted to three existing files: the
`prepare_application_libraries` action and resolver `main.yml`/`instance.yml`.
Remove the unused `_application_package_<hash>` include_vars and its lazy alias.
The existing action now supports `placement: true`: load application defaults
once, resolve parameters with the existing native templar/merge order, expose
typed parameters to the ENV/default templar, then call the existing row assembler.
The final set_fact retains application_parameters/application_inherited and the
indexed resolved row. Old action modes remain supported. No new production file.

RED OS current-worktree tests:8 native connection/template tests,18 project
resolution tests and8 snapshot diagnostic tests PASS (34 total). Added direct
staged-versus-combined equivalence for two hosts, inherit on/off, typed values,
override precedence and failed Jinja without partial rows. Native role regression
asserts one combined calculation per placement and absence of removed tasks;
existing repeated-role/error-isolation/order cases still pass.

Standalone current-source100-placement fresh calculation:169.051s,898 task
headers, one resolver; previous implementation1298 headers. Placement actions
300 ->100; unused include_vars100 ->0, intermediate parameter set_fact100 ->0.
All complete public snapshots equal the previous source, fingerprint91d6ef1...;
both shared replays also match (29.862/29.329s,9 tasks,0 resolver calls).
Standalone source was synced with qa-sync to node2, then cleaned with qa-sync.
These standalone timings are not used as the Wails acceleration denominator.

Repeated actual React Verify handlers through real Wails Go, same node3,
project `project-50a1100000000001`, SZI5+SDKU45,100 placements on node1/node2:

| Cold Verify | Old runtime9cc95724 | New runtime4d5f062f |
|---|---:|---:|
| Wails wall run1 |258.228s|196.121s|
| Wails wall run2 |262.151s|197.093s|
| Core run1 |253.410s|191.406s|
| Core run2 |257.634s|191.795s|
| Resolver run1 |238.709s|179.241s|
| Resolver run2 |242.152s|179.937s|

All four Verify results VERIFIED; every measured Core record has
resolution.hit=false/source=fresh. Only this project's exact shared-cache file
was quarantined between trials; no service/target writes were made by Verify.
Mean Wails260.190 ->196.607s (-24.44%), Core255.522 ->191.601s (-25.02%).
The historical304.622s cold call is not the comparison denominator.

The standard builder used the same full approved runtime/artifact/image input
on node2. Manifest comparison shows exactly those three changed components;
artifactSources and containerImages are identical. Standard Go validation and
publication PASS. Real UI rebind and node preparation activate:
sha256:4d5f062ff76293ede9ccb6fdd1678f0ec88bd31e0a356b990bb6922e4fde19ce.
Activated source checksums match the built files.
Old/new saved revisions are a9554ca6... / a07b2750... (bundle binding changed).
All100 full calculated application rows have the same canonical SHA256:
5fe38908f7c0ba22d4a53844bf6ad5b9b94296832370e4b2c5a97d5c4328fea7.
Whole Wails snapshot fingerprints differ with the new project/runtime binding,
as expected; no execution-plan fingerprint comparison was bypassed or modified.

First bundle transfer failed before Core with EXECUTION_NODE_PREPARE_STAGE_FAILED:
node3 had1.8GiB free while archive plus extraction require more. After verifying
the full local backup and current9cc runtime, the inactive b076 QA release was
removed (local identical manifest backup retained); free space3.0GiB. Retry through
Wails PREPARED in325.074s including automatic cold verification, without a
verification error. Preparation/transfer time is excluded from the Verify table.
Previous runtime9cc and both full local bundle sources remain preserved.

Evidence: `.runtime/qa/cold-placement-1108/` contains before source files,
native-results/native-equivalence, full native snapshot, Wails baseline/changed
results, row digests, bundle validation/publication, activated file hashes,
first preparation failure and summary.json. No credentials are included.
No installation/Plan/Start or visual acceptance was performed. No commit/push.

### Instance-common and isolated host contexts (2026-11-08, uncommitted)

Owner requested splitting common instance calculation from host-dependent work,
with a potential2x improvement. No new software, production module, package
syntax, desired-state field, public DTO/API or deferred Docker calculation.
The existing shared library/host .env and base Compose remain unchanged; Core
still returns complete effective settings for every placement.

Independent FULL PLAN HOST-CONTEXT-PLAN-01: APPROVE_WITH_CHANGES, zero blockers.
Fixed envelope SHA256:
BEFB84214480BB45342992CBC94CCCC9FE6684296CD3D2E8BC54E2380A0A9EF5.
HC-P01 addressed by a bounded proof over actual fully literal typed inputs,
not by assuming that pure Jinja text is host-independent. Unknown aliases,
unresolved nested strings, filters/tests (including overridden builtin names),
lookups, methods and unsupported contexts stay on fresh native Templar.
HC-P02 addressed by copied/clean host contexts, current vars/ansible_facts
parameter aliases, unchanged controller inventory_hostname and per-host failure
boundaries, including resource/default failures. Good rows survive either host's
failure, in original producer order. HC-P03 addressed by native Templar and
merge_hash, existing row assembler/library rendering, and per-instance in-memory
memo only. No generic dependency interpreter or new persistent cache.

The existing action prepares consecutive library/slot groups and processes them
in one batch. Common library/resource values retain library/host scope. Scalar
render results share only within the same instance and for identical bounded
typed dependencies; memo is discarded between instances and operations. Existing
cross-operation qualification, project identity and plan/fingerprint admission
are unchanged. Publishing rows/findings through standard set_fact happens once,
without custom persistent Ansible facts. Unused library_defaults.yml and
topic_roles.yml were removed after their native logic was consolidated in the
existing action. Production delta:3 existing files changed,2 unused files removed.

37 current-source RED OS tests PASS:11 native connection/template cases,
18 resolution/cache cases and8 snapshot/diagnostic cases. New coverage includes
typed/transitive parameters, unknown aliases, external file rereads, custom and
overridden builtin filters, host port overrides, vars/ansible_facts aliases,
controller identity, one-host failures in either order and resource/default
failures. Native regression asserts one batch per resolver invocation and resets
between role invocations; no plaintext input/result values are logged.

Same source/project/inputs on node2, fresh local result files and sequential
processes (no concurrent tests/builds):

| Implementation | Seconds | Task headers | Calculation action calls |
|---|---:|---:|---:|
| Before (runtime4d5f source control) |152.042|898|100 placements|
| Grouped prototype |96.067 /100.159|178|50 groups|
| Final batch |64.209 /63.372|79|1 batch|

The final batch internally handles50 instances/100 placements, renders4
library/host contexts, performs1025 outer scalar renders and reuses667 matching
scalar results. These are outer field counts, not all recursive Jinja calls.
All complete public snapshots match the before control and each other,
fingerprint91d6ef1af7d46d533b757e4bb466e525126f167e7bdc11f2e28b7551c7d7dbbf.
The prototype exposed repeated include/set_fact/collection cost; batching that
data transfer eliminated it instead of moving work into Apply.

Actual React handlers, real Wails Go and Core on the same node3, same project
project-50a1100000000001, SZI5+SDKU45,100 placements on node1/node2:

| Cold Project Verify | Before4d5f | Afterfe648 |
|---|---:|---:|
| Wails run1 |194.725s|90.722s|
| Wails run2 |190.094s|90.289s|
| Core run1 |185.032s|85.668s|
| Core run2 |185.493s|85.486s|
| Resolver run1 |172.812s|74.179s|
| Resolver run2 |173.534s|73.871s|

All four results VERIFIED, every measured operation resolution.hit=false,
source=fresh. Only the exact QA project's shared resolution file was quarantined
between trials; the intended intra-invocation scalar reuse remains enabled.
Wails mean192.409 ->90.505s:2.126x, -52.96%. Core mean185.263 ->85.577s:2.165x.
No preparation/transfer time is included in these Verify intervals.

Standard build on trusted node2 reused the same full approved offline input.
Manifest diff is exactly those5 Core paths; artifactSources/containerImages are
identical. Standard validation/publication PASS; real UI rebind/preparation
PREPARED217.837s including activation/automatic verification. Runtime:
sha256:fe648cfb6f7d9dded06e9e1a237230cc86796ec35b4285fd34895010fa1e894a.
Saved revisiona07b2750... ->43d62b91... reflects the bundle binding only.
Activated files match the built files and the2 obsolete tasks are absent.
All100 complete application rows have the same before/after canonical digest:
5fe38908f7c0ba22d4a53844bf6ad5b9b94296832370e4b2c5a97d5c4328fea7.
Whole Wails snapshot fingerprints change with project/runtime binding as expected;
execution-plan checks were neither bypassed nor changed.

Before transfer, inactive9cc QA runtime was removed after verifying its identical
full local backup; active4d5f was preserved, and node3 had3.0GiB free for staging.
Prior4d5f/full new bundles remain under C:/devops/qa-placement1108 and
C:/devops/qa-host-context1108. Evidence under.runtime/qa/host-context-1108 includes
before sources, prototype/final profiles/counts, native snapshot, Wails before/
after records, row digests, bundle checks and summary.json. No credential values.
No installation, Plan/Approve/Start or visual acceptance was performed.
No commit/push; unrelated worktree edits preserved.
