# Redis key bindings — FULL PLAN

Independent read-only reviewer `/root/topic_roles_plan_review`,2026-10-19.
Verdict **BLOCK**; unresolved BLOCKING:1, NON_BLOCKING:1. No implementation or
server commands executed by reviewer. Review validity CURRENT for plan SHA256
`0fd9e7107a7eee5d430352ad111ed6e0a5aaf36681c720333a72bc14d41fe0bc`.
Base b7d530340568907fa44dfa162c47ad2ac3bb712b plus documented preparation draft.

## RKB-P01 — BLOCKING, OPEN

Existing prepare_application_libraries.py:22–36 templates library defaults and
deployment overrides before instance.yml. Resources currently normalize inside
instance.yml. Proposed library_resources before shared ENV therefore requires
moving that early evaluation; the plan currently allows Python-boundary changes
only for validation/job classification, so it does not authorize this necessary
sequence correction.

Impact: undefined context before tasks, or stale context reuse. Duplicating merge
in Python would add the resolver explicitly excluded by the plan.

Smallest proposed owner-approved correction: remove premature shared-default
templating from the existing prepare action. Sequence: validated raw inputs ->
library identity -> standard Ansible resource merge -> fresh library_resources ->
shared defaults/overrides -> application ENV/grants. Preserve isolation from
application/previous-placement variables. Resource defaults consume only upstream
inputs, never library_resources while it is being built. No new Python executable,
resolver or store. Verify through the actual prepare action/standalone snapshot,
from clean context and repeated two-library/three-placement resolution, including
missing selections without prior-library fallback.

## RKB-P02 — NON_BLOCKING, OPEN

Existing Resources UI writes mode unconditionally; common schema permits it.
Explicitly require omission of mode for redis.key and define manual-field policy;
reviewer recommends rejecting this inapplicable field for the new kind. Verify
absence of mode, data ownership marker, key-existence check and data-creation jobs.

## Scope and disposition

No blocking overengineering findings. library_resources is an alias to existing
normalized data; reuse Resources UI/account ACL jobs. Redis data writer/CRUD,
empty-key creation, expiry/type management, lock/DTO/store are unnecessary.
Redis/Kafka aliases checked: METADATA_TOPIC is Kafka; REDIS_METADATA_TOPIC Redis.
Prototype Verify/REDIS_ISOLATION failure is not new-contract acceptance.

Automatic work stops for owner disposition. No implementation, automatic
re-review or deployment is authorized by this verdict. Proposed corrections above
are not silently incorporated into the blocked reviewed plan.
