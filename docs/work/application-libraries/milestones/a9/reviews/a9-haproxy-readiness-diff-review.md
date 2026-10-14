# A9 HAProxy readiness ordering — independent FULL DIFF

Decision **APPROVE**; zero blockers/nonblocking findings.
Independent reviewer a9_pg_cidrs_review, 2026-10-13; separate scope from PG review.
HEAD1db6604488525eb04125630789361e4042665b99, codex/application-libraries.
Scoped diff SHA256329509AC40DF9DD9AA3B6F0B32F335DDFEB96D6E82C9B3C86BB1B0B33727E736.

Scope prepare.yml and test_partial_optimization_runtime.py only. Existing
Reset/Create/Stage tasks move after check_targets; parameters/guards/file sets
unchanged. Proven inventory capture remains first. Readiness dependencies are
resolved before check; check_targets does not read candidate directory. Successful
checks precede all candidate copy/render/validation tasks. Active graph/publication
logic untouched. Real native HTTP503 preserves prior proof; HTTP200 retries.
No additional production tasks, resolver or persistent-state framework.
RED OS runtime2/archive11 PASS supplied by implementer, not independently rerun.
Host-scope test was still running at review. Later render/validation failure
recovery remains existing behavior; not claimed covered by this scoped verdict.
