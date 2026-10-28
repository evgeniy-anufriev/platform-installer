# Оптимизация подготовки библиотек — этап 3

Владелец принял оптимизацию 2026-10-26. Текущий run/bundle не менять.

1. По отдельному решению владельца убрать post-create describe/config readback
   топиков. Сохранить начальное пакетное чтение, drift validation и отказ при
   ошибке create. Успех `--if-not-exists` не исключает конкурентного создания;
   фактические параметры проверяются следующим Apply.
2. Preflight: заменить три задачи сборки config/archive pairs одним стандартным
   map/zip/sort, объединить независимые facts image platform/environment.
   Сохранить точный digest, порядок зависимых вычислений, проверки путей,
   namespace, владельцев, кеш discovery. Новых механизмов кеширования нет.
3. ACL: внутри одной учётной записи сначала вычислить недостающие операции
   существующим точным predicate (resource/name/pattern/principal/host/ALLOW).
   Сгруппировать только одинаковые resourceType, patternType и набор операций.
   Для каждой группы один argv Kafka CLI с повторными ресурсными селекторами.
   Разные типы, шаблоны и операции не объединять. Principal один на аккаунт,
   allow-host=* неизменен. Перед каждым аккаунтом сбрасывать группы.
   Убедиться в поддержке повторных селекторов CLI до реализации.
   Прямые callers application_acl.yml сохраняют прежнее немедленное выполнение;
   batching включается только внутренним параметром вызывающей задачи аккаунта.
   Ключ использует отсортированные уникальные missing operations; повторные
   имена дедуплицируются, cluster selector один. Флаг batching — scoped include
   vars, не set_fact. Один общий writer обслуживает batch и прямой caller.
   Verify/existing только проверяют, не создают. Ошибка записи блокирует Apply.
   CLI не атомарен: частичная запись допустима до ошибки; последующие группы не
   запускаются, следующий Apply по свежему snapshot добавляет оставшуюся дельту.
   Нет удаления ACL, нового парсера, модуля, DTO, desired-state схемы или секрета
   в argv. Прежние private properties и cleanup сохраняются.

QA на RED OS из текущей source copy: реальные Ansible includes с подставными
CLI, fresh/repeat/no-write, partial missing operations, разделение pattern/type/
principal/operation, ошибка CLI; native digest regression. Дополнительно
проверить реальный установленный Kafka CLI на разбор повторных селекторов без
обращения к работающему broker (неизвестные данные не создавать).
FULL PLAN для ACL batching и FULL DIFF перед завершением; пользовательские
упрощения topic/preflight уже реализованы с focused QA и не меняют архитектуру.
Реальная обновлённая установка/React-Wails/benchmark остаются pending, без
автоматического запуска нового плана.
