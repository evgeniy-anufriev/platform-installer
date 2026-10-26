# SERVICE-RUNTIME-OPTIMIZATION — общая подготовка, этап 2

Владелец 2026-10-26 принял дополнительные направления оптимизации по профилю
текущего run и разрешил реализацию в том же worktree. Это отдельный review gate
для расширенной области; прежний FULL DIFF/D01 recheck сохраняются как история.

## Границы и реализация

1. Полный `ansible-core/playbooks/validate.yml` сохраняет текущую семантику:
   инфраструктура и библиотеки проверяются до общего Plan/Start. Выделить его
   общие pre_tasks и вызов существующего validate_project в небольшие task files.
   Добавить явно названный `validate-infrastructure.yml`: тот же сбор обычных
   inventory/group_vars/host_vars и проверка инфраструктуры, без загрузки defaults
   приложений и без project_snapshot приложений. Артефакт по умолчанию имеет
   отдельное имя infrastructure-validation-result.json; это не полный Project
   Verify и не авторизация выполнения. Сервисные Apply и DNS projection используют
   инфраструктурную проверку; общий Validate/Plan/Start остаётся полным. Новых
   flags, DTO, cache, Go/UI веток и способов обхода Start admission нет.
2. При публикации endpoint обычного инфраструктурного serviceDeployment
   resolve-source не вызывает resolver приложений. Сервисная проекция вычисляется
   существующими Core modules прямо из desired state. Не записывать пустой
   platform_endpoint_sources как признак готовности приложений. Для источника
   приложения текущий resolver/fallback сохраняется. Частичная публикация должна
   сохранять ранее опубликованные маршруты других источников.
   Shortcut действует также в HAProxy resolve.yml: только для явно непустой
   partial scope, full_reconcile=false и всех ID из serviceDeployments. Пустая
   или некорректная partial scope по-прежнему блокируется до публикации.
3. artifact_source_resolution выполняет один dnf repoquery со всеми именами
   текущей группы требований на каждом узле. Существующий filter по-прежнему
   проверяет каждое имя/version/os/architecture и выбирает repository -> offline
   -> blocked. При неуспешном batch query сохранить прежнее раздельное чтение,
   чтобы частичный результат общего запроса не менял приоритет источников.
   Репозитории не меняются, совместимость/целостность bundle не ослабляются.
4. PostgreSQL: сохранить отдельные условия REPOSITORY/OFFLINE для PostgreSQL и
   pg_auto_failover, но собрать разрешённые repository packages в один вызов
   package. Проверять альтернативное семейство имён только если основное не
   найдено. Не считать доустановочный поиск pg_ctl готовым после установки новых
   пакетов. Если ничего не изменилось и pg_ctl уже найден, повторный поиск не нужен.
5. Docker уже устанавливает список пакетов одним вызовом. Нового installer или
   package cache не добавлять; выигрыш ожидается от общей пакетной repoquery.
6. PKI уже использует --skip-tags platform_installer_pki_materialization после
   общего Apply. Проверки integrity/привязки плана/источников сохраняются. Убрать
   лишь повторный keytool probe, если первый уже успешен. Кеш между процессами и
   доверие к одному факту «PKI выполнен раньше» вместо проверки не вводить.
7. BIND/HAProxy Verify неизменны. Сервисные endpoints публикуются сразу после
   readiness, прежде потребителей. Между controller operations публикация не
   переносится: отдельные процессы пока не образуют безопасную общую batch-группу.
   Не вводить новый scheduler/барьер ради группировки. Дальнейшее пакетирование
   нескольких источников допустимо только в уже существующей одной операции.

## QA

- Полный Validate по-прежнему блокирует ошибочные библиотеки; инфраструктурный
  путь не загружает их defaults, но блокирует ошибочную инфраструктуру.
- Native standalone без Go, варианты обычного inventory и legacy metadata,
  сохранение Ansible precedence и target-free validation.
- Native endpoint service source не запускает app resolver; app source запускает
  его при необходимости; existing sources не теряются, прежние backend fixtures.
- Native dnf stub и существующий real filter: mixed versions/architectures,
  одно отсутствующее имя, batch rc!=0, доступный repository + offline, blocked;
  argv не зависит от shell, один успешный вызов для группы.
- PostgreSQL: обе repository, обе offline и смешанные источники; единственная
  package-транзакция только для выбранных repository packages; правильный fallback
  названий и обнаружение pg_ctl после реальной установки.
- Focused service/Core regression на RED OS через qa-sync, source hash evidence,
  syntax. Native PKI проверка без изменения целостности и secret/no_log контракта.
- Активный run/runtime bundle не меняются. Нет нового реального run и заявления
  об ускорении до измерения обновлённой реализации. React/Wails приёмка остаётся
  открытой до обновлённого bundle и отдельного поддерживаемого цикла.

## Review

FULL PLAN: APPROVE_WITH_CHANGES, blocking0, independent architecture-reviewer.
Reviewed plan SHA256 `6f3431e6dd46bcb8d7f488c6f9a13187968dc2ffdd447a683f7ba57207b33297`.
SRO2-N01: обе точки endpoint shortcut и непустая scope; уточнено выше.
SRO2-N02: явные пустые application findings для инфраструктуры и раздельные
артефакты; реализуются общими task files без новых DTO.
SRO2-N03: успешный полный package family, независимые смешанные источники,
повторный pg_ctl поиск после установки/исходного отсутствия; покрываются native QA.
Повторный PLAN review для этих ограниченных уточнений не требуется.
