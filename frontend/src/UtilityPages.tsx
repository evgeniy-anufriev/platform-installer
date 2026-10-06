import type { InstallationEventView } from "./backend";
import "./utility-pages.css";

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
        {events.length === 0 ? (
          <section className="utility-card">
            <h2>Событий пока нет</h2>
            <p>События появятся здесь после запуска плана. Секретные значения не отображаются.</p>
          </section>
        ) : (
          <ol className="event-log" aria-label="События выполнения">
            {events.map((event) => (
              <li key={`${event.runId}-${event.sequence}`}>
                <time dateTime={event.timestamp}>{event.timestamp}</time>
                <strong>{event.eventType} · {event.status}</strong>
                <span>{event.safeMessage}</span>
                {(event.serviceDeployment || event.host) && (
                  <small>
                    {[event.serviceDeployment, event.host].filter(Boolean).join(" · ")}
                  </small>
                )}
              </li>
            ))}
          </ol>
        )}
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
            Проект закреплён за конкретным набором установки и каталогом описаний
            сервисов. Если подходящего проверенного набора нет в локальном кэше,
            сохранённые настройки остаются в проекте, но редактирование параметров
            сервисов отключается. Это не удаляет настройки.
          </p>
        </section>
        <section className="utility-card">
          <h2>Как обновить привязку существующего проекта?</h2>
          <ol>
            <li>Сохраните резервную копию проекта через «Экспортировать проект».</li>
            <li>Получите проверенный неизменяемый набор установки от поставщика и скопируйте его целиком в папку bundle внутри проекта.</li>
            <li>
              На странице «Проект» нажмите «Проверить новый набор», сравните
              версии и digest, затем нажмите «Привязать». Обнаружение набора
              само по себе проект не изменяет.
            </li>
            <li>
              Откройте проект заново и проверьте его через Core. Перед установкой
              сформируйте и одобрите свежий план.
            </li>
          </ol>
          <p>
            Инсталлятор проверяет старую ревизию проекта и новый набор.
            Если каталог не менялся, обновляется только привязка к набору;
            если менялся — атомарно обновляется пара «набор + каталог».
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
            <dt>Продукт</dt><dd>Platform Installer V2</dd>
            <dt>Интерфейс</dt><dd>Wails · React</dd>
            <dt>Схема конфигурации приложения</dt>
            <dd>{configVersion === undefined ? "Недоступна" : `v${configVersion}`}</dd>
            <dt>Типы серверов</dt>
            <dd>{serverTypes.length ? serverTypes.map((item) => item.displayName).join(", ") : "Недоступны"}</dd>
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
            <p>Локальная конфигурация приложения и сведения о хранении данных.</p>
          </div>
        </header>
        <section className="utility-card">
          <h2>Конфигурация приложения</h2>
          {configError ? (
            <p role="status">{configError}</p>
          ) : (
            <>
              <p>Версия схемы: {configVersion === undefined ? "загрузка…" : `v${configVersion}`}</p>
              <p>Типы серверов: {serverTypes.length ? serverTypes.map((item) => item.displayName).join(", ") : "не заданы"}</p>
            </>
          )}
          <p>Учётные данные сеанса и секреты не сохраняются в настройках приложения.</p>
        </section>
      </section>
    );

  return null;
}
