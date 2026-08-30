# CORE-04 — Scoped Configuration and Variable Context

CORE-04 extends the derived `ResolvedServiceConfiguration` projection with
deployment and logical-member scopes. A member is identified by
`deploymentId + memberId`; its physical `hostId` is context and is not its
identity.

The effective chain is:

```text
ROLE_DEFAULT -> DEPLOYMENT_OVERRIDE -> MEMBER_OVERRIDE
```

Each service-package mapping may declare `scopes: [deployment, member]`.
Generic Core does not infer scopes or role-variable names. A member override
for a setting without `member` scope produces a blocking finding.

`host_vars` are deliberately outside this chain. They describe the physical
host and may be available to later Ansible execution, but they do not silently
override a logical member configuration.

CORE-04 statically resolves only literal values and exact references of the
form `{{ variable_name }}` or `{{ namespace.variable }}`. Filters, lookups,
facts, arithmetic, conditionals, concatenation, secrets and other Jinja
expressions remain `DEFERRED`. Missing exact references are `UNRESOLVED` and
cycles are `CYCLIC`.

The projection contains per-member `variableContext`, configuration values,
sources and independent configuration fingerprints. It never emits role
variable dictionaries, runtime facts, secrets or generated inventory. The
real apply boundary remains standard Ansible; CORE-04 is a deterministic
diagnostic projection, not an Ansible variable-engine clone.

Ansible variables outside the declared service mapping are preserved as
`opaqueVariables` with their original name and physical source path. They are
not rejected, dropped, assigned a semantic scope or exposed as managed
settings. Secret-like opaque values are redacted. Their editing and
classification belong to the future backend/UI milestone.
