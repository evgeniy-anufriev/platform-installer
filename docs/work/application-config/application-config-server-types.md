# Application config and required server type foundation

Foundation scope and implementation steps. Current status is recorded in
[CURRENT_STATE](../../../CURRENT_STATE.md); the versioned rules are in
[the foundation contract](../../contracts/application-config-foundation.md).
Original review/audit/acceptance statements are retained in [evidence](evidence/foundation-acceptance.md).

## Owner decision

See [the dedicated document](../../contracts/application-config-foundation.md#owner-decision).

## Current contract audit

See [the dedicated document](evidence/foundation-acceptance.md#current-contract-audit).

## Planned contract

See [the dedicated document](../../contracts/application-config-foundation.md#planned-contract).

## Write and compatibility behavior

See [the dedicated document](../../contracts/application-config-foundation.md#write-and-compatibility-behavior).

## Implementation and verification

1. Add the minimal schema, repository config and strict Go loader/error model.
2. Add additive `project-edit/v1alpha3`, retain v1alpha2 unchanged, and extend
   the shared edit command, backend validation and first-save writer. The
   existing UI-01D first-save form receives only the minimal AppConfig-backed
   type selector needed to keep that already shipped flow functional with new
   v1alpha3 sessions; full server CRUD remains UI-01E.
3. Extend the existing host desired schema and snapshot projection only.
4. Expose AppConfig through the current App/Wails service and add bounded
   unknown/missing-type presentation warnings without adding UI-01E forms.
5. Add loader, command, compatibility, snapshot and no-mutation tests. Update
   contracts and durable architecture/UI documentation.
6. Run Go test/vet, affected frontend checks if generated bindings change,
   contract/schema checks, focused Core snapshot tests on RED OS when required,
   secret audit and `git diff --check`.

Acceptance results: [historical evidence](evidence/foundation-acceptance.md#implemented-acceptance-evidence).

Future template export may derive display slots such as `infra-1`, `infra-2`
and `app-1`, but a slot is never canonical host identity and import assignment
will remain explicit. No template generation or matching is implemented here.

## Non-goals and overengineering guard

No settings database, arbitrary map, remote config service, feature framework,
migration engine, template subsystem, automatic placement, service defaults,
topology/PKI rules, credentials, target addresses or Execution Node policy is
added. One YAML document, one schema, one small loader and extensions to the
existing command/snapshot paths are sufficient.
