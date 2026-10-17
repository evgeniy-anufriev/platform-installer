# SDKU corrections — TARGETED_RECHECK D02/D03

2026-10-17. Independent reviewer: `/root/library_common_plan_review`.
Verdict: **APPROVE; zero unresolved BLOCKING findings**.
Base HEAD: `4aab08d865d0754831c93c70b50cb417c8128afb`.
Manifest: `.runtime/sdku-corrections-targeted-review-scope.json`, SHA-256
`33314425319330a96552675eb9998775351d93adb5845a186c4034a2594e5ab2`.
All 104 fingerprints checked independently, zero drift. This is the single
owner-authorized targeted recheck; no further FULL review was performed.

## D02 — RESOLVED

Standard assert/loop in `application_runtime/tasks/resolve_paths.yml` rejects equal
or nested absolute roots of different libraries against earlier host-local
preflight rows, before provider/materialization. Same-library placements pass.
Native test covers HOME/absolute equality, nesting in both orders, siblings,
same-library reuse and traversal. No new lock/path manager/Python helper.

## D03 — RESOLVED

Reviewer directly inspected the real React/Wails evidence at
`.runtime/qa/application-design/sdku-corrections-plan-asserted.json`.
Both plans are EXECUTABLE/PLAN_REVIEW for one saved revision:

- false: `plan-175cd94bfff8339c989b47e8`, SERVICE_VERIFY then application pair;
- true: `plan-907024a7bff353ef8f299c0b`, application pair only.

Fingerprints differ. Both retain actual BLOCKED/INFRA_VERIFY_STALE and null
evidenceRevision. No Approve/Start. Runtime digest:
`sha256:9df8b8d7facba2c767023dfc155a52227124d745014d8392050ebe3d0e3fb735`.
Retained runtime07 rejects the new protocol. The immediate UI toggle correction
requires fresh Build in both directions, preserving existing mode-only behavior.
QA seam uses chooser substitution and observation of actual bindings, no production
bypass. Code, evidence and fingerprints were inspected; tests were reported by
the implementer, not independently rerun.

## Disposition and limits

No unjustified mechanisms found. Existing bindings/protocol/lifecycle and standard
Ansible tasks suffice. Other FULL review conclusions remain; P01 stays SUPERSEDED
by the owner's sequential-execution decision. No additional lock is required.
CURRENT for the manifest above. Final-source full Core-suite and visual PASS are
not claimed. This is plan-boundary acceptance, not application installation
acceptance, and authorizes no application Start or installation.
