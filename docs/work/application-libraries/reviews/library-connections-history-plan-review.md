# Library connections/history — FULL PLAN

Independent read-only reviewer `/root/topic_roles_plan_review`, 2026-10-19.
Verdict APPROVE_WITH_CHANGES, zero BLOCKING findings. Base a5ce142c plus accepted
dirty DIRECT baseline. Reviewed plan SHA256
`8e9adfa15aaebbf3a57d02465c7762d81f881e770f473c6010dfa4579e73aefb`.

LCH-P01 NON_BLOCKING: library connections currently references application
connections; adding list support must not allow a library list. Bounded correction
added: retain full declaration map with allOf/type:object on the existing ref;
test app list/map, library map/list rejection and missing selected library key.
No repeat PLAN review needed. No other findings or overengineering mechanisms.

Standard Ansible normalization and UI direct-reference lookup respect existing
ownership. ClickHouse history keeps resource/connection/provider keys distinct;
users/grants/table behavior and installed resource ownership remain unchanged.
This is plan-only review; implementation/native/UI acceptance requires the one
FULL DIFF gate. Review grants no application/SQL/Kafka mutation permission.
