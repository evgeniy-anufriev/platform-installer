# SDKU: environment as the ordinary ENV declaration

2026-10-19. Owner requested removing `identity_environment` from packages,
keeping only independently reused/template configuration in `parameters`, and
declaring ordinary ENV in `environment`. No installation/restart requested.

## Changes

- All26 SDKU application packages have no `identity_environment` declaration.
  Former identity entries are ordinary defaults.environment expressions using
  `application_instance_id`. Existing host-specific Kafka client ID expressions
  and shared logical application/group IDs retain their values.
- `source_variables` removed.82 entries classified:20 shared configuration
  parameters retained directly under `parameters`,62 moved to `environment`.
  Five of the latter are computed SDKU consensus port ENV from effective port-2;
  their listener aliases share the same expression. HTTP port-1 aliases retained.
- Reused topics/URLs, database_name and file/template inputs remain parameters.
  Single-use values are ordinary ENV; unknown direct ENV defaults are empty,
  not usable connection endpoints. README and group_vars example explain manual
  override migration, including full frontend URLs instead of domain suffixes.
- Common library environment/base-compose and protected Vault secret bindings
  remain in their established roles. No new source of desired state or runtime
  secret persistence. SDKU import-catalog hashes refreshed.

Core/Go/UI/contracts unchanged. The existing Core conflict check applies only
to a package's declared identity list; absent lists allow ordinary ENV without
any guard removal. Legacy generic package compatibility is preserved. This
corrects the earlier conversational assumption that Core changes were necessary.
Existing Python package QA helper's fixture context updated for ordinary ENV,
flat parameters, port/placement expressions and current base-compose metadata;
no new Python script, function or runtime behavior added.

## Evidence

Native unchanged resolve_application_libraries plus builtin template/from_yaml
on trusted RED OS102,26 applications before/after,293 tasks per variant, each
failed0/changed1. The one changed task writes the synthetic JSON comparison
artifact within the temporary QA workspace; no infrastructure/app mutation.
Resolved and rendered environments match for all26 with equivalent configured
inputs. Baseline normalization accounts for legacy identity projection and the
five intentionally added SDKU consensus ENV, using their previous calculated
parameter values. Comparison reports zero differences.

Current SDKU helper:27 package schemas/digests,2 example prepare jobs,26
synthetic Compose renders,one shared base variant PASS. Real-target execution
false. Context-only helper failures (recursive synthetic full-definition data,
missing fixture database_name) corrected; native resolver source unchanged.

The first automated refactor exposed MAIN_TOPIC/MAIN_TOPIC_BASE prefix
collision in HMI. Fixed exact identifier matching, regenerated from the saved
pre-refactor packages, reran native comparison and package validation. Initial
failure preserved locally; no deployment used the intermediate result.

Real React/Wails on isolated KNP project, runtime40
`sha256:687d7e459a719222889025ede43b6ad0c3eb1501e60706d561e54c6a28256e25`:
initial Project Verify VERIFIED revision
`sha256:d8c097d1a34bca194320069db6960329281956716a998b2f5abce4b6854f26ee`.
Saved ordinary KAFKA_APPLICATION_ID_CONFIG override, verified revision
`sha256:78dcb4c765139ac813646f054b5778f640dd29838b097384cb308ed989c60efc`;
reset through the UI, saved/verified revision
`sha256:35e74324584e8037fab03c22edf25b8637b33b971a1f11eed81c204cdf40b027`.
Inherited ID restored to sdku-knp-sdku-dm. Existing project-specific account/
Sentinel bindings retained. Original project and target containers untouched.

The combined UI driver's continuation timed out because its identity test
finished on Startup instead of returning to Secrets. Identity Save/Verify/reset
evidence was preserved; a separate unchanged plan-only flow then passed:
Project Verify VERIFIED at the reset revision above, fresh plan
`plan-ea77d1fec5ce7cb6e42e3bd7` EXECUTABLE, exactly Library Apply/Verify,
skipInfrastructureVerify=true. No Approve/Start/run or Infra Verify. No UI
production fix or test bypass was needed.

Artifacts under .runtime/qa: sdku-env-native-before.log,
sdku-env-native-after.log,sdku-env-before.json,sdku-env-after.json,
sdku-env-comparison.json,sdku-env-migration.json,
sdku-env-package-validation-final.log,application-design/sdku-env-identity-ui.json.
Final plan: application-design/sdku-env-final-plan.json and
sdku-env-final-plan.log. Current-source qa-sync verification and catalog/diff
checks PASS. All four owned remote QA workspaces cleaned with qa-sync.
No visual/load/business/target execution acceptance claim.
