# Группы и назначения ролей

Списки находятся в `platform_library_definition.defaults.parameters.IDENTITY_GROUPS`
СЗИ и СДКУ. Каждый элемент содержит имя группы и `roles_file`: обычный Ansible
`lookup('ansible.builtin.template', ...) | from_json`, указывающий на конкретный
файл пакета. Результат lookup — объект назначений; путь не передаётся целевой
машине. Файл включается в `files` манифеста библиотеки. Пакетный API-скрипт выполняется
на Execution Node через curl/jq; дополнительных контейнеров для интеграции нет.

Пример файла:

```json
{
  "realm_roles": ["reader"],
  "client_roles": {
    "alarm-view-service-sdku": ["Администратор", "viewCurrentDataMT"]
  }
}
```

Ключи `client_roles` — clientId, совпадающие с applicationId. JSON может быть
шаблоном `.json.j2`; используется существующий контекст Ansible пакета.
Переопределение `overrides.parameters.IDENTITY_GROUPS` в group_vars заменяет
список целиком. Пустой список отключает создание/назначение, сохраняя ранее
созданные объекты и связи. UI для этого функционала не добавляется.

Вызовы имеют один обычный `provider_prepare` phase и явный `order`:

1. `-100`: создать группы.
2. `0` (по умолчанию): создать клиентов приложений.
3. `100`: создать недостающие роли и назначить их группам.
4. Стандартная пакетная обработка accounts провайдера.

Скрипт проверяет назначения чтением API. Повторный Apply не добавляет уже
существующие роли и связи. Он не удаляет роли/назначения и не меняет определения
существующих ролей, включая composites. Отсутствующий клиент — ошибка; новый
client role создаётся у найденного клиента.

Исходные дампы `keycloak_13-10-2026` и `keycloak_14-10-2026` содержат прямые
client-role mappings групп, без прямых realm-role mappings. У ТУЗ назначений
нет. Файл СДКУ переносит три назначения клиента alarm-view-service для текущего
интегрируемого приложения: `Администратор`, `viewCurrentDataMT`, `uma_protection`.
Другие исторические клиенты и права управления `master-realm` автоматически не
переносятся. Их добавляют в файлы соответствующих интегрируемых приложений по
мере включения этих приложений. Это не полный перенос старой модели доступа.

## Прямые назначения пользователю

Управляемый account использует тот же формат файла через
`defaults.accounts.sso.parameters.roles_file`. В defaults приложения
указывается обычный lookup файла пакета с `from_json`. Членство в группах
остаётся отдельно в `parameters.groups`. Существующее `parameters.roles`
совместимо с этим форматом и добавляется к realm_roles.

Файлы `assets/account-roles/admin-grant-access.json` и
`assets/account-roles/admin-grant-access-audit.json` в соответствующих пакетах
переносят прямые назначения этих пользователей из исходного дампа от 14 октября.
В обоих дампах они состоят в ТУЗ; отдельно им назначены realm roles admin и
default-roles-master и client roles клиентов grant-access, grant-access-audit,
master-realm, account и broker. В defaults исправлены имена пользователей на
admin-grant-access и admin-grant-access-audit. Runtime password refs сохранены.

Назначения выполняются пакетным account-скриптом для mode=managed после создания
пользователя. Связи добавляются и проверяются чтением прямых role mappings API,
без удаления существующих связей. mode=existing не меняет роли или членство.
В Vault/Agent по-прежнему доставляются стандартные username/password account;
файлы ролей не являются секретами. Новых account-полей в Core или UI нет:
roles_file — произвольный параметр существующего accounts.parameters.
