# SERVER-INFORMATION-CHECK-01

Document scope: the original milestone contract/design. Historical status, review
and QA checkpoints are collected separately; current status and authorization
are recorded only in [CURRENT_STATE](../../../CURRENT_STATE.md).

## Решение владельца и область

Владелец 2026-10-08 разрешил прямую информационную SSH-проверку из Go на workstation как для target server, так и для Execution Node до подготовки Core. Установка, инфраструктурная семантика и Ansible остаются исключительно на Execution Node. V1 — справочник UX, его пакеты не копируются. Это новая узкая проверка, не Core discovery и не разрешение Plan/Start.

## UX

В строке/карточке сохранённого сервера одна outline-кнопка «Проверить сервер». Кнопка открывает существующее по стилю окно подтверждения SSH-ключа: адрес/порт, тип ключа и SHA256-отпечаток, явное подтверждение после независимой сверки. После подтверждения автоматически выполняется ограниченное подключение и чтение информации. Отмена не запускает подключение. Повторная проверка снова получает текущий ключ и требует явного подтверждения; нет скрытой замены доверенного ключа.

Для Execution Node вместо отдельных «Получить отпечаток SSH» и «Проверить узел» — одна «Проверить сервер». Сбор сведений работает до Core. После успешного информационного подключения вызывается существующая read-only проверка readiness; подготовка остаётся отдельным действием, не выполняется автоматически. Состояние информационной проверки не заменяет готовность runtime.

Под карточкой сервера, мелким шрифтом, без раскрытия: фактический hostname; ОС/версия/архитектура; логические CPU и общий RAM; время сервера; последняя успешная проверка в ru-RU Europe/Moscow. Время сервера показывается как дата/время МСК с сохранённым UTC timestamp. Иные сведения не собираются. При успехе отдельный статус «Проверен»; сохранённость желаемой конфигурации показывается независимо. Ошибка не обозначает успех. Смена адреса/порта/credentials, проекта или ревизии сбрасывает актуальность наблюдений. Ошибки показываются безопасным русским текстом.

## Go и безопасность

Добавить один узкий информационный operation facade для saved hostId, а не произвольных адресов/команд от React. Подключение использует сохранённый typed server address/port и действующий SSH-сеанс (пароль или PEM); Go не разрешает Ansible precedence, effective installation connection может отличаться. Явно показывать, что проверен адрес карточки. Владелец уточнил: одно явное подтверждение ключа используется и для информационной проверки, и для установки. После успешного подключения точный подтверждённый ключ заносится в существующий session-only installation trust с привязкой к проекту, ревизии и адресу/порту. Execution Node получает тот же pin. Это не approval плана: Build/Approve/Start остаются обязательными. Несовпадение ключа или effective installation endpoint блокирует подключение.

Для target новый bounded прямой probe/approval/check путь передаёт pin в существующий installation trust; повторного подтверждения через Execution Node не требуется. Approval одноразовый token, 2 минуты, привязка project root/id/revision, host/address/port, credential generation и точный public key. Никакой StrictHostKeyChecking=no: OpenSSH подключение только с pin в runtime known_hosts, IdentitiesOnly=yes; для PEM BatchMode=yes, для пароля bounded ASKPASS без key fallback, таймаутом 20 секунд и ограничением вывода 16 KiB. Приватные ключи/пароли не выводятся, не сохраняются вне established identity mechanism. Хранить временный known_hosts только .runtime/secrets или established runtime identity mechanism, удалять после операции. Ошибки raw stderr не передаются UI.

Команда статична и не принимает пользовательские строки: hostname; /etc/os-release (только NAME/VERSION_ID); uname -m; getconf _NPROCESSORS_ONLN; MemTotal /proc/meminfo; date UTC. Не source/eval os-release. Использовать ограниченный структурированный формат с allowlist полей и строгой Go-валидацией. Никакого sudo/установки/Python/Ansible/изменения целевого состояния для этой операции. Partial сбор не получает статус «Проверен»; причина отказа безопасна. Context отменяет локальное подключение, не remote install. Короткие блокировки App для capture/revalidation; сетевое ожидание вне editMu. Поздний ответ при изменении binding не публикуется.

Наблюдения живут только в памяти UI/Go-сеанса, не project.yml/inventory/SQLite. Нет фонового сканирования, нового lifecycle framework или persistence. Новые Wails методы и Browser transport описывают тот же Go facade.

## Проверки и статус

План реализации разрешён владельцем; FULL PLAN review повторно требуется после owner-approved изменения прямого informational SSH boundary, предыдущие SC-01/SC-02 относятся к отвергнутому Core discovery варианту. HIGH-RISK FULL DIFF review для direct SSH/trust boundary после реализации. При BLOCK остановиться с конкретными finding IDs; автоматическое повторное ревью не выполняется.

Focused Go tests: timeout/output bounds/parser, binding mismatch, expired token, changed key, credential replacement, unknown host, SSH failure, secret-safe errors; frontend flow confirm/cancel/read-only facts/status invalidation; Go test/vet и frontend tests/typecheck/lint/build. Реальная React/Wails informational target+exec проверки с действующим PEM/trust и визуальная проверка обязательны; нет authorization новой установки/сброса/подготовки targets. Core tests не нужны при отсутствии Core изменений. Обновить architecture/ADR/roadmap/UI contract с narrow owner-approved exception до acceptance. Текущие uncommitted recovery/status/date изменения сохраняются.

Recorded status and review scope: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#server-information-check-plan-checkpoint-002).




Owner-observed acceptance and reviewer outcome: [historical checkpoint](evidence/documentation-checkpoints-20261012.md#server-information-check-plan-checkpoint-001).
