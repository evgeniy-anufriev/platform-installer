# Клиенты Keycloak для SDKU

Шаблоны подготовлены 2026-11-07 из `dump/keycloak_14-10-2026` архива
`C:\Users\AnufrievEV\Codex\SZI_Update\dump.7z`.
SHA-256 исходного файла:
`b12bfe70d45fc5605e4f1e2bc4e683dc9deaf14a8c48a0408fdeb8c177d3ced4`.
Совпадение проверено с файлом, извлечённым непосредственно из этого архива.

Для каждого приложения файл находится в
`application-packages/<application>/1.0.0/assets/keycloak-client.json.j2`
и включён в `files` его манифеста. Контрольные суммы пакетов обновлены в
`import-catalog.json`. Существовавшие шаблоны `data-manager`, `hmi-backend`
и `hmi-frontend-para` заменены настройками соответствующих клиентов дампа;
их прежние дополнительные роли и политики не смешиваются с исходными.

| Приложение | Клиент дампа | Роли | Ресурсы | Политики |
| --- | --- | ---: | ---: | ---: |
| alarm-service | alarm-service | 4 | 1 | 2 |
| alarm-view-service | alarm-view-service | 8 | 6 | 12 |
| data-manager | data-manager | 9 | 7 | 14 |
| ef-backend | hmi-backend | 3 | 1 | 2 |
| evo-scheduler | evo-scheduler | 4 | 2 | 4 |
| hmi-backend | cspa_hmi_backend | 6 | 5 | 10 |
| hmi-frontend-alarms | hmi-frontend-alarms | 3 | 0 | 0 |
| hmi-frontend-para | hmi-frontend-para | 2 | 0 | 0 |
| hmi-frontend-svg-editor | hmi-frontend-svg-editor | 2 | 0 | 0 |
| hmi-frontend-trends | hmi-frontend-trends | 2 | 0 | 0 |
| hmi-frontend-viewer | hmi-frontend-viewer | 2 | 0 | 0 |
| sdku-knp | sdku-knp-backend | 2 | 1 | 2 |
| sdku-knp-ui | sdku-knp-ui | 2 | 1 | 2 |
| sdku-vtor | sdku-vtor | 4 | 3 | 6 |
| sdku-vtor-ui | sdku-vtor-ui | 2 | 1 | 6 |
| user-preferences | user-preferences | 2 | 1 | 2 |

Соответствия `hmi-backend` → `ef-backend`, `cspa_hmi_backend` → `hmi-backend`
и `sdku-knp-backend` → `sdku-knp` согласованы владельцем.
Имя первого клиента в исходной БД записано через дефис: `hmi-backend`.
Для остальных приложений использовано точное совпадение имени клиента.
В дампе нет одноимённых клиентов для `evo-manager`, `ham-backend`,
`hmi-frontend-viewer-noszi`, `iec60870`, `kafka-ch-replicator`,
`kafka-history-writer`, `opc-ua-server`, `sdku-status-calculation`,
`sdku-tank-farm`, `sdku-telemechanics`; шаблоны для них не создавались.

## Переносимые значения

`clientId`, `name` и ссылки политик на собственные роли используют
`application_instance_id`. Исторический адрес nginx заменён на
`application_connections.sso.parameters.proxy_url`; пути приложения используют
тот же ID экземпляра. Сохранены callback-пути фронтендов, включая
`/oidc-callback`, и настройки logout. У `alarm-service` пустой root URL и
относительный redirect `/*` привязаны к прокси и пути экземпляра приложения.
`webOrigins` содержит origin прокси без исторического пути приложения.

Флаги клиента, protocol mappers, default/optional client scopes, роли,
ресурсы, политики, режим enforcement и стратегии решений перенесены из дампа.
Связи ресурсов, политик и ролей используют имена вместо UUID исходной БД.
Секреты клиентов, registration tokens и время создания старого секрета
в шаблоны не включены. Runtime-секреты передаются существующим механизмом SSO.

## Использование

Эта поставка добавляет файлы клиентов. Настройки `connections`, флаги включения
SSO и provisioning hooks приложений не менялись. Уже существующие lookup у
`data-manager`, `hmi-backend`, `hmi-frontend-para` используют обновлённые файлы,
если для экземпляра включено подключение `sso`.

Для подключения файла в `defaults.parameters` другого приложения применяется
тот же lookup, что у `hmi-backend`:

```yaml
IDENTITY_CLIENT: "{{ (lookup('ansible.builtin.template', (application_job.application.defaultsPath | dirname) ~ '/../../../assets/keycloak-client.json.j2', convert_data=false) | from_json) if 'sso' in application_connections else {} }}"
```

Само наличие файла в пакете не включает SSO и не создаёт клиента. Для этого
приложение должно потреблять подключение `sso` и передавать `IDENTITY_CLIENT`
штатному провайдеру. Существующие правила подключения СЗИ описаны в [README](README.md).

## Проверка на RED OS

На `192.168.56.101` без запуска контейнеров проверены:

- штатная загрузка схем и digest всех 28 пакетов SDKU/CSPA;
- штатная подготовка обоих примеров, по 2 задания, и 26 синтетических Compose render;
- 32 рендера 16 клиентских шаблонов средствами Ansible с двумя разными ID
  экземпляра и адресами прокси;
- соответствие исходной БД: 57 ролей, 29 ресурсов, 62 политики, состав scopes
  и protocol mappers, ссылки политик на роли, ресурсы и другие политики;
- отсутствие секретов исходных клиентов, исторического адреса и UUID БД в
  сформированных шаблонах.

Результат PASS. Восстановление БД, импорт клиентов в работающий Keycloak,
проверка входа и фактическая установка приложений не выполнялись.
