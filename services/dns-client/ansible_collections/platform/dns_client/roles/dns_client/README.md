# `platform.dns_client.dns_client`

Настраивает split DNS из одной ссылки на BIND deployment. При наличии unit
выбирается systemd-resolved; иначе NetworkManager используется только с
поддерживаемым per-domain adapter.

Запуск: `apply.yml`, `verify.yml` и controller-only `projection.yml`. В desired
state настраиваются `dnsServerRef` и placement. `platform_dns_client_phase` —
lifecycle control, а не параметр обычного operator apply.

Адреса серверов и route domains — derived runtime projection. Не заменяйте
`/etc/resolv.conf`, Platform resolved drop-in или NetworkManager fragments:
role безопасно прекращает работу, если не может владеть split-DNS adapter.
