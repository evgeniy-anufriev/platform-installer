# СЗИ этап 1 — дополнительный TARGETED_RECHECK SZI-P02

Вердикт: **APPROVE_WITH_CHANGES**. Неразрешённых блокирующих замечаний: **0**. Дополнительная точечная проверка запрошена владельцем после исчерпания обычного бюджета review. Проверенная редакция `docs/work/application-libraries/szi-stage1-technical-plan.md`: SHA-256 `2F84CCAEC024C063BBA8810BC98987D5142526A42D94F319091334D665CFEEA1`; base HEAD `7f044699f5b66ccbad4603978472275ce2010235`. Объём — SZI-P02 и непосредственно затронутые границы scripts, Core preflight, TLS и endpoint stage. P01/P03 повторно не рассматривались.

## SZI-P02 — RESOLVED

Живая HTTPS-проверка перенесена в `create-admin` после readiness (§5–6 плана). `placement_https` использует `ansible_host` выбранного размещения и effective published port, поэтому не зависит от ещё не опубликованного маршрута nginx/HAProxy. Скрипт проверяет CA и имя/IP SAN до Admin API. Отдельный pre-Apply TLS probe в Core не требуется. Прежний блокер холодного старта устранён.

## SZI-P02-N01 — NON_BLOCKING, решение владельца зафиксировано

Ревьюер предложил явно закрепить выбор порта из `settings.ports[settings.endpoint.listener].published` и требование `settings.endpoint.protocol: https`. У Keycloak несколько портов; существующий endpoint selector достаточен, новое поле не нужно.

**Решение владельца после review:** отдельное закрепление в контракте не требуется; `placement_https` использует текущую реализацию endpoint placement. Предложение N01 не включать в план как новое контрактное правило. При реализации проверить, что выбранный placement ведёт к нужному порту и HTTPS-соединение проходит штатную проверку сертификата после readiness.

## Оценка границы и доказательства

Ненужных абстракций, дублирующих контрактов/DTO, преждевременных функций и упущенного более простого механизма не выявлено. Независимый ревьюер прочитал текущий план, предыдущие FULL и TARGETED_RECHECK заключения, `AGENTS.md`, `CURRENT_STATE.md`, процедуру review, схему endpoint settings, Core Apply/preflight/readiness/endpoint-код и draft Keycloak Compose/defaults. Тесты и target QA не выполнялись; работа сертификата, сети и скрипта на стенде не доказана. Заключение действительно только для указанного SHA и объёма. Изменение выбора адреса/порта, TLS identity или фазы `after_ready` требует повторной оценки затронутой части.
