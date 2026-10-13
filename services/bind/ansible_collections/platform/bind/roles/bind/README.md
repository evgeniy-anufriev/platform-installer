# `platform.bind.bind`

Управляет authoritative BIND primary с необязательными secondary. Для standalone достаточно одного primary; role выводит project-host,
endpoint и wildcard records, валидирует complete candidates на всех участниках
и активирует их только после cluster barrier. Secondary получает зону native
transfer, не Ansible copy.

Запуск: `services/bind/playbooks/apply.yml` и `verify.yml`. В desired state
настраиваются `zone`, `defaultTtl` и
`advancedConfig.options.minimal-responses`; package/path/phase defaults — в
`defaults/main.yml`.

Тип зоны/files, transfer/update policy, recursion и notifications зарезервированы
role. Не редактируйте `/etc/named.conf`, Platform includes, zone/slave/candidate
files или generated DNS serial/fingerprint: их render/activation выполняет role.
