# `platform.keepalived.keepalived`

Управляет одним unicast VRRP instance на Keepalived deployment; все declared
virtual addresses перемещаются вместе. NET-04.1 опционально отслеживает
colocated HAProxy через root-owned bounded readiness helper.

Запуск только через `services/keepalived/playbooks/apply.yml` и `verify.yml`.
Lifecycle: `prepare → Barrier A → activate → Barrier B → reconcile`; отдельный
single-host apply намеренно отсутствует.

Настраиваются `endpointGroupRef`, `virtualRouterId`, `virtualAddresses`,
per-host inventory priority и опциональный
`haproxyHealthTracking.serviceDeploymentRef`. Ссылка обязана указывать на
colocated HAProxy с тем же endpoint group. Paths и helper timing — defaults.

`state`, `nopreempt`, priorities, peers, VRID, VIPs, scripts, `track_script` и
`weight` зарезервированы. Не редактируйте active/candidate config, helper или
runtime VIPs вручную.
