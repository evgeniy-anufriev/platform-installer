# ENDPOINT-HAPROXY-PLACEMENT-01 — узкий план реализации

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#endpoint-haproxy-placement-plan-checkpoint-001).



## Требования

Выбор цели: сервис.endpointGroup → Keepalived.endpointGroupRef → заданные
серверы Keepalived → размещения HAProxy той же группы на этих серверах.
Применять ко всем найденным provider/host парам; не вводить блокировки
полного покрытия VIP, единственности HAProxy или количества на сервере.
Параметры haproxy.backend сохранить, deploymentRef перестаёт выбирать цели.
Не обнаруживать живые процессы для разрешения отношений.

Нет подходящего размещения: ошибка «HAProxy для endpoint не найден» в общем
Core журнале, backend-интеграция пропущена, установка продолжается.
Предусмотренный, но недоступный HAProxy — существующая ошибка исполнения.

## Изменения

1. Расширить существующий service_integration_resolution входом inventory
   placements. Добавить shared bounded функцию разрешения provider/host
   пар. Переиспользовать её в haproxy_resolution и project_snapshot.
2. Existing resolved integration projection содержит несколько HAProxy IDs
   и host scope. Никаких новых persistent DTO или desired-state store.
3. haproxy_resolution строит backend для всех выбранных providers, сохраняя
   прежние ports/TLS/options/template contracts. В backend projection дать
   host scope, чтобы публикация не затрагивала provider вне пересечения.
4. Existing apply-endpoint/reconcile modules/playbooks передают inventory;
   partial integrate ограничивает prepare/activate/start целевыми host IDs.
   Full provider path строит ту же модель; сохраняются existing archives,
   partial source filtering, candidate validation, publication и recovery.
5. Planner dependencies выбирают найденные provider IDs, а не deploymentRef.
   Source Apply зависит от выбранных base HAProxy Apply: существующий partial
   hook вызывается после здоровья source и требует подготовленный provider.
   Устаревший обратный source-before-provider барьер удаляется, поскольку base
   HAProxy уже не потребляет будущие backend. При конфликте выбранного порядка
   сохраняется существующее блокирование, без автоматической перестановки.
   Публичные схемы допускают backend-only объект haproxy; legacy deploymentRef
   принимается для чтения, игнорируется при выборе и не удаляется молча.
   Действующие runtime/schema digests и bundle validation фиксируют обновление.
   Владелец отдельно согласовал package defaults: roundrobin, check=true,
   fall=3, rise=2, ssl=true, sslVerify=required. Они объявлены в service manifests
   и потребляются существующей нормализацией; backend override сохраняется.
6. Missing-provider вывести через existing event/result mechanisms без
   fail-stop и without ignore_errors для других ошибок. Сохраняется текущий
   terminal lifecycle; запись должна различать ошибку и пропуск интеграции.
   Не вводить новый PARTIAL terminal state или новую UI lifecycle семантику.
7. Перенос/удаление использует только имеющиеся source-owned partial/reconcile
   пути и доказанные managed inventories/archives. Не вводить durable intent,
   per-source receipt store или distributed transaction. Если текущий путь
   не может выполнить отдельный сценарий, зафиксировать конкретное ограничение
   и вернуть владельцу, а не строить новый механизм в этой задаче.

## За пределами задачи

Новые гарантии атомарности, автоматический rollback, новый journal/state,
новая миграционная подсистема, установка HAProxy при отсутствии размещения,
изменение существующих fail-stop ошибок и общая транзакция переноса.
Owner явно поручил переиспользовать существующий backend код с необходимыми
правками для новой привязки. Старые EHP-01/EHP-02 не заявляются исправленными:
их предмет исключён новым согласованным scope.

## Проверки

RED OS current-source resolver/planner/schema и affected integration/HAProxy
тесты; полный existing test suite affected modules. Проверить same group,
partial overlap, several HAProxy, no suitable provider, stale deploymentRef,
backend-only settings, ports/TLS, host filtering во всех стадиях, source prefix
ownership и сохранение других fragments. Обновить representative fixtures.
No new topology logic in Go/React. Standalone Ansible must work.

Реальный full-services UI retry, HTTPS checks, unchanged repeat и move/delete
acceptance выполняются только по отдельно согласованному сценарию. Подготовка
bundle/Start/cleanup сейчас не разрешена. Source implementation не является
полной acceptance. Независимый FULL DIFF review после реализации.
