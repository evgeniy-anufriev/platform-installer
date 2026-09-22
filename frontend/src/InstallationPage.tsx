import type { InstallationState } from "./backend";

type InstallationTab = "summary" | "plan" | "execution" | "result";

const tabLabels: Array<{ id: InstallationTab; label: string }> = [
  { id: "summary", label: "Сводка" },
  { id: "plan", label: "План" },
  { id: "execution", label: "Выполнение" },
  { id: "result", label: "Результат" },
];

const verificationLabel = (status: string) => {
  switch (status) {
    case "VERIFIED":
      return "Проверено";
    case "INVALID":
      return "Ошибки проверки";
    case "STALE":
      return "Проверка устарела";
    case "UNAVAILABLE":
      return "Проверка недоступна";
    default:
      return "Не проверено";
  }
};

export function InstallationPage({
  state,
  tab,
  onTabChange,
  onOpenServers,
}: {
  state?: InstallationState;
  tab: InstallationTab;
  onTabChange: (tab: InstallationTab) => void;
  onOpenServers: () => void;
}) {
  const prerequisites = state?.prerequisites || [];
  const node = state?.executionNode;
  return (
    <section className="installation-page">
      <div className="title">
        <div>
          <h1>Установка</h1>
          <p>Готовность, свежий план и выполнение сохранённой конфигурации.</p>
        </div>
        <span className="readonly">{state?.status || "Состояние загружается"}</span>
      </div>
      <nav className="installation-tabs" aria-label="Разделы установки">
        {tabLabels.map((item) => (
          <button
            key={item.id}
            type="button"
            className={tab === item.id ? "active" : "outline"}
            aria-selected={tab === item.id}
            onClick={() => onTabChange(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div className="workflow-strip" aria-label="Стадии установки">
        <div className={tab === "plan" ? "workflow-current" : ""}>1. План</div>
        <div className={tab === "execution" ? "workflow-current" : ""}>2. Выполнение</div>
        <div className={tab === "result" ? "workflow-current" : ""}>3. Результат</div>
      </div>
      {tab === "summary" && (
        <>
          <article className="card">
            <h2>Execution Node · prerequisite</h2>
            <dl>
              <dt>Состояние</dt><dd>{node?.status || "NOT_CONFIGURED"}</dd>
              <dt>Узел</dt><dd>{node?.safeLabel || "Не выбран"}</dd>
              <dt>Подготовка</dt><dd>Доступна только на странице «Серверы».</dd>
            </dl>
            <p><button className="outline" onClick={onOpenServers}>Открыть Серверы</button></p>
          </article>
          <article className="card">
            <h2>Сохранённый проект</h2>
            {state?.project ? (
              <dl>
                <dt>Ревизия</dt><dd>{state.project.revision}</dd>
                <dt>Проверка</dt><dd>{verificationLabel(state.project.verificationStatus)}</dd>
                <dt>Изменения</dt><dd>{state.project.hasUnsavedChanges ? "Есть несохранённые" : "Сохранено"}</dd>
              </dl>
            ) : <p>Сохранённый проект пока недоступен.</p>}
          </article>
          <article className="card">
            <h2>Следующее действие</h2>
            {state?.status === "READY_TO_PLAN" ? (
              <p>Предпосылки для свежего плана выполнены. Создание плана будет добавлено в UI‑02B.</p>
            ) : (
              <ul className="safe-findings">
                {prerequisites.map((item) => <li key={item.code}><code>{item.code}</code> {item.safeMessage}</li>)}
              </ul>
            )}
          </article>
        </>
      )}
      {tab === "plan" && <ReadOnlyStage title="План" message="Свежий план ещё не создан. UI‑02A отображает только безопасное состояние; создание и одобрение плана появятся в UI‑02B." />}
      {tab === "execution" && <ReadOnlyStage title="Выполнение" message="Нет известного запуска в текущем сеансе. UI‑02A не запускает выполнение и не обращается к целевым серверам." />}
      {tab === "result" && <ReadOnlyStage title="Результат" message="Нет результата для отображения. UI‑02A не хранит историю запусков и не выполняет повторную проверку." />}
    </section>
  );
}

function ReadOnlyStage({ title, message }: { title: string; message: string }) {
  return <article className="card installation-empty"><h2>{title}</h2><p>{message}</p></article>;
}
