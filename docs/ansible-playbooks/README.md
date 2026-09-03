# Ansible playbooks

Общая точка входа оператора. Желаемое состояние задаётся обычным inventory:
`inventory/hosts.yml`, `inventory/group_vars/all/platform.yml` и при
необходимости `host_vars/`. `project.yml` — совместимые метаданные и lock
каталога, но не замена inventory.

## Запуск

Работайте из корня репозитория и подключайте только нужные collections. Пароли,
закрытые ключи и значения секретов нельзя передавать через inventory или `-e`.
Для них используются только runtime-only файлы и ссылки.

```bash
export ANSIBLE_COLLECTIONS_PATH="$PWD/ansible-core/collections:$PWD/services/<service>/ansible_collections"
ansible-playbook -i examples/valid/<fixture>/inventory/hosts.yml <playbook> \
  -e @examples/valid/<fixture>/inventory/group_vars/all/platform.yml
```

Перед apply запускайте `ansible-core/playbooks/validate.yml`: он работает только
на controller и не подключается к targets.

## Синхронизация исходников для QA на RED OS

Для запуска Core-тестов на RED OS используйте стандартный helper из корня
репозитория:

```powershell
$qaWorkspace = .\scripts\qa-sync.ps1 `
  -TargetHost <qa-host> `
  -TargetUser <qa-user> `
  -KeyPath .\.runtime\<qa-key>
```

Helper применяет только `scp -r`, создаёт уникальный workspace под
`/var/tmp`, передаёт каталоги `ansible-core`, `services`, `examples` и
`contracts`, затем проверяет их наличие и обязательный catalog generator.
Полученный путь используйте как корень QA-запуска. После завершения удалите
только этот workspace:

```powershell
.\scripts\qa-sync.ps1 `
  -Cleanup `
  -CleanupHost <qa-host> `
  -CleanupUser <qa-user> `
  -CleanupKeyPath .\.runtime\<qa-key> `
  -RemoteWorkspace $qaWorkspace
```

При необходимости отдельно проверьте уже переданный workspace:

```powershell
.\scripts\qa-sync-smoke.ps1 `
  -TargetHost <qa-host> `
  -TargetUser <qa-user> `
  -KeyPath .\.runtime\<qa-key> `
  -RemoteWorkspace $qaWorkspace
```

Не используйте tar-потоки или архивные конвейеры. Ошибка передачи — это сбой
QA-инфраструктуры, а не дефект продукта. Синхронизация не затрагивает
постоянные execution, PKI, generated или service state каталоги.

## Core playbooks

| Playbook | Назначение |
| --- | --- |
| `validate.yml` | Read-only валидация desired state, catalog и topology. |
| `prepare-execution-node.yml` | Подготовка выбранного Execution Node. |
| `bootstrap-targets.yml` | Bootstrap технического пользователя и ключа на target. |
| `target-connectivity.yml` | Read-only проверка подключения и elevation. |
| `ensure-execution-access.yml` | Последовательно запускает три предыдущие prerequisite-проверки. |
| `pki-apply.yml` | Материализует PKI на controller и развёртывает material на targets. |
| `pki-verify.yml` | Read-only восстанавливает derived PKI plan и проверяет material. |
| `pki-reissue.yml` | Явный reissue только перечисленных request IDs. |

## Service playbooks

| Сервис | Apply | Verify | Примечание |
| --- | --- | --- | --- |
| Kafka | `services/kafka/playbooks/apply.yml` | `verify.yml` | `discover*.yml` — диагностика read-only; reset — явное destructive recovery. |
| PostgreSQL | `services/postgresql/playbooks/apply.yml` | `verify.yml` | Оба включают PKI lifecycle. |
| BIND | `services/bind/playbooks/apply.yml` | `verify.yml` | Cluster barriers для candidate и active config. |
| DNS client | `services/dns-client/playbooks/apply.yml` | `verify.yml` | `projection.yml` — controller-only projection. |
| HAProxy | `services/haproxy/playbooks/apply.yml` | `verify.yml` | Полные candidate/active barriers. |
| Keepalived | `services/keepalived/playbooks/apply.yml` | `verify.yml` | Только lifecycle `prepare → Barrier A → activate → Barrier B → reconcile`. |

Пример: PostgreSQL.

```bash
export ANSIBLE_COLLECTIONS_PATH="$PWD/ansible-core/collections:$PWD/services/postgresql/ansible_collections"
ansible-playbook -i examples/valid/postgresql-standalone/inventory/hosts.yml \
  services/postgresql/playbooks/apply.yml \
  -e @examples/valid/postgresql-standalone/inventory/group_vars/all/platform.yml
```

Перед TLS-потребителем применяйте PKI. Kafka дополнительно получает runtime-only
файл с путём approved artifact и mapping secret-file, но без plaintext secrets.

## Runtime secrets в `.runtime`

Каталог `.runtime/` игнорируется Git. Каждый секрет хранится отдельным локальным
файлом с одним значением и правами `0600`; его имя и путь выбирает оператор.
В inventory указывается только `SecretRef`, а runtime input YAML сопоставляет
этот reference с файлом. Сам файл со значением не является YAML и не должен
попадать в shell history, логи или commit.

```text
.runtime/
├── artifacts/kafka/kafka_2.13-4.3.1.tgz
├── secrets/
│   ├── kafka-store-password       # одно локальное значение, mode 0600
│   └── postgresql-admin-password  # одно локальное значение, mode 0600
└── inputs/
    └── kafka-ssl.yml              # только пути и metadata, mode 0600
```

Пример `.runtime/inputs/kafka-ssl.yml` (значения секретов здесь отсутствуют):

```yaml
platform_kafka_artifact_path: /absolute/path/bundle/artifacts/kafka/kafka_2.13-4.3.1.tgz
platform_kafka_artifact_checksum: sha256:<approved-artifact-digest>
platform_pki_secret_files:
  runtime:pki-store-password: /absolute/path/.runtime/secrets/kafka-store-password
```

Ключ `runtime:pki-store-password` обязан точно совпадать с
`storePasswordSecretRef` выбранного TLS profile. Аналогично PostgreSQL использует
только mapping, например:

```yaml
platform_postgresql_secret_files:
  runtime:postgres-admin-password: /absolute/path/.runtime/secrets/postgresql-admin-password
```

Здесь ключ обязан совпадать с `passwordSecretRef` администратора или
pg_auto_failover credential. Перед запуском ограничьте права локально:

```bash
chmod 700 .runtime .runtime/secrets .runtime/inputs
chmod 600 .runtime/secrets/* .runtime/inputs/*.yml
```

## Примеры команд установки

Во всех примерах `<runtime-inputs>.yml` — Git-ignored runtime-only файл с
путями к approved artifacts и secret files. Не записывайте в него секреты как
значения и не добавляйте его в репозиторий.

### PKI

```bash
export ANSIBLE_COLLECTIONS_PATH="$PWD/ansible-core/collections"
ansible-playbook -i examples/valid/pki-host-scope/inventory/hosts.yml \
  ansible-core/playbooks/pki-apply.yml \
  -e @examples/valid/pki-host-scope/inventory/group_vars/all/platform.yml \
  -e @.runtime/<runtime-inputs>.yml
```

### Kafka с TLS

```bash
export ANSIBLE_COLLECTIONS_PATH="$PWD/ansible-core/collections:$PWD/services/kafka/ansible_collections"
ansible-playbook -i examples/valid/kafka-ssl-single/inventory/hosts.yml \
  ansible-core/playbooks/pki-apply.yml \
  -e @examples/valid/kafka-ssl-single/inventory/group_vars/all/platform.yml \
  -e @.runtime/<runtime-kafka-inputs>.yml
ansible-playbook -i examples/valid/kafka-ssl-single/inventory/hosts.yml \
  services/kafka/playbooks/apply.yml \
  -e @examples/valid/kafka-ssl-single/inventory/group_vars/all/platform.yml \
  -e @.runtime/<runtime-kafka-inputs>.yml
```

### PostgreSQL

```bash
export ANSIBLE_COLLECTIONS_PATH="$PWD/ansible-core/collections:$PWD/services/postgresql/ansible_collections"
ansible-playbook -i examples/valid/postgresql-standalone/inventory/hosts.yml \
  services/postgresql/playbooks/apply.yml \
  -e @examples/valid/postgresql-standalone/inventory/group_vars/all/platform.yml \
  -e @.runtime/<runtime-postgresql-inputs>.yml
```

### BIND и DNS client

```bash
export ANSIBLE_COLLECTIONS_PATH="$PWD/ansible-core/collections:$PWD/services/bind/ansible_collections"
ansible-playbook -i examples/valid/bind-authoritative/inventory/hosts.yml \
  services/bind/playbooks/apply.yml \
  -e @examples/valid/bind-authoritative/inventory/group_vars/all/platform.yml \
  -e @.runtime/<runtime-inputs>.yml

export ANSIBLE_COLLECTIONS_PATH="$PWD/ansible-core/collections:$PWD/services/dns-client/ansible_collections"
ansible-playbook -i examples/valid/bind-authoritative/inventory/hosts.yml \
  services/dns-client/playbooks/apply.yml \
  -e @examples/valid/bind-authoritative/inventory/group_vars/all/platform.yml
```

### HAProxy и Keepalived

```bash
export ANSIBLE_COLLECTIONS_PATH="$PWD/ansible-core/collections:$PWD/services/haproxy/ansible_collections"
ansible-playbook -i examples/valid/haproxy-routing/inventory/hosts.yml \
  services/haproxy/playbooks/apply.yml \
  -e @examples/valid/haproxy-routing/inventory/group_vars/all/platform.yml \
  -e @.runtime/<runtime-haproxy-inputs>.yml

export ANSIBLE_COLLECTIONS_PATH="$PWD/ansible-core/collections:$PWD/services/keepalived/ansible_collections"
ansible-playbook -i examples/valid/haproxy-routing/inventory/hosts.yml \
  services/keepalived/playbooks/apply.yml \
  -e @examples/valid/haproxy-routing/inventory/group_vars/all/platform.yml \
  -e @.runtime/<runtime-haproxy-inputs>.yml
```

## Владение файлами

Оператор редактирует inventory и документированные role variables. Поддержанные
managed settings и reserved advanced properties описаны в
`services/*/service.yml`; standalone defaults — в `roles/*/defaults/main.yml`.

Не редактируйте generated catalog/schema/locks, runtime workspace, generated
state, PKI plans, candidate/active configs и systemd units. Их владельцы —
generator, runtime/PKI lifecycle и соответствующая role. Перегенерация:

```bash
python3 ansible-core/tools/build_fixture_catalog.py
python3 ansible-core/tools/build_service_configuration_schema.py
```
