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
