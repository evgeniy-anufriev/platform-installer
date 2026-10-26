# Оптимизация СЗИ и общей доставки — этап 4

Владелец 2026-10-26 разрешил реализацию после профиля СЗИ55:45.
Текущий run/bundle не менять, новый установочный план не запускать.

## Пакетные hooks без знания продукта в Core

- Package v1alpha4 (прежние v1–v3 закрытые схемы неизменны) добавляет только
  опциональное `batch: true` для provider_prepare / connection_apply,
  execution=once. По умолчанию false. Go import допускает новую версию;
  прежний post_install feature/version не меняется, нового UI нет.
- Подготовка обычных argv/secret references остаётся прежней. В пределах одного
  готового provider batch объединяются только соседние совместимые opt-in hooks:
  один order, runOn, target и точный набор secret input references; одинаковое
  содержимое allowlisted source (SHA256) и ID скрипта. Не переходить через
  границы порядка, готовности или accounts. Разные client_secret — разные вызовы.
- Группа содержит исходные argv в исходном порядке; зависимости каждого
  потребителя/shared fields вычисляются до группировки и сохраняются.
  Script runner получает обычную job с invocation list. Для batch он пишет
  JSON-массив argv в приватный файл внутри собственного temporary input directory
  и передаёт единственный дополнительный generic env
  PLATFORM_SCRIPT_BATCH_FILE. Аргументы команды batch-script пустые.
  Нет секретных значений в batch JSON, только прежние несекретные argv.
  Прямой вызов batch-enabled скрипта также получает список из одного элемента.
- Раннер ничего не знает о Keycloak/контейнерах. Input directory cleanup сохраняется
  при успехе/ошибке, разные secrets и accounts не переиспользуются между вызовами.
- integration.sh поддерживает batch-файл: проверяет одинаковый URL/realm/admin,
  получает admin token один раз, выполняет исходные операции последовательно,
  суммирует changed. Отказ операции останавливает пакет, следующий Apply читает
  состояние заново. Частичные изменения не откатываются. Bootstrap не пакетируется.
  Opt-in только у provider client callback и prepare-groups wrappers библиотек
  СЗИ/СДКУ/CSPA. Исходные group→client→role→account границы сохраняются.

## Раннер и Vault

- Объединить независимые set_fact и заменить цикл построения environment из
  secretInputs одним стандартным map/zip/combine. Каталог и allowlisted source
  доставляются штатными builtin file/copy на каждый вызов. Кеша готовности
  скриптов нет. Копирование секретов и очистку на каждый вызов сохранить.
- instance.yml вместо двойного чтения preflight вызывает один полный preflight
  и согласование документов непосредственно внутри себя. deliver-ready удаляет
  внешний повтор; standalone instance сохраняет чтение перед записью.
  Policy/role ownership и KV CAS/read/retry остаются прежними.
- Vault runtime token/CA уже обнаруживаются по провайдеру: не вводить второй
  login cache. Host route/LXC CIDR discovery переиспользовать в пределах вызова
  только для одинакового provider routeAddress, host, bridge; записи role/policy
  остаются индивидуальными и проверяются перед изменением.

## Endpoints и образы

Текущая ordered-library уже пакетно публикует независимые endpoints; отдельная
ранняя публикация нужна готовому провайдеру. Нового механизма не вводить.
Проверить повторную передачу одного source SHA на один host/account в текущем
вызове; reuse только уже проверенного доставленного архива с сохранением digest
и image inspect. Не параллелить тяжёлые load на малоресурсных QA hosts.

## QA и ограничения

FULL PLAN до реализации, FULL DIFF после focused QA. RED OS из текущих sources:
schema compatibility/invalid batch phases, projection order/secret separation/
skipped provider; script native fresh/repeat/failure, одна admin authentication;
реальные Ansible role calls на isolated stub endpoints: env/delivery cache host/
account/source isolation, cleanup success/failure, standalone Vault + deferred
delivery, CAS conflict and foreign ownership, CIDR isolation. Existing affected
regression suites. No target mutation, production service writes or updated run.
Предел TASK-журнала диагностирован отдельно; его изменение не включено в этот
план оптимизации и не считается исправленным. Реальный benchmark/UI pending.

Уточнение N02: timeout300s×N, singleton300s. Приватный каталог batch JSON создаётся
даже при пустом secretInputs. Generated password на deferred preflight берётся
из ранее выбранного protected runtime file после ownership/deletion checks.

FULL DIFF BLOCK SRO4-D01: передача общего .scripts другому аккаунту позволяет
заменить соседний файл. Владелец выбрал отказ от кеша source files и разрешил
один TARGETED_RECHECK. Штатный idempotent copy восстанавливает bytes/owner/mode
каждый вызов. Native proof: root A(first) → nobody B(second), B подменяет first
в общем каталоге → root A(first), должны быть восстановлены исходные bytes и
исполнен A. Остальные package batching/Vault границы остаются прежними.
