# Архитектура библиотек — черновик

## Сущности

| Сущность | Ответственность |
| --- | --- |
| ApplicationDefinition | Пакет приложения: Compose-шаблон, role defaults, schema, files/templates, поддерживаемые подключения и secret bindings |
| LibraryDefinition | Переиспользуемый состав приложений, общие настройки, инфраструктурные слоты и ресурсы подготовки |
| LibraryDeployment | Конкретная библиотека в проекте: bindings к service deployments, overrides, placement |
| ApplicationInstance | Именованный экземпляр пакета внутри библиотеки; собственные параметры, УЗ, AppRole и endpoint |

Например, `apigateway` — определение, `apigateway-sdku` и `apigateway-cspa` —
экземпляры. Пользователь задаёт ID один раз ключом экземпляра. Из него
материализуются service key, необходимые application IDs и пути. Для глобальных
ресурсов учитываются также project/library identity и ограничения provider.
Переименование — отдельная явная операция, не незаметное изменение label.

## Хранение

Предлагается включать versioned application/library packages в переносимый проект:

```text
project/
  application-packages/apigateway/1.0.0/
    application.yml
    roles/application_apigateway/defaults/main.yml
    roles/application_apigateway/templates/apigateway.compose.yml.j2
    files/
  library-packages/sdku/1.0.0/
    library.yml
    templates/.base_compose.yml.j2
  inventory/hosts.yml
  inventory/group_vars/all/platform-installer.yml
  inventory/host_vars/node-app-1/platform-installer.yml
```

Standalone допускает обычные operator-owned group_vars/host_vars. Installer
использует существующие owned documents, не новый applications.json или БД.
`project.yml` остаётся необязательным. Пакеты входят в revision fingerprint,
перенос и экспорт; версии/digest — в расширение существующего lock механизма.
Изменение пакета обесценивает прежний план. Доверие исполняемым Ansible/Jinja
пакетам связано с digest и областью исполнения; Compose-ограничения не sandbox.

## Исполнение и ownership

- Ansible загружает defaults/group_vars/host_vars штатно. Отдельная ограниченная
  композиция связывает defaults определения, overrides рецепта и экземпляра.
  Не воспроизводить Ansible precedence или Jinja в Go/Python.
- Core работает на Execution Node: схемы, infrastructure references, DAG,
  projections, validation. Ansible применяет/проверяет через обычные роли.
- Go сохраняет существующее владение edit/session/transaction/approval/run.
- React отображает metadata/snapshot, не вычисляет Compose, endpoints или grants.
- Local Save остаётся node-free и не исполняет пользовательские роли/шаблоны.
- Desired inputs, generated workspace, observed results и runtime secrets разделены.

Первая предлагаемая граница — одно развёртывание библиотеки на одном хосте
и одном выбранном rootless Docker runtime. Multi-host/HA приложений отдельно.
Уточнение единицы Compose project остаётся открытым для нескольких экземпляров
одного исходного манифеста с одинаковыми `${...}`.

Compose-манифест приложения остаётся переиспользуемым исходным шаблоном.
Идентичность/разрешённые настройки экземпляра материализуются Ansible;
общие подключения проецируются в библиотечный base Compose и `.env`.
Производные файлы не редактируются как второй источник desired state.
