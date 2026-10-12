# Архитектура библиотек — черновик

Контекст: консолидированное проектное предложение с уточнениями разных этапов.
Scope конкретного контракта и evidence выбирайте по [индексу](contract-index.md);
примеры будущих этапов не подтверждают реализацию или разрешение работ.

## Сущности

| Сущность | Ответственность |
| --- | --- |
| ApplicationDefinition | Пакет приложения: Compose-шаблон, role defaults, schema, files/templates, поддерживаемые подключения и secret bindings |
| LibraryDefinition | Переиспользуемый состав приложений, общие настройки, инфраструктурные слоты и ресурсы подготовки |
| LibraryDeployment | Конкретная библиотека в проекте: bindings к service deployments, overrides, явный набор Docker-хостов |
| ApplicationInstance | Именованный логический экземпляр пакета внутри библиотеки; собственные параметры, УЗ, AppRole и endpoint, размещаемый на выбранных хостах |

Например, `apigateway` — определение, `apigateway-sdku` и `apigateway-cspa` —
экземпляры. Пользователь задаёт ID экземпляра библиотеки (`sdku`, `cspa`),
а Core/Ansible автоматически вычисляет `application_instance_id` как
`<application_name>-<library_instance_id>`. Отдельного ввода ID приложения нет. Из него
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
    roles/application_apigateway/templates/agent.hcl.j2
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

Одна библиотека может явно размещаться на нескольких хостах с Docker; состав
хостов задают обычные inventory/host_vars без второго списка placement. Подготовка
общих ресурсов и provider accounts выполняется для логической библиотеки и
экземпляра, а материализация Compose, запуск и readiness — на каждом выбранном
хосте. На каждом хосте свой локальный Compose project и рабочий каталог;
Swarm/Kubernetes и автоматический scheduler для этого не нужны. `SERVER_ID`
Ansible проецирует из уже существующего ID хоста в inventory (ключа
`host_vars`, доступного как `inventory_hostname`) в локальный `.env` для
`${SERVER_ID}` в исходном Compose-манифесте. Отдельного поля ID и повторного
ввода нет. Контейнеры и пути получают host suffix,
а одинаковый published port допустим на разных хостах; конфликты проверяются
отдельно на каждом хосте. Endpoint собирает готовые targets всех размещений.
HA/failover поведения приложения и автоматического переразмещения это само по
себе не обещает.

Compose-манифест приложения остаётся переиспользуемым исходным шаблоном.
Идентичность/разрешённые настройки экземпляра материализуются Ansible;
общие подключения проецируются в библиотечный base Compose и `.env`.
Производные файлы не редактируются как второй источник desired state.
