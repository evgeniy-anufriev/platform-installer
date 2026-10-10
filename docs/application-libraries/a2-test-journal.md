# A2 — implementation and test journal

Base: `ac4340be8693c3068dc631be91975a22947aab32`, branch
`codex/application-libraries`. Owner authorized implementation on 2026-10-10.
PLAN gate: [independent TARGETED_RECHECK APPROVE](a2-plan-review.md).
Current status remains in [CURRENT_STATE](../../CURRENT_STATE.md).

## Scope and environment

Standalone application materialization/image delivery/rootless Apply/Verify.
No A3–A8, Go/UI changes, provider mutations, image build or unrelated acquisition, runtime
bundle release/publication or Installer Start. The existing planner guard stays.
Primary QA: RED OS node1 `192.168.56.101`, `platform-automation`, existing SSH
identity, strict host-key checking and sudo -n. Sources transferred/verified with
qa-sync; runtime image archive fixtures are outside portable source fixtures.

Existing probe image on node1 confirmed read-only:
`sha256:acd94e424cb685723e768de1e1b0a7f98ffe5b491f4666a6a89888a31bf64ebb`, Linux/amd64.
Docker account UID is discovered (`1002` on this node); no assumption of UID1000.
Node2 Docker daemon is present, original probe tag absent at initial inspection.
Node2 ED25519 trust fingerprint matched node1 and workstation known_hosts.

## Contract/source choices

- Package render descriptors extend A1 allowlisted manifests; no package task execution.
- Readiness/config_files are normal application settings.
- Native `platform_artifact_lock` uses the existing artifactLock slot and its
  allowed `x-container-images` extension; conflicts with project.yml block.
- Typed image authority/result use v1alpha2 dispatch, preserving RPM v1alpha1.
  Shared authority constructor is used by RPM planner and standalone caller.
- Existing bundle manifest byte digest anchors the selected component SHA256/size.
  Synthetic QA image fixture is not a published execution-runtime release.
- Built-in tasks plus existing Compose CLI; no new collection dependency.
- Config digest is derived from sorted destination/content-hash pairs. Managed
  labels plus native Compose reconciliation preserve retry activation; Verify
  compares expected files, disk checksums, label and native config hash.
- Files/instances require ownership markers/labels; host-local atomic guards
  are released in always. Abandoned guards require explicit recovery.

## Initial focused checks and QA corrections

1. First RED OS focused run: A1 15 + existing artifact source 4 = **19 PASS**.
2. New contract run initially found a schema `$id`/relative-reference mismatch;
   local canonical HTTPS schema IDs corrected. New 8 cases then PASS.
3. First real Apply stopped before mutations: QA inventory omitted explicit
   localhost; corrected so controller receives ordinary group_vars.
4. Next preflight exposed missing declared ansible_host in the local QA target;
   snapshot reported `DNS_HOST_ADDRESS_UNRESOLVED`. QA inventory corrected.
5. Runtime package loader then exposed a nonstandard `contracts_root` attribute
   assumption. Reused standard SchemaValidator.schema_root and added a package
   validation regression case. A2 preparation now returns safe status/code
   separately from its private rows.
6. Current focused run: A1 15 + artifact source 4 + A2 9 = **28 PASS**.

Original failed Apply runs are retained as failures, not acceptance. Recovery
tests dependent on an initial successful Apply were unavailable/skipped in those
runs. Private logs/fixture archives stay on the QA node pending cleanup; no raw
inspect/config/environment is copied into this journal.

## Required remaining evidence

Real Apply/Verify/repeat, isolation/interrupted config activation, multi-host,
registry and offline delivery, bounded negative scenarios, affected artifact/Core
regression, independent FULL DIFF review and final source/cleanup audit remain
open until recorded below. No A2 acceptance or DONE is asserted here.
Existing probe does not read arbitrary config at startup; labels/IDs/disk evidence
do not replace the separate application-consumption test prerequisite.

## Public registry QA image (owner clarification)

A2 now uses docker.io/library/nginx:1.28.0-alpine for startup config consumption.
Linux/amd64 platform manifest:
`sha256:09ab424a8c788f8d0fe3a64429f6d19dfa526885c8609b748d0943a75dcb9f8c`.
Image ID checked after the RED OS pull:
`sha256:c318e336065b17ff460aeac6d14bce5d0b13e35f25d5cb1843b635359fc00c9a`.
Only this public test-image acquisition is authorized; no build/provider mutation.
The prior local-probe run completed 2 real QA cases in 433.685 seconds: standalone
Apply/Verify/clean repeat and interrupted-state activation/isolation. That run
proved IDs/labels/files, not consumption of mounted config by the old probe.
The replacement Nginx fixture checks actual HTTP values before and after recreate.
Public-image registry/offline QA remains pending until recorded with its result.


## Frozen DIFF review identity and final focused checks

HEAD: ac4340be8693c3068dc631be91975a22947aab32; branch codex/application-libraries.
43 changed/new files in ansible-core, contracts, examples/valid/application-runtime.
Review fingerprint:
`39ce43430fdaf6c8dd2fcd88f0239cd4549c87bbc1d9542eb0d1a2ab2bb883be`.
Each sorted unique path is prefixed by lowercase SHA256(file bytes) and a space;
joined with LF including a final LF, then SHA256 over UTF8 bytes. Documentation
is outside this source fingerprint. FULL DIFF is a separate gate from PLAN.

Final-source RED OS focused runtime suite: **10 PASS**, 0.143 seconds.
Shared-env secret/bounds and alternate-entrypoint rejection added; the earlier
combined run was A1 15 + RPM 4 + A2 9 = 28 PASS, before these bounded changes.
Catalog check PASS:
`sha256:4507a53a8984bfa7c0c284acb29b407cfce3130240450073c8f8b0f0accd8b5f`.
Configuration-schema reproducibility PASS.
Source workspace: /var/tmp/platform-installer-qa-3c460ee3d1e448d19fd888e0794fa4f0.
Public multi-host QA and broad regression source workspace:
/var/tmp/platform-installer-qa-8e70e1a7bd564e1d8805dc5f382a56bc. That earlier copy
precedes the final launch/shared-env hardening; do not present it as a full final
source acceptance. Runtime-only SSH identity is delivered under .runtime/secrets
for node1 to node2, and will be removed by verified workspace cleanup.

## FULL DIFF gate: BLOCK

Independent review returned **BLOCK** with A2-D01 and A2-D02; exact envelope and
smallest corrections are in a2-diff-review.md. A2-D03/D04 are nonblocking.
Source identity remains frozen at 39ce...; no automatic correction/recheck.
Implementation stopped under docs/agent-procedures/review.md. Existing QA runs
may complete and cleanup, but do not fix the two code defects. A2 acceptance
remains open; no next-stage authorization is implied.

## Owner-approved corrections after FULL DIFF

Owner response: «Принимаю оба блокера» to the correction/TARGETED_RECHECK question.
Only D01/D02 corrections and one targeted recheck authorized; no new FULL gate.
D01: preparation checks archive descriptors only; all target-selected offline
bytes are verified by a controller-side filter in the global preflight before
any materialization. Registry never needs optional fallback bytes/bundle.
D02: managed local reference is derived from the full config/image digest.
Operator localReference is optional and, if present, must equal the derived
reference. A mismatched existing reserved tag blocks before writes. No daemon
registry/lock or persistent identity store was introduced.
Focused tests added for deferred archive selection and digest-bound references.
Real QA additionally uses the public Nginx alpine-slim variant for different-image
parallel library runs; pinned platform manifest:
`sha256:eb8c00e3f75d52947cbfe3cc352671e70bcb78f850be8b64e6bf9652ee8853de`,
config ID `sha256:72c83a2a01fe2ae843fc2bdd4c9bb73064f58215f93a226445a1e443806c4f3c`.
Both identities retrieved from the same public repository API; actual delivery
identity remains to be proved by the runtime QA. No image build/provider changes.

## Targeted recheck and final QA in progress

The single owner-approved DIFF TARGETED_RECHECK returned APPROVE_WITH_CHANGES:
D01/D02 RESOLVED, zero blockers. D03/D04 remain nonblocking; see exact scope and
fingerprint in a2-diff-review.md. No automatic review budget remains.

Corrected focused tests: 31 PASS (2.781s); network-isolated execution: 31 PASS
(3.690s); Apply/Verify syntax PASS. Docker 29.7.2 rejected tag@digest manifest
inspection but accepted name@digest for the same pinned platform manifest.
A bounded URI normalizer strips the final tag for both probe and pull, preserving
registry ports and the locked digest. Focused final suite: 32 PASS (2.244s).

Earlier public two-host run: test_01/test_02 PASS, registry test_03 FAIL;
3 cases in 1836.470s. This failure is retained, not replaced by later evidence.
Final public runtime copy: /var/tmp/platform-installer-qa-a692181b93e74b2f84690ed0df5bb2ea;
source fingerprint a9e4d5a8bd8a79346d34802841a5a552c75ca8eebf10227cd3db5c72deabce23.

Broad regression on the earlier copy 8e70e1a7bd564e1d8805dc5f382a56bc:
526 cases, 3214.345s, five errors / 19 skipped. All five errors are existing
test_pki_single_pass_resolution subprocess TimeoutExpired at 180s; no A2 failure
reported in that run. Isolated unchanged PKI cases are being rerun. This is not
a final-source full PASS. Another Installer run was observed on the same node;
it is preserved and no causality is asserted from concurrent workload alone.

QA cleanup correction: Compose network ownership uses the actual project name
(including library ID), rather than container name. Only exact QA-owned labels
are removed. A separate healthcheck case exercises healthy readiness/clean repeat,
unhealthy Apply failure and read-only Verify rejection. These checks remain
pending until their terminal results and cleanup are recorded.

The post-recheck deltas are bounded: registry URI normalization plus its unit
case; QA exact-network cleanup/failure evidence and explicit healthcheck case.
They do not alter source precedence, deferred archive validation or image-ID
binding. Final 43-file fingerprint:
`7e25425262c86fa124e4449b9c2193162bd1cce9eea2498ef2cf9e26080ccf63`.
Healthcheck uses separate native fixture ports 28280/28281 and QA source
/var/tmp/platform-installer-qa-fdc893c643c048ac879552240e0ebaff.

Final network-isolated contracts: **32 PASS**, 2.274s (A1 15/RPM 4/A2 13),
on source c88a884d3a0f44bbbcb7d41b0ce9b260. A first invocation used two incorrect
module names, causing loader errors only; corrected explicit module names passed.
That source workspace and its private QA key have been removed by qa-sync cleanup.
Completed failed fixture roots cmkxpljh/icls092x/1xfx08pc/x_7ha2xb were removed
after preserving concise failure evidence here. Empty networks of exact project
a2qa-x_7ha2xb were inspected for matching Compose labels/no attached containers
and removed on node1/node2. Current QA resources remain until terminal results.

The isolated unchanged PKI rerun also failed: 5 cases, 900.689s, all five
TimeoutExpired at the existing 180s subprocess limit. The affected fixture uses
synthetic local hosts/private PEM/PKCS12 roots, not installed PKI or Vault.
At that checkpoint no timeout increase, test skip or PKI production change had
been made. A bounded diagnostic rerun of the unchanged fixture confirmed the
last captured task at 180s: `Verify candidate truststore alias and entry type`.
The test-only native play limit is now 600s to permit real RED OS PEM/PKCS12
verification; assertions, production PKI and test coverage are unchanged.
Five cases are rerun on fresh source ddd8af41f25a4a54a3b95638398a08e3.
The broad regression gate remains open until that result; isolated A2 evidence
cannot replace it. This test budget change is a QA-only delta after review.

Performance observation during parallel QA: the CSPA scoped native Apply
(one container on node1, changing to the pinned slim image) took approximately
307s, from private log creation to its final recap write; node1 ok=81/changed=6.
The parallel SDКU scoped Apply on two hosts took approximately 335s and reported
changed=0 on both. These are complete playbook timings under concurrent workload,
not first installation on an empty daemon or isolated Docker startup latency.

Terminal final public multi-host run: **4 PASS / 1 ERROR**, five cases in
3072.642s. Cases 01–04 passed (offline/repeat, interrupted activation/isolation,
registry with missing/corrupt unused fallback, selected corrupt fallback rejection).
Case 05 parallel Apply and Verify passed; its final combined repeat exceeded the
QA subprocess limit of 360s. It is not a complete PASS. Its older harness did not
retain captured output on TimeoutExpired; the concise terminal error is recorded
here and that cleanup limitation is corrected in the current harness.

Separate healthcheck case 06: **PASS**, 1429.154s, project a2qa-8mmenu1e.
Actual healthy readiness/Verify/clean repeat passed on both hosts. A false
healthcheck caused Apply/Verify rejection, with identical IDs across read-only
Verify. Exact owned containers, networks and target project paths were cleaned.

The QA play/parallel wait limit is now 600s; TimeoutExpired marks failed evidence
and saves captured output privately. No production readiness limit or assertion
changed. Only case 05 is rerun from e4755c45930644df85380c83c3b401ae.
Completed source a692181b93e74b2f84690ed0df5bb2ea and
fdc893c643c048ac879552240e0ebaff, including their private SSH keys, were removed
with qa-sync. Empty exact Compose networks from a2qa-cwkb9d3w and earlier
a2qa-ti8j_8ha were inspected and removed; known QA digest aliases were removed
only after confirming no containers of that image remained. Public image cache
and the unrelated application-connection-probe-qa container were preserved.

Final isolated case 05: **PASS**, 656.345s, project a2qa-5t5k3dg9,
source e4755c45930644df85380c83c3b401ae. Native parallel Apply installed different
pinned image IDs; Verify passed; combined repeat reported changed=0 and preserved
all container IDs. Thus runtime cases 01–06 are covered by completed real runs;
the earlier 360s failure remains recorded above.

Safe container identity evidence recovered from exact-project native daemon
create events after successful repeat; each placement had one create event:

| Placement | Container ID before/after clean repeat |
| --- | --- |
| cspa / node1 | 3a279bf26e2f7fe63097110eeb2858f2a93482df15ecfe6bfb6d656f17d49ad7 |
| sdku / node1 | 9dc50091166d8550011c1e1efd18a73d4f05dbb0b0cb6620aaa692b104c50d5a |
| sdku / node2 | 256b3fea7ecfcd1d77164e002099254e602ae2c33cba81317ab632241b2f1c5e |

The test itself compared complete before/after ID/config-digest/running metadata
for both hosts. Older healthcheck create events had already expired from the
daemon buffer; its ID-preservation assertion passed, without retained literal IDs.

Final A2 target cleanup audit: **PASS node1 / PASS node2**. No a2qa containers,
Compose networks or project subdirectories remain. Exact e4755c45930644df85380c83c3b401ae
source and its private QA SSH key removed through qa-sync cleanup. Audit had to
run find from `/` under the Docker account: its initial inherited working directory
was the private automation HOME and GNU find could not restore that directory.
No directory permissions or sudo policy were changed. The unrelated probe
container remains with image ID
`sha256:acd94e424cb685723e768de1e1b0a7f98ffe5b491f4666a6a89888a31bf64ebb`;
observed running=false. A2 never operated on that container; no cause inferred.
Only the active PKI rerun source ddd8af41f25a4a54a3b95638398a08e3 remains needed.

## Final standalone A2 gate

Five previously timed-out PKI cases: **5 PASS**, 2259.536s, with the test-only
600s native play limit. Certificate reissue/authority change, missing/mixed stores
and invalid PEM assertions all retained. Production PKI was unchanged. Together
with the earlier 526-case broad run (502 passed, 19 skipped, five timeout errors)
and this focused repair rerun, the regression gate is closed; this is combined
evidence, not a claim of a single final-source 526/530-case successful invocation.
The final focused 32 cases and six real runtime cases cover later A2 corrections.

Final 44-file source/fixture/test fingerprint:
`cd86be0c69d3519efc0eb5115ef63323a781b21e1e446b75493f4a58e92b44a0`.
The additional file since the 43-file review is the existing PKI QA fixture's
timeout budget; source-policy/image-binding conclusions are unchanged. Post-review
URI/QA deltas are described above; no second automatic review was requested.
Catalog/schema reproducibility and Apply/Verify syntax checks passed; git diff
--check passed. No ALT-specific behavior changed or ALT acceptance claimed.

Cleanup: ddd8af41f25a4a54a3b95638398a08e3 source removed by qa-sync after terminal
PASS. The leftover /tmp/pki-single-pass-3vt2ojde contained only local-tmp and
remote-tmp scratch from a completed timeout; exact path/UID/no active process cwd
were checked before removal. No A2 temporary roots, source copies or copied QA
keys remain. Four older pki-single-pass directories were outside the identified
A2 cleanup scope and were preserved: 4v7kg2b4, 0s94yvuj, l81xnmmb, j724k1h9.
The l81xnmmb fixture references source ef8a7c783cd94bfc9eee8857ef1095de rather
than the A2 sources above; no process cwd pointed into those roots at audit time.
Their contents were not treated as A2-owned solely from a shared filename prefix.

**Standalone A2 baseline PASS.** D01/D02 independently RESOLVED; D03/D04 remain
nonblocking limits (private Docker auth ownership/lifecycle and unsupported optional
platform.variant). Public pinned-image delivery is proved; private credential
lifecycle, release bundle/bootstrap, provider/Agent hooks, Go/UI and Installer
execution integration are outside this acceptance. No A3 authorization or commit
is implied. Existing application execution planner guard remains active.
