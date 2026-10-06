import { useEffect, useMemo, useState } from "react";
import type { InstallationEventView } from "./backend";
import "./utility-pages.css";

const LOGS_PAGE_SIZE = 512;

type EventColumn = {
  key: string;
  label: string;
  value: (event: InstallationEventView) => string;
};

const eventColumns: EventColumn[] = [
  { key: "sequence", label: "№", value: (event) => String(event.sequence) },
  { key: "timestamp", label: "Время", value: (event) => event.timestamp },
  {
    key: "eventType",
    label: "Тип события",
    value: (event) => eventTypeLabel(event.eventType),
  },
  {
    key: "status",
    label: "Статус",
    value: (event) => eventStatusLabel(event.status),
  },
  {
    key: "safeMessage",
    label: "Сообщение",
    value: (event) => event.safeMessage,
  },
  { key: "phaseId", label: "Этап", value: (event) => event.phaseId || "—" },
  {
    key: "actionId",
    label: "Действие",
    value: (event) => event.actionId || "—",
  },
  {
    key: "serviceDeployment",
    label: "Развёртывание сервиса",
    value: (event) => event.serviceDeployment || "—",
  },
  { key: "host", label: "Узел", value: (event) => event.host || "—" },
  {
    key: "taskRole",
    label: "Роль задачи",
    value: (event) => event.task?.role || "—",
  },
  {
    key: "taskName",
    label: "Задача",
    value: (event) => event.task?.name || (event.task ? "Скрыто" : "—"),
  },
  {
    key: "taskUUID",
    label: "ID задачи",
    value: (event) => event.task?.uuid || "—",
  },
  {
    key: "elapsed",
    label: "Длительность",
    value: (event) =>
      event.elapsedMilliseconds === undefined
        ? "—"
        : `${event.elapsedMilliseconds} мс`,
  },
  {
    key: "errorCode",
    label: "Код ошибки",
    value: (event) => event.errorCode || "—",
  },
  {
    key: "errorSummary",
    label: "Описание ошибки",
    value: (event) => event.errorSummary || "—",
  },
  {
    key: "redacted",
    label: "Редакция данных",
    value: (event) => (event.redacted ? "Применена" : "Нет"),
  },
  { key: "runId", label: "ID запуска", value: (event) => event.runId },
];

const defaultVisibleColumns = [
  "timestamp",
  "eventType",
  "safeMessage",
  "serviceDeployment",
  "host",
  "status",
];

function eventTypeLabel(value: string): string {
  const labels: Record<string, string> = {
    RUN_STARTED: "Запуск начат",
    PHASE_STARTED: "Этап начат",
    ACTION_STARTED: "Действие начато",
    TASK_STARTED: "Задача начата",
    TASK_COMPLETED: "Задача завершена",
    ACTION_COMPLETED: "Действие завершено",
    PHASE_COMPLETED: "Этап завершён",
    RUN_COMPLETED: "Запуск завершён",
    DIAGNOSTIC: "Диагностика",
  };
  return labels[value] || value;
}

function eventStatusLabel(value: string): string {
  const labels: Record<string, string> = {
    PENDING: "Ожидает",
    RUNNING: "Выполняется",
    SUCCESS: "Успешно",
    CHANGED: "Изменено",
    SKIPPED: "Пропущено",
    FAILED: "Ошибка",
    CANCELLED: "Отменено",
    INTERRUPTED: "Прервано",
  };
  return labels[value] || value;
}

function EventLog({
  events,
  runId,
}: {
  events: InstallationEventView[];
  runId?: string;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [selectedSequence, setSelectedSequence] = useState<number>();
  const [visibleColumns, setVisibleColumns] = useState<string[]>(
    defaultVisibleColumns,
  );
  useEffect(() => {
    setPage(0);
    setSelectedSequence(undefined);
  }, [runId]);
  const orderedEvents = useMemo(
    () => [...events].sort((a, b) => a.sequence - b.sequence),
    [events],
  );
  const filteredEvents = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("ru");
    if (!needle) return orderedEvents;
    return orderedEvents.filter((event) =>
      eventColumns.some((column) =>
        column.value(event).toLocaleLowerCase("ru").includes(needle),
      ),
    );
  }, [orderedEvents, query]);
  const pageCount = Math.max(
    1,
    Math.ceil(filteredEvents.length / LOGS_PAGE_SIZE),
  );
  const currentPage = Math.min(page, pageCount - 1);
  const pageEvents = filteredEvents.slice(
    currentPage * LOGS_PAGE_SIZE,
    (currentPage + 1) * LOGS_PAGE_SIZE,
  );
  const selectedEvent =
    filteredEvents.find((event) => event.sequence === selectedSequence) ||
    filteredEvents.at(-1);
  const visible = eventColumns.filter((column) =>
    visibleColumns.includes(column.key),
  );

  return (
    <>
      <div className="event-log-toolbar">
        <label className="event-log-search">
          Поиск по событиям
          <input
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setPage(0);
            }}
            placeholder="Сообщение, задача, узел…"
          />
        </label>
        <details className="event-log-columns">
          <summary>
            Колонки ({visible.length} из {eventColumns.length})
          </summary>
          <fieldset>
            <legend>Показывать колонки</legend>
            {eventColumns.map((column) => (
              <label key={column.key}>
                <input
                  type="checkbox"
                  checked={visibleColumns.includes(column.key)}
                  onChange={(event) =>
                    setVisibleColumns((current) =>
                      event.target.checked
                        ? [...current, column.key]
                        : current.filter((key) => key !== column.key),
                    )
                  }
                />
                {column.label}
              </label>
            ))}
          </fieldset>
        </details>
      </div>
      <div className="event-log-layout">
        <section
          className="event-log-table-panel"
          aria-label="События текущего запуска"
        >
          <div className="event-log-table-scroll">
            <table className="event-log-table">
              <thead>
                <tr>
                  {visible.map((column) => (
                    <th key={column.key} scope="col">
                      {column.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageEvents.map((event) => (
                  <tr
                    key={`${event.runId}-${event.sequence}`}
                    className={
                      selectedEvent?.sequence === event.sequence
                        ? "is-selected"
                        : ""
                    }
                    onClick={() => setSelectedSequence(event.sequence)}
                  >
                    {visible.map((column) => (
                      <td key={column.key} title={column.value(event)}>
                        {column.value(event)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {pageEvents.length === 0 && (
              <p className="event-log-empty">
                {events.length
                  ? "По заданным условиям события не найдены."
                  : "События появятся здесь после запуска плана."}
              </p>
            )}
          </div>
          <footer className="event-log-pagination">
            <span>
              {filteredEvents.length
                ? `Показаны ${currentPage * LOGS_PAGE_SIZE + 1}–${Math.min((currentPage + 1) * LOGS_PAGE_SIZE, filteredEvents.length)} из ${filteredEvents.length}`
                : "Нет событий"}
            </span>
            <button
              type="button"
              onClick={() => setPage((value) => Math.max(0, value - 1))}
              disabled={currentPage === 0}
            >
              Назад
            </button>
            <span>
              Страница {currentPage + 1} из {pageCount}
            </span>
            <button
              type="button"
              onClick={() =>
                setPage((value) => Math.min(pageCount - 1, value + 1))
              }
              disabled={currentPage >= pageCount - 1}
            >
              Далее
            </button>
          </footer>
        </section>
        <aside className="event-log-details" aria-label="Подробности события">
          <h2>Детали события</h2>
          {selectedEvent ? (
            <>
              <strong>
                {eventTypeLabel(selectedEvent.eventType)} ·{" "}
                {eventStatusLabel(selectedEvent.status)}
              </strong>
              <p>{selectedEvent.safeMessage}</p>
              <dl>
                <dt>Время</dt>
                <dd>{selectedEvent.timestamp}</dd>
                <dt>Этап / действие</dt>
                <dd>
                  {[selectedEvent.phaseId, selectedEvent.actionId]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </dd>
                <dt>Развёртывание сервиса</dt>
                <dd>{selectedEvent.serviceDeployment || "—"}</dd>
                <dt>Узел</dt>
                <dd>{selectedEvent.host || "—"}</dd>
                <dt>Роль / задача</dt>
                <dd>
                  {[
                    selectedEvent.task?.role,
                    selectedEvent.task?.name ||
                      (selectedEvent.task ? "Скрыто" : ""),
                  ]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </dd>
                <dt>ID задачи</dt>
                <dd>{selectedEvent.task?.uuid || "—"}</dd>
                <dt>Длительность</dt>
                <dd>
                  {selectedEvent.elapsedMilliseconds === undefined
                    ? "—"
                    : `${selectedEvent.elapsedMilliseconds} мс`}
                </dd>
                <dt>Ошибка</dt>
                <dd>
                  {[selectedEvent.errorCode, selectedEvent.errorSummary]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </dd>
                <dt>Редакция данных</dt>
                <dd>{selectedEvent.redacted ? "Применена" : "Нет"}</dd>
                <dt>ID запуска</dt>
                <dd>{selectedEvent.runId || runId || "—"}</dd>
              </dl>
            </>
          ) : (
            <p>Выберите событие, чтобы увидеть подробности.</p>
          )}
        </aside>
      </div>
    </>
  );
}

type Props = {
  page: string;
  events: InstallationEventView[];
  runId?: string;
  configVersion?: number;
  serverTypes: Array<{ id: string; displayName: string }>;
  configError: string | null;
};

export function UtilityPages({
  page,
  events,
  runId,
  configVersion,
  serverTypes,
  configError,
}: Props) {
  if (page === "logs")
    return (
      <section className="utility-page" aria-labelledby="logs-title">
        <header className="utility-page-title">
          <div>
            <h1 id="logs-title">Журналы</h1>
            <p>События текущего выполнения в безопасном представлении.</p>
          </div>
          {runId && <span className="utility-status">Выполнение {runId}</span>}
        </header>
        <EventLog events={events} runId={runId} />
      </section>
    );

  if (page === "help")
    return (
      <section className="utility-page" aria-labelledby="help-title">
        <header className="utility-page-title">
          <div>
            <h1 id="help-title">Справка</h1>
            <p>Совместимость проекта с проверенным набором установки.</p>
          </div>
        </header>
        <section className="utility-card">
          <h2>Почему каталог может быть недоступен?</h2>
          <p>
            Проект закреплён за конкретным набором установки и каталогом
            описаний сервисов. Если подходящего проверенного набора нет в
            локальном кэше, сохранённые настройки остаются в проекте, но
            редактирование параметров сервисов отключается. Это не удаляет
            настройки.
          </p>
        </section>
        <section className="utility-card">
          <h2>Как обновить привязку существующего проекта?</h2>
          <ol>
            <li>
              Сохраните резервную копию проекта через «Экспортировать проект».
            </li>
            <li>
              Получите проверенный неизменяемый набор установки от поставщика и
              скопируйте его целиком в папку bundle внутри проекта.
            </li>
            <li>
              На странице «Проект» нажмите «Проверить новый набор», сравните
              версии и digest, затем нажмите «Привязать». Обнаружение набора
              само по себе проект не изменяет.
            </li>
            <li>
              Откройте проект заново и проверьте его через Core. Перед
              установкой сформируйте и одобрите свежий план.
            </li>
          </ol>
          <p>
            Инсталлятор проверяет старую ревизию проекта и новый набор. Если
            каталог не менялся, обновляется только привязка к набору; если
            менялся — атомарно обновляется пара «набор + каталог».
          </p>
          <p>
            Не меняйте digest вручную в project.yml и не выбирайте «последний»
            набор без проверки. Обычное сохранение проекта не обновляет эту
            привязку.
          </p>
        </section>
      </section>
    );

  if (page === "about")
    return (
      <section className="utility-page" aria-labelledby="about-title">
        <header className="utility-page-title">
          <div>
            <h1 id="about-title">О программе</h1>
            <p>Platform Installer V2</p>
          </div>
        </header>
        <section className="utility-card">
          <h2>Сведения о программе</h2>
          <dl className="about-details">
            <dt>Продукт</dt>
            <dd>Platform Installer V2</dd>
            <dt>Интерфейс</dt>
            <dd>Wails · React</dd>
            <dt>Схема конфигурации приложения</dt>
            <dd>
              {configVersion === undefined ? "Недоступна" : `v${configVersion}`}
            </dd>
            <dt>Типы серверов</dt>
            <dd>
              {serverTypes.length
                ? serverTypes.map((item) => item.displayName).join(", ")
                : "Недоступны"}
            </dd>
          </dl>
          {configError && <p role="status">{configError}</p>}
        </section>
      </section>
    );

  if (page === "settings")
    return (
      <section className="utility-page" aria-labelledby="settings-title">
        <header className="utility-page-title">
          <div>
            <h1 id="settings-title">Настройки</h1>
            <p>
              Локальная конфигурация приложения и сведения о хранении данных.
            </p>
          </div>
        </header>
        <section className="utility-card">
          <h2>Конфигурация приложения</h2>
          {configError ? (
            <p role="status">{configError}</p>
          ) : (
            <>
              <p>
                Версия схемы:{" "}
                {configVersion === undefined
                  ? "загрузка…"
                  : `v${configVersion}`}
              </p>
              <p>
                Типы серверов:{" "}
                {serverTypes.length
                  ? serverTypes.map((item) => item.displayName).join(", ")
                  : "не заданы"}
              </p>
            </>
          )}
          <p>
            Учётные данные сеанса и секреты не сохраняются в настройках
            приложения.
          </p>
        </section>
      </section>
    );

  return null;
}
