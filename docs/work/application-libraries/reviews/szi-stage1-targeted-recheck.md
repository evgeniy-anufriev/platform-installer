# СЗИ этап 1 — независимый TARGETED_RECHECK SZI-P01–P03

Вердикт: **BLOCK**. Проверенная версия `docs/work/application-libraries/szi-stage1-technical-plan.md`: SHA-256 `FF524338E4DC74C21DEE603D4DD3D292400FDA2EBD72A984861D7EA0D56E33DC`, base HEAD `7f044699f5b66ccbad4603978472275ce2010235`. Рассматривались только замечания исходного FULL PLAN review и непосредственно затронутые границы. Target QA не выполнялась.

| Замечание | Итог | Основание |
| --- | --- | --- |
| SZI-P01 | RESOLVED | Приоритеты библиотек помещены в Installer `config/application.yml`; точный порядок выбранных library IDs фиксируется в Core плане. Владелец явно допускает ранние мутации общих provider resources, но запуск/endpoint/read-only проверка идут побиблиотечно и отказ СЗИ останавливает запуск СДКУ. |
| SZI-P02 | **OPEN, BLOCKING** | `ansible_host` выбранного размещения и published port с проверкой SAN устраняют зависимость от неопубликованного маршрута, но план требует живую HTTPS-достижимость **до Apply**. При холодном старте контейнер ещё не запущен. До Apply допустимы структурные проверки адреса/порта/ожидаемой TLS identity; живую HTTPS/TLS-проверку нужно выполнить после readiness непосредственно перед `create-admin`. Проверить первый и повторный Apply без существующего nginx/HAProxy маршрута. |
| SZI-P03 | RESOLVED | Проверенный образ доставляется до `before_start`; временный `docker compose run --rm --no-deps` с нужными mounts и protected-file secret inputs задаёт исполнимый путь CLI без SZI-ветки в Core. Холодный старт/повтор/обрыв остаются QA. |

В исправленном объёме ненужных абстракций, дублирующих контрактов/DTO и упущенного более простого готового механизма не выявлено. Проверены план, исходный FULL review, Installer config/model и затронутые Core/Compose входы. Бюджет одного FULL и одного TARGETED_RECHECK использован. По [процедуре review](../../../agent-procedures/review.md) после повторного `BLOCK` автоматические исправления и review не продолжаются; следующий review требует явного запроса владельца.
