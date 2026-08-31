# CORE-05 — Canonical Service Metadata & Variable Preservation

`service.yml` is the canonical metadata contract for managed logical settings.
Each setting explicitly declares its kind (`MANAGED` or `ADVANCED`), ordinary
role variable, type, allowed scopes, validation and optional UI metadata.
`configuration.schema.json` is a deterministic, tracked derivation of that
metadata. Role `defaults/main.yml` remains the only canonical source of
Ansible default values and expressions.

The generator never copies defaults into the configuration schema. A literal
default is checked when present; Jinja/non-literal defaults remain `DEFERRED`;
and a missing default is valid for required, runtime or computed role input.

`configurationMapping` remains a read-only compatibility form for existing
fixture manifests. A service definition cannot declare it together with
canonical `configuration.settings`.

An explicitly bound `GROUP_VARS` document can supply a managed deployment
override only when its `deploymentId`, `serviceType`, group identity and
logical relative path are supplied. Core never infers this binding from a
variable prefix. Unknown group and host variables are preserved as `OPAQUE`
with physical origin and without an inferred semantic scope.

`configurationFingerprint` contains only managed/advanced logical
configuration. `opaqueVariablesFingerprint` separately covers canonical opaque
content and context; it excludes absolute paths, YAML formatting and input
ordering. A later manifest mapping promotes an existing opaque role variable
to managed without rewriting its physical value.
