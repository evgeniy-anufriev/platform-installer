# Apply performance P2 — implementation and QA journal

2026-10-15. Owner authorized implementation and QA; no new probe concurrency or
infrastructure Apply. Base B4 `3fcf54c83ec13dcb2fda035862a5305c843a1095`.
Branch `codex/application-libraries-apply-performance`.

## Final verdict

P2 functional/nonvisual acceptance PASS on final bundle04. No infrastructure Apply,
new probe concurrency was performed. Owner subsequently authorized commit and master synchronization; publication identity is recorded in Git history. Visual
inspection and real30-container timing are not claimed. Cleanup has one explicit
local exception: automatic approval rejected deletion of old local QA bundle02/03
copies as blocked by policy; these copies remain. Remote temporary workspaces and
diagnostic credential copies were removed; installed runtime/infrastructure remain.

Final bundle digest:
`sha256:b00ded903bffaf188638cbf2c4f13fb91a6a886d74bd2ca582ac32e65629b165`.
Saved revision:
`sha256:6791602a10169e43ff9ff3eec3bc8e078404fe3d7f84a8add8eaefddddda39f1`.

| Evidence | Result |
| --- | --- |
| Real React/Wails final prefix run `installer-c9ff800da69a78e8c762f479c3993d92` | SUCCEEDED seq5759; ten SERVICE_VERIFY then library Apply/Verify; zero SERVICE_APPLY |
| Real React/Wails saved-proof repeat `installer-ea019afddbcb1714daadc4037e189193` | SUCCEEDED seq2039; authoritative infra Verify PASS for ten deployments from c9ff; exact two library operations, no infrastructure operations |
| First final04 Apply / Verify | 642s (10:42) / 203s (3:23) |
| Saved-proof final04 Apply / Verify | 575s (9:35) / 190s (3:10) |
| Both unchanged runs | changed=0; three HAProxy reload tasks SKIPPED and one zone update SKIPPED per Apply |
| Container metadata, both before/after pairs | All three IDs, StartedAt, image, Running and ownership labels IDENTICAL |
| Provider metadata, both before/after pairs | Entire parsed JSON IDENTICAL: ten KV versions, PostgreSQL discovery/OIDs/ACL/memberships, ClickHouse identities/DBs/grants, live HAProxy/BIND hashes/mtime and service/reload metadata |
| Health after each final04 run | Three direct and two CA/hostname-verified HTTPS status200; overall ok and all exact eight checks ok |
| Final SSH cleanup | Zero own control directories/sockets; actual 30 readonly connections / ten sequential cleanup cycles PASS |
| Hygiene | 16 known runtime values, 230 files, zero matches; values never printed |
| Remote cleanup | Four node2 QA workspaces and one node1 QA workspace absent; two diagnostic credential copies deleted; current runtime04 manifest rechecked |

| Stage | B4 baseline | Final04 prefix Apply | Final04 saved-proof Apply |
| --- | ---: | ---: | ---: |
| Apply | 28:47 | 10:42 | 9:35 |
| Preflight | 7:19 | 2:13 | 1:54 |
| Shared provider preparation/resources | — | 1:48 | 1:32 |
| Instance accounts | — | 1:03 | 1:07 |
| Instance runtime | — | 2:23 | 2:14 |
| Endpoints including original sequential probes | 9:18 | 3:15 | 2:48 |
| Verify | 7:57 | 3:23 | 3:10 |

Measured Apply reduction is 62.8–66.7%, about 2.69–3.00x faster on this same
two-library/three-placement topology. Endpoint <=3min is met by the repeat but not
the first final04 run (3:15); the plan's target remains an orientation, not an SLA.
Preflight includes placement checks; these are stage timings, not isolated per-
container costs. No claim of constant probe time or real30-container throughput.

Safe detailed files are under `.runtime/qa/apply-performance/evidence/`:
`performance-summary.json`, final run safe events, target prefix/repeat evidence,
both container/provider before/after pairs, health probes, native cleanup proof,
test logs, bundle validation/publication and hygiene summary. Final broad Core
675PASS/21standardSKIP preceded the bounded transport corrections; affected final
execution188PASS/4standardSKIP and seven SSH cases plus native/live final acceptance
cover those corrections. No second final full-Core run is claimed. Independent
FULL and owner-approved targeted D01 review reports remain exact historical
identities; subsequent path-bound/cleanup fixes preserve the approved architecture
and have the separate tests/live evidence described here.

## Current implementation

- Standard Core pipelining; operation-private OpenSSH ControlMaster/ControlPersist60s.
  Short controller-owned0700 control directories; exact socket guards and bounded
  close; cleanup reused by confirmed-stop runtime credential cleanup/recovery.
- Existing per-source resolution retained to preserve per-source probe policy;
  one union publication through current partial HAProxy lifecycle, host filtering
  after common source-set resolution; singular compatibility and empty-scope guards.
- BIND production validation/normalization/verification tasks reused for singleton
  and zone batches; local nsupdate TCP with existence/RDATA prerequisites and
  conservative pre-mutation message bound. No new zone-file/reload path.
- Network probes remain the existing sequential tasks, not a new runner.

## Historical QA checkpoints

Current sources transferred by qa-sync to RED OS node2. Execution/trust/lease
suite190run/186PASS/4existingSKIP. Integrations14PASS; BIND25PASS including new
native zone-request guards/30owner rendering. HAProxy30PASS under root, required
for disposable production copy/archive ownership tests; initial nonroot invocation
had3failures (fixture normalization and required root ownership), retained in log.
Fixture extraction now includes the production partial-scope normalization rather
than bypassing it. New plural cross-provider host-preservation case and real isolated
BIND multi-owner/prerequisite test added, pending final affected rerun.
At this historical checkpoint full Core was RUNNING; no terminal PASS was claimed. Independent DIFF review
and new immutable bundle/actual target acceptance were pending; see final verdict above.

## Baseline and acceptance

B4 baseline run9ba624: Apply28m47s, preflight7m19s, endpoint9m18s, Verify7m57s.
Compare action wall time, not whole Verify-prefix run, against a new real React/Wails
run from the same desired library topology. Record exact bundle/revision/run IDs,
candidate/reload/update counts, complete probes and unchanged container/provider
metadata. No optimized result or final cleanup/hygiene PASS claimed before measured QA.

## Historical independent review stop

FULL DIFF BLOCK, AP-P2-D01: main.yml singular assertion rejects plural-only production
scope despite successful partial_scope normalization. Exact43file identity and
minimal fix/native test requirements are in the independent review report. No
production fix/recheck performed at that checkpoint; owner decision was pending. No bundle publication,
activation, target Apply or optimized timing claimed.

Final affected HAProxy31rootPASS; actual isolated BIND multi-owner/prerequisite1PASS;
Core endpoint-focused4PASS after test fixture includes production normalization.
The broader Core run session80688 was already active before BLOCK, and its first
fixture-extraction failure remains historical; no full-regression PASS claimed.
Trusted node2 built perf-bundle01 from current source and approved existing08 runtime
inputs without downloads. It remains unpublished pending review resolution.

Owner authorized D01 correction and one targeted recheck. Duplicate main assertion removed; native production-normalization/main guard4PASS19.730s. TARGETED_RECHECK APPROVE/D01RESOLVED/0blockers; report retained. First broadCore696run3failures/21skips1853.435s: one pre-correction fixture extraction, two Vault collection-lookup QA environment omissions (singular collection path overrode test plural env). Production behavior not weakened; final full rerun uses all service collections. Final bundle02 bf836a4674402d520052d43c30ac8564fd9249c3e3ae16ea90369284d21f615e built from trusted source/approved08 bytes, standard validate/publish PASS; original08 preserved locally. Real React/Wails PREPARED/READY and exactProjectVERIFIED7e72f5528b3a6893cc6cef1f596399a395abc49043a8ea50d2a8f7509ae949d6. Before-target3containers and safe provider metadata saved (10KVversions,2CHusers/2DBs/grants,PGprimarydiscovery/OIDs/ACL,liveHAPBINDhashmtime/servicecounter). No target outcome claimed yet.

First real prefix installer-d90de7629e8efa8809c037be538edc08 FAILEDseq44 at BIND Verify/SSH before any library action. Read-only native diagnostic proves current socket expanded97bytes fails unix_listener/pathTooLong; identical trusted identity/host with61byte path succeeds. OpenSSH temporary atomic-rename suffix17bytes was missing from bound. Bounded correction: compact operation namespace (run20hex+operation12hex) under private UID root, same128bitcombined hash space; bound reserves suffix, no auth/trust/lease/cleanup policy change. Five focusedSSHtestsPASS; actual fixed nativeSSH/cleanup outcome saved. Historical failure retained; no failed run retroPASS. This is an implementation path-length correction within approved custody architecture, not a new review cycle or credential mechanism.

Final broad Core696:675PASS/21standardSKIP/0fail/errors1803.937s (started before final compact ControlPath correction); affected final execution190:186PASS/4standardSKIP11.584s plus actual fixed SSH/cleanupPASS. Owner authorized obsolete QA cleanup: inactive B4QA04 runtime release e7691c8a…5903b manifest exactly matches preserved local copy; removed only that release after current-symlink guard. Current02 runtime and all infrastructure/journals retained; available node1 space4182884KiB. Real React Prepare03 retry in progress.

Bundle03 real PrepareREADY/ProjectVERIFIED revision6debf555984272c9588a80e03121e8061d4aea6831bf376ef0bcd8efbf62b261. Actual React Cancel installer-e467a7fc5c9ae071f6661e3b02db906e terminalCANCELLED after readonly DNS prefix task;271safeevents,0libraryactions,0infraApply. Unitinactive and /tmp/p0 empty after confirmedstop. New normal actual React runinstaller-261d1ed25d0e0e92864738f98583115a started fixed10SERVICE_VERIFY+libraryApply/Verify, noSERVICE_APPLY. Preliminary hygiene16values185files0matches; final audit pending.

First bundle03 runinstaller-261d1ed25d0e0e92864738f98583115a SUCCEEDEDseq5759. All10infraVerify and libraryApply/VerifySUCCESS; SERVICE_APPLY0. Apply16:28:09Z–16:37:56Z587s(9:47), Verify188s(3:08). Full prefix before/after parsed metadata+3containers IDENTICAL (object key presentation order excluded); liveHAPBINDhashmtime/servicecounters,10KVversions,PGOIDsACL/CHidentitiesgrants stable. All3direct/twoCAhostnameverifiedHTTPS200/overallok/exact8checksok. Actual React fresh samebundle03plan authoritatively savedinfraVerifyPASS10deployments and exact2appops; repeatinstaller-4a3436e9e1e2f3617dc42afe09ea0ab6 STARTED16:47:19Z, noinfraoperations.

Saved-proof repeatinstaller-4a3436e9e1e2f3617dc42afe09ea0ab6 INTERRUPTEDseq1588, notPASS. All endpoint tasks completed; controller stderr safely classified Errno39 DirectoryNotEmpty under /tmp/p0. OpenSSH exit acknowledgement precedes socketunlink. Bounded architecture-preserving correction waits at most3s for confirmed unlink after successful -Oexit; never unlinks live socket; expiry/list inspection handles disappearing socket. Regression7PASS incl delayedunlink and boundedlivefailure; actual30readonlySSH/10sequentialcleanupcyclesPASS with0ownedremainingdirectories. Finalaffected192run188PASS/4standardSKIP25.865s. Freshsources qa-sync node2e17987aaedb842af8cb413d967dadffd; bundle04 build uses existing approvedruntimeinputs, no downloads. Node2space initialbuildFAILED28; only locallypreservedverified oldQA02/03 buildcopies removed thenbuildPASS. Node1noncurrentownedPerf02release removedaftermanifest/currentguard, current03/infrastructure retained. No new security/lifecycle architecture/review cycle; final real acceptance pending.

Bundle04 b00ded903bffaf188638cbf2c4f13fb91a6a886d74bd2ca582ac32e65629b165 standardvalidate/publishPASS; actual React READY/ProjectVERIFIED revision6791602a10169e43ff9ff3eec3bc8e078404fe3d7f84a8add8eaefddddda39f1. Finalprefixruninstaller-c9ff800da69a78e8c762f479c3993d92 STARTED17:17:04Z, exact10SERVICE_VERIFY+librarypair, noSERVICE_APPLY. Newbeforeprefixmetadata saved; final PASS/timing remains pending.

Final04 prefixinstaller-c9ff800da69a78e8c762f479c3993d92 SUCCEEDEDseq5759. Apply17:34:24Z–17:45:06Z642s(10:42), Verify203s(3:23), changed0; all3HAPreloadtasksSKIPPED/DNSupdatesSKIPPED. All5status200/exact8checksok/CAhostnameverified; parsed3containermetadata+entireprovidersnapshotIDENTICAL. Final04 actualReact freshplan savedinfraPASS10 exact2libraryops; repeatinstaller-ea019afddbcb1714daadc4037e189193 STARTED17:52:44Z. Finalrepeat/hygiene/cleanup stillpending.
