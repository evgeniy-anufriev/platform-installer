# PKI single-pass: FULL PLAN review

Date: 2026-09-29. Independent role: architecture-reviewer.
Base HEAD: `f261eff44820aeff93b93d1db5aec0d8f99e41a6`.
Reviewed plan: [pki-single-pass.md](../pki-single-pass.md).
Reviewed plan SHA-256:
`9e7c689b594383eb7d86ce4697eb47c38861312354d2e2714a3f98eb3aa67bbf`.

Initial FULL PLAN verdict: **BLOCK** (historical). Owner accepted the bounded
integrity correction and authorized implementation. The targeted disposition
below supersedes this finding's OPEN state, not the historical review.

## PKI-SP-PLAN-01 — target-material integrity before activation

The plan promises rejection of corrupt/unreadable target material before
service activation, but the existing five consumer paths do not establish
complete integrity. Existence checks, copying and PEM assembly do not prove
the integrity of private keys and PKCS12 stores. Existing pki_verify is also
insufficient for that complete guarantee.

Required bounded correction: specify a read-only pre-activation integrity
check covering the actual target files consumed by the optimized path,
including keys and stores, or retain/fall back to full deployment where this
proof is absent. Reuse Core tasks and standard tools, with sensitive checks
under no_log. Prove corruption/unreadability behavior with real Ansible.

Reviewer found the remaining resolution/dispatch design coherent:
per-process resolution is retained; fresh resolver output is compared to
frozen manifest plans without trusting shadowed set_fact variables; skip
state is current-dispatch-only; standalone defaults remain complete.
Real Ansible tests remain required for dynamic tags and process separation.

Overengineering findings: no unnecessary abstraction, duplicate DTO or
persistence layer in the plan. Do not introduce a generic verifier framework
to address this finding.

No tests or target contact were performed by the reviewer. Prior Core tests
and run timings are context only. The previous PKI-SP-01 whole-import-skip
DIFF verdict remains BLOCK; that implementation was reverted, not accepted.

## Owner-authorized targeted recheck — 2026-09-29

Verdict: **APPROVE**; `PKI-SP-PLAN-01` **RESOLVED**, zero blocking findings.
The same independent reviewer inspected the integrity/resolution/tag/dispatch
boundary; no second FULL review or extra recheck cycle was run.
Scoped production fingerprint:
`69c9807eca36787117249330eaafb4b789c3d8331eed2ee7e9f7c0bf1cfdbf6c`.
Corrected plan SHA-256 at review:
`2c86ca404da460e815cfe15b3bd1c53c7b2ef878e9b864c24a17c7df1af9ed3e`.

The guard checks trusted source and deployed bytes, types, permissions and
the fingerprint marker. Mismatch uses existing deploy tasks; unavailable
source blocks before activation. No new DTO, persistence or verifier framework.

Parent-supplied RED OS evidence: four controller/integrity tests PASS in
194.912s; eight separate-process resolution/consumer tests PASS in 73.150s,
both with zero skips. Consumer tests use production copy/assemble tasks and
activation expressions with harmless observations, not daemon restarts.
Go test/vet, catalog/schema reproducibility and five service apply syntax
checks PASS. Reviewer independently inspected source/file identities but did
not run tests or contact targets. Full Core and SI08-F remain separate gates.
