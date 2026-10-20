# Redis key bindings for SDKU/CSPA

2026-10-19. Owner request extends the SDKU/CSPA alarm-view-service test: use
library resource_defaults and direct resource IDs for Redis, as for database
bindings. This is a versioned Core/UI contract extension; implementation follows
one independent FULL PLAN and owner approval, then one FULL DIFF. No additional
lock, resolver/store, Python executable, key data writer or automatic migration.

## Contract

- Extend existing resource_defaults with redis.keys. Exactly the requested
  logical IDs in SDKU: dm-meta, alert-hdl, alert-class. Each has a name, e.g.
  dm-meta.name = "{{ library_instance_id }}-meta". Physical names can be changed
  through library instance resource_defaults/group_vars or an explicit selected
  resource name; reset restores inheritance. Do not special-case these IDs in
  Core/UI: they are package data.
- Add redis.key to the existing library resource selection contract. Binding
  selects a Redis deployment; parameters.name is the resolved physical key.
  Reuse package -> instance resource_defaults -> selected parameters precedence.
  Defaults alone do not select resources. These are references to names, not a
  request to create application data or empty Redis structures. No SET/HSET,
  DEL, FLUSH, expiry/type change or key data ownership claim.
- Expose the already normalized selected resource map as library_resources for
  library/application templates, before shared library defaults ENV is expanded.
  No duplicate resolver or persistent map. Shared ENV uses direct resource IDs,
  e.g. library_resources['dm-meta'].parameters.name. Own application grants.keys
  and grants.channels use the same IDs/names. Account/provider and privilege
  ownership remain unchanged; no automatic grant widening.
- Shared library ENV holds REDIS_METADATA_TOPIC, TN_SCADA_METADATA_TOPIC,
  ALERT_HANDLER_TOPIC and ALERT_CLASS_TOPIC. The actual bindings
  are three Redis keys; TOPIC suffix does not make them Kafka resources.
  Application packages remove duplicate physical Redis names/ENV declarations.
  METADATA_TOPIC is not a Redis alias: the inspected alarm-view JAR maps it to
  tn-scada.kafka.topic.metadata-topic; preserve that separate Kafka setting.
- Redis key references produce no provider resource-creation jobs. Existing
  account Apply/Verify manages the ACLs; application's real data producer creates
  data. Plan/snapshot expose resolved names; never claim an empty Redis key was
  created by a plan.
- Reuse Resources UI: Redis key kind, matching Redis provider, add from defaults,
  name override/clear/reset and fresh Core name preview. Do not expose irrelevant
  DB schema/owner or Kafka partitions/RF settings. Hide managed/existing lifecycle
  controls for this name reference; UI omits mode and Core rejects manually set
  mode for redis.key as inapplicable. Do not invent another mode. Go transports and
  saves the contract only; UI performs no precedence/provider/topology resolution.

## Minimal implementation and checks

Read canonical schemas/configuration contract and the current resource tasks and
provider job builder. Extend existing schemas, native Ansible resource-default
merge/public variable timing and existing UI component. Owner approved RKB-P01/
RKB-P02 correction2026-10-19: remove premature shared-default templating from the
existing prepare action; no replacement resolver in Python. Sequence: validated
raw inputs -> library identity -> standard Ansible resource merge -> fresh
library_resources -> isolated shared defaults/overrides -> application ENV/grants.
Keep shared defaults isolated from application variables and prior placements.
Resource defaults consume upstream inputs only, never the library_resources map
being constructed. Existing Python boundary changes are limited to this removal
and unavoidable validation/job classification; no new script.
Document namespace variables and absence of Redis key data lifecycle.

Implementation clarification within the same order/isolation boundary: reuse
the existing prepare action's isolated templar only when Ansible requests an
upstream resource-default render or a late shared-default render. Its former
eager job loop is removed; all precedence/selection merges remain native tasks.
Built-in file/from_yaml lookup was checked on the synthetic fixture: unsafe
lookup output preserves unexpanded name expressions, while allowing eager lookup
expansion evaluates the whole file before resources exist. The existing raw host
context and sanitized templar are retained rather than adding a new Python script,
resolver or unsafe JSON/template workaround. This bounded reuse preserves the
owner-approved sequence and is included in the upcoming FULL DIFF scope.

Current-tree RED OS tests: two libraries/three placements, distinct names,
same-provider binding validation, shared ENV/ACL agreement, package/instance/
resource precedence and reset, missing selections, no Kafka/SQL/Redis key-data
jobs for redis.key, legacy Kafka/DB compatibility and secret-safe projection.
Check that shared defaults resolve within each library identity, without context
leaking from the last application/library; prior direct-ENV prototype failed its
pre-plan REDIS_ISOLATION guard and is not acceptance evidence.

UI tests plus real React/Wails: three Redis defaults selections, override/reset,
Save/reopen/Verify and fresh library-only plan on matching verified/published
runtime. Original owner-authorized deployment remains pending: same application
package in SDKU/CSPA, library differences limited to name/resource_defaults;
instance overrides only collision/memory requirements. Show final project path,
folder composition and resolved resource names again before plan execution.
Then use real fresh Plan/Approve/Start with skip_verify, and create users/grants,
Kafka topics and databases only through that plan. Observe all six containers on
101/102/103, their own endpoints/accounts and distinct configured Redis names,
distinct DBs and Kafka topics. Retain diagnostic logs; report absent application
data honestly and use only explicitly owned temporary probe keys if necessary.

Scope correction after owner's question2026-10-20: the three reference names do not imply a new ACL
restriction. Preserve the selected application's original keys/channels policy;
the implementer's test-only three-name ACL and isolated username suffix are
removed. No Core security policy or manual account changes are introduced.

## Current boundary

No application deployment plan was built/approved/started for this test. Runtime44
was prepared. KNP containers were stopped on all three hosts to free RAM; images,
volumes and logs retained. SDKU/CSPA project copy remains under
.runtime/qa/sdku-cspa-alarm-view-project. Current shared ENV source/config edits
are a preparation draft, not acceptance of the new binding contract.
