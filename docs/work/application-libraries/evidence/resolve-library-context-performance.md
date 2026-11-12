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

### Owner-requested installation preflight control, 2026-11-08

This later test exercises real React handlers and Wails Go Plan/combined Start,
using the same project-50a1100000000001, SZI5+SDKU45 / 100 placements on node1/node2,
Execution Node node3, artificial test images and retained complex Jinja/ENV.
The comparison is 4d5f062f (before the last host-context batch, retaining earlier
optimizations) versus fe648cfb. It is not an entirely unoptimized master baseline.
All six previously active qa78-static Kafka/Registry units were stopped throughout
both controls and restored afterward; all six returned active. No Core code changed.

Both runs selected APPLICATION_LIBRARIES_ONLY with infrastructure Verify skipped,
the same fixed runtime inputs and all 100 placements. The actual React cancellation
handler stopped each run after exactly 20 successful preflight context records,
before provider writes/container installation. Both terminal states are CANCELLED;
zero failed TASK_COMPLETED results. Cancellation diagnostics do not mean a task
failure. This is a bounded preflight comparison, not completed resource-stage or
full installation acceptance.

| Measurement | Before 4d5f | After fe648 |
|---|---:|---:|
| Warm explicit Project Verify after node preparation |32.434s|33.193s|
| Plan |117.181s|122.221s|
| Combined approval/Start to STARTED |181.014s|190.181s|
| Apply start to Docker preflight boundary |863s (14:23)|542s (9:02)|
| Task headers before that boundary |938|119|
| Resolver role task headers |888|69|
| Docker preflight boundary through 20th context |1155s (19:15)|1054s (17:34)|
| Task headers within that interval |712|712|
| Apply start through 20th context |2018s (33:38)|1596s (26:36)|

The observed preflight interval decreased by 101s / 8.74%; total Apply-through-20
by 422s / 20.91%. The optimized batch calculation is one invocation, 59.390s,
for all 100 placements. Complete calculated rows retain canonical digest
5fe38908f7c0ba22d4a53844bf6ad5b9b94296832370e4b2c5a97d5c4328fea7.
Thus the last batch change reduces calculation/task overhead but does not remove
the sequential placement preflight; long preflight also reproduces before it.

Limits: one pair, not repeated-timing acceptance. Ansible selected node1 first in
the baseline and node2 first afterward; the first 20 therefore cover different
target hosts even though the full desired project, selected scope, inputs and EO
are unchanged. Host ordering/state and VM load prevent attributing the exact
8.74% to the code change. Warm Verify results here do not replace the earlier
repeated cold Verify comparison. Existing runtime preparation/transfer timings
are excluded from the table's preflight intervals.

Before run installer-ea83ad8ce4701ddac7e790054cd77a23, revision a07b2750:
Apply18:35:18Z, preflight18:49:41Z, twentieth19:08:56Z.
After run installer-65bfc9cc56927e21efc1965f7c74e923, revision43d62b91:
Apply19:21:20Z, preflight19:30:22Z, twentieth19:47:56Z. Times are UTC.
Authoritative redacted remote events, per-task profiles, input-row digest and
comparison JSON are under .runtime/qa/full50-1108; browser event duplicates were
replaced with the execution node's events.jsonl for the final counts.
Full prior infrastructure service Apply/Verify passed across recovered attempts,
not one uninterrupted installation; this control does not claim otherwise.
The final active/bound runtime is fe648cfb. No commit/push was made for these tests.

The 2026-11-09 preflight follow-up resolves the selected job and its compact
template context from a placement index at role entry. Snapshot-derived template
inputs and distinct library roots are prepared per target. A checked placement
publishes only its result fields under its index. One final task combines those
fields with the original jobs in order for the existing Apply and offline archive
consumers. Direct role calls still use their existing inputs.
Focused RED OS Ansible 2.18.15 checks: 11 preflight, 4 path/ownership and 6
offline archive tests PASS. The new regression runs the production preflight
tasks with a Docker CLI fixture and checks host selection, placement order,
rendered template context, offline source and one collection per host.
Real Wails acceptance and comparable performance timings for this follow-up are pending.

Shared Compose/ENV follow-up (2026-11-09): classify the selected base template
sources once on the controller. Reuse native rendered content in host-local
facts only for matching library inputs. Application data, dynamic host fields,
external lookups and unsupported template constructs use the ordinary per-placement
lookup. The existing shared-file consistency check consumes the same job fields.
Focused RED OS results: 12 preflight, 4 path/ownership and 6 offline archive tests
PASS. Stock SZI and SDKU templates qualify. The native fixture exercises one
shared base/ENV entry for two placements, distinct base results for differing
library context, and fresh rendering for application-dependent templates.
The standalone Apply playbook passes syntax checking.

Real React/Wails follow-up on 2026-11-09 used project-50a1100000000001, the same
100 placements, fixed session inputs and offline artifacts on EO node3. The
first bundle e4f500ea, run installer-97b3652a5d41bd15c5c0d577b723dca6, failed
before the first placement in the library-root lookup. Read-only reproduction
from the saved project and actual runtime-job preparation isolated that task.
It now consumes the discovered account and home directly. The corrected task
passed the reproduction on node1 and node2.

Retry bundle sha256:20280f6defb7068dd1b8f3675ee1f8e5736d31021f6a491248edbf9512775207,
revision sha256:39fee05d71119d358590d42afb33450af41d863d8983e0931e04ac8908c67a37,
run installer-d0abb638d8454884314c0bab4c493ab3. Preparation231.783s,
Verify VERIFIED44.588s, Plan154.861s, combined Start STARTED245.535s.
Apply09:26:39Z, Docker preflight boundary09:40:55Z, twentieth10:00:50Z.
Preflight1195s with369 task headers,
Apply-through20 2051s. The first20 completed 10 on each of node1/node2,
zero failed task results, one shared-file cache publication and nine skips
on each host. The reference fe648 run completed its first20 on node2:
1054s preflight,712 headers,1596s Apply-through20. Timings do not demonstrate
a speedup under the differing host order and VM load. Compose rendering
and agent configuration account for203s and136s of retry task intervals.
All100 rows retain the same canonical digest as fe648.

The browser event stream stalled during the retry. The authoritative remote
events drove the bounded stop via the real Wails Go cancellation binding.
Terminal CANCELLED, no provider writes or full installation acceptance.
All six qa78-static Kafka/Registry units restored active. The corrected bundle
remains bound and activated. Safe results and remote events are under
.runtime/qa/full50-1108.
The corrected source also passed 12 native preflight tests and the discovery
cache test with the existing platform-automation rootless Docker account.

Compact-context follow-up (2026-11-09): keep original runtime jobs on the
controller, prepare host descriptors and shared-file keys once, and index the
registered output before templating each selected job. The existing Apply
input list is still assembled at the end. Focused native tests:12 preflight,
4 paths,6 offline archives PASS. Three alternating CPU measurements with
the same 20 rows and a small probe template yielded identical rendered values.
The sample scope shrank 4,802,773 ->330,016 bytes per host and median rendering
CPU14.456s ->0.342s. This measures the context-copy mechanism in isolation.

Actual React/Wails bundle8000aada / revisionf834a319, run
installer-aa49ee40c74bef63aeca8ed592e0fe42. The manifest differs from20280f6d
only in the three preflight implementation files. Same artifact/image records,
project inputs, resolved100-row digest and first10 placements per target.
Both runs used EO node3 with qa78-static paused. A single pair does not
control background load. Same20 contexts,369 task headers and zero failed
task results. Shared-file publication once per host and nine skips per host.
Wails preparation258.056s, Verify39.639s, Plan146.571s, Start221.886s.
Apply10:37:15Z, preflight10:52:09Z, twentieth11:13:34Z. Preflight1195s ->1285s
and Apply-through20 2051s ->2179s. Task intervals: Compose203s ->130s,
Vault Agent136s ->85s, selection/account74s ->63s, template context76s ->163s,
ownership markers69s ->124s. The targeted render tasks improved but the
total regressed in this observation. Wails cancelled after the twentieth
placement, before provider writes. All six qa78-static units restored active.
Safe logs and matched CPU probe results are under .runtime/qa/full50-1108.

The next source change used the existing selected job and template context in
the preflight set_fact. The node3 comparison loaded native jobs from the
saved run above and alternated both task definitions on the first10 placements
per target. Three runs matched all output fields, including the direct-role
fallback check. Template CPU median10.977s ->5.700s for20 placements.
The existing focused native preflight suite passed12 tests.

On the same node, replay of the saved100-placement snapshot (10,948,009
serialized bytes) separated Ansible argument templating from Core action
execution. Selection, Vault, providers and runtime consumed18.682s median CPU
to prepare arguments before the change and0.006s after. Each action's output
matched with explicit and implicit snapshot input. Existing endpoint arguments
and the fresh snapshot construction remain in the play. Apply's task listing
contains one Vault projection action, previously two, and the redundant
provider snapshot copy is gone (85 ->83 statically listed tasks, syntax PASS
for both playbooks). The native localhost stage replay passed with
all100 jobs, eight task headers including fixture setup and assertions, one
Vault projection action and102.5s wall time. These probes did not run target
operations or establish full Apply latency. No replacement bundle was
activated for Wails. Node3 had1,138,061,312 bytes free against1,280,980,022
bytes in the existing full bundle.

The subsequent baseline Wails run on8000aada, installer-12a97979e7dadb62cc63fac9590a179c,
was cancelled at owner request after4:47:46. All100 placements passed preflight.
PostgreSQL consumed1:31:45 including29 account write tasks with a152.386s
median callback interval. The staged bundle was not activated. On node3 the
read-only render replay used a67.2MB reconstructed scope and synthetic
credentials. The same SQL length took30.19–36.54s with the large scope
(11.34–13.04s CPU,13.70–21.81s runnable wait) and0.049–0.068s with the
narrow scope. The historic callbacks do not separately time SSH and SQL.
Instrumenting the native lookup in one further paired render confirmed equal
SQL text. The full render took30.790s, including30.387s in deepcopy of the
template variables (12.676s CPU and14.272s runnable wait).

The next changes reuse deployment grouping for PostgreSQL accounts and validate
already collected path observations once per target. The isolated RED OS
comparison used the same fixture per size, native Ansible and a fresh local
PostgreSQL instance per variant. Account SQL launches5 ->1 and20 ->1;
preflight+accounts task headers32 ->20 and77 ->20. At5 apps first/repeat
12.832/17.479s ->9.577/12.791s. At20 apps43.832/54.139s ->19.176/30.658s.
The20 separate psql write calls totalled1.509s during initial creation and the
single batched invocation took0.201s. All expected roles and schema grants
were present and repeat returned changed=0.

The native placement fixture used one target and stubbed Docker discovery.
Two runs at5 placements yielded29.123/30.699s ->26.649/26.288s and194 ->181
task headers. At20 placements129.763/132.349s ->102.189/102.509s and734 ->676
headers. Paths were read once in both variants. All Compose values and output
placement order matched the fixture. This comparison covers the ownership
batch, with rendering and remaining placement checks still scoped per app.
Focused native tests passed for the foreign owner marker and PostgreSQL grant
parity and repeat. Apply syntax check passed.
No full Wails run was requested for this slice. Safe metrics are in
.runtime/qa/full50-1108/pg-preflight-batch-measurements.txt.

### Single-process preflight Wails retry, 2026-11-10

React/Wails on the same SZI5 + SDKU45 QA project, node3 as Execution Node,
50 placements each on node1 and node2. Both Vault file imports passed in
a fresh dev-only picker session. Run installer-efbfcea7db5ee23f2dfd2cec648e94ce
failed at Docker account preparation with no provider writes. The action ran
outside the role and required an optional registry config variable that the
direct benchmark had supplied explicitly. On node3 the same native probe
without this input returned APPLICATION_PREFLIGHT_CONTEXT_INVALID in the
previous bundle and passed with the fix. The fixture checks both the fallback
and explicit registry path. 20 focused RED OS tests passed.

Retry installer-18522578b7197413fc0f7089343a2807 used saved revision
5fadacfa85624e7dabd683b3741a66ec37f3c118bde0fa3df3438b587e8e519c and active
bundle a6b699730fce6f9de3b50a2da50a4a5fe54d5895ac22a45cf65b99248277be3b.
All six runtime payload hashes matched the failed run. Node preparation
306.332s, Verify 49.534s, Core service projection 54.655s, plan 166.395s and
combined approval/Start 266.248s. Apply to preflight 921s. Preflight to the
first read-only Vault check 3290s and 1001 Ansible task starts. All 100
placement records and the selected offline archive barrier succeeded.
Wails confirmed CANCELLED before provider write tasks. There were zero
failed Ansible task results. This was one complete boundary measurement.
The older 5120s Wails measurement is an observed comparison, and the
1800s preflight target is still unmet.

Largest intervals between task starts were Vault Agent rendering 247s,
image-source selection 229s, Compose and library rendering 224s, and
placement result assembly 177s (50 task starts each). Final host result
publication took 160s with one task start. Safe evidence is in
.runtime/qa/full50-1108/wails-batched-100-docker-default-results.json and
.runtime/qa/full50-1108/wails-batched-100-events.jsonl.

### Batched placement preflight Wails comparison, 2026-11-10

PFB-D01 preserves the original phased Ansible path for unproved template
dependencies and current or cross-host facts. PFB-D02 checks the common
library path, Compose and ENV bytes before the archive barrier and provider
stage. The independent targeted recheck approved both corrections. A
subsequent admission refinement excludes Jinja names that are assigned and
never read. The focused RED OS fixture covers that case, dynamic hostvars
and digest, shared-output conflicts, protected source reuse and one registry
probe for distinct requirements sharing the same approved observation.

Real React/Wails run installer-6f01e840765e41069469086b865ea52f used saved
revision 0ca6c7da7464d23ffe171c12255cbd51840a38dfb98d413ceb1bdbc8045c59a3 and
bundle 12aef47864a1dd70bbabe27abe41f5901d4dd2995235881ed838ee06b0be34e3.
Same QA project, SZI5 + SDKU45, node3 as Execution Node, 50 placements each
on node1 and node2. All six runtime payload hashes match the baseline.
Preflight 3290s to 363s, task starts 1001 to 72. Apply to preflight 889s,
Apply to the stopping boundary 1252s. Prepare 301.418s, Verify 61.970s,
plan 212.010s, approval and Start 301.843s. Placement rendering and result
assembly took 140s across 50 task starts. Host publication took 33s.

All 100 placements and the offline archive barrier passed. Zero failed
Ansible task results. The terminal state was CANCELLED during Vault
preflight, with no start marker for the provider resource-write stage.
One matched Wails comparison, no full installation or visual acceptance.
Safe evidence is in .runtime/qa/full50-1108/wails-pfb-100-results.json,
.runtime/qa/full50-1108/wails-pfb-baseline-events.jsonl and
.runtime/qa/full50-1108/wails-pfb-100-events.jsonl.

### Consolidated preflight Wails comparison, 2026-11-12

Execution Node node3, 50 placements each on node1 and node2. Inventory and
package files were byte-identical across projects. Artifact records, image
records and target platforms matched between bundles. The candidate changed
only preflight components and used bundle digest
a137acb15b021506bccaf242c56ed90525ce6e23f511c6028960d13b70c42eae.

| Run | Preflight seconds | Ansible task starts |
| --- | ---: | ---: |
| installer-b3c588298a65b2d14f4c7eef01b6031e | 64 | 72 |
| installer-ec6dfae2892159e9e3627785f628fd9a | 61 | 72 |
| installer-da0b1ec0503650abd5f6b0c4cc484bb3 | 53 | 23 |
| installer-bbed57ca64c88f11292355321e6f389f | 38 | 23 |

The measured interval runs from host preflight initialization to the first
Vault provider preflight task. Each candidate run had one fast placement
task start and two successful host results, zero failed tasks and a
confirmed cancellation before provider writes. Focused tests also cover
the dynamic-template and registry paths.
