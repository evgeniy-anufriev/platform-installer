import { useState } from "react";
import type { InstallationEventView, InstallationPlanOperation, InstallationRunOperation, InstallationState, SessionCredentialStatus } from "./backend";

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
  plan,
  busy,
  onCreatePlan,
  onApprovePlan,
  run,
  events = [],
  onStart = () => {},
  onCancel = () => {},
  credentialStatus = null,
  onSetPKIStorePassword = async () => { throw new Error("PKI_STORE_PASSWORD_UNAVAILABLE"); },
}: {
  state?: InstallationState;
  tab: InstallationTab;
  onTabChange: (tab: InstallationTab) => void;
  onOpenServers: () => void;
  plan?: InstallationPlanOperation;
  busy: boolean;
  onCreatePlan: () => void;
  onApprovePlan: (planId: string, acknowledgements: string[]) => void;
  run?: InstallationRunOperation;
  events?: InstallationEventView[];
  onStart?: (planId: string) => void;
  onCancel?: (runId: string) => void;
  credentialStatus?: SessionCredentialStatus | null;
  onSetPKIStorePassword?: (value: string) => Promise<SessionCredentialStatus>;
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
              <>
                <p>Предпосылки для свежего плана выполнены. Проверка проекта не заменяет свежий DeploymentPlan.</p>
                <button onClick={onCreatePlan} disabled={busy}>Сформировать свежий план</button>
              </>
            ) : (
              <ul className="safe-findings">
                {prerequisites.map((item) => <li key={item.code}><code>{item.code}</code> {item.safeMessage}</li>)}
              </ul>
            )}
          </article>
        </>
      )}
      {tab === "plan" && <PlanStage operation={plan} busy={busy} onCreatePlan={onCreatePlan} onApprovePlan={onApprovePlan} onStart={onStart} credentialStatus={credentialStatus} onSetPKIStorePassword={onSetPKIStorePassword} />}
      {tab === "execution" && <ExecutionStage run={run} events={events} busy={busy} onCancel={onCancel} />}
      {tab === "result" && <ResultStage run={run} events={events} />}
    </section>
  );
}

function PlanStage({
  operation,
  busy,
  onCreatePlan,
  onApprovePlan,
  onStart,
  credentialStatus,
  onSetPKIStorePassword,
}: {
  operation?: InstallationPlanOperation;
  busy: boolean;
  onCreatePlan: () => void;
  onApprovePlan: (planId: string, acknowledgements: string[]) => void;
  onStart: (planId: string) => void;
  credentialStatus: SessionCredentialStatus | null;
  onSetPKIStorePassword: (value: string) => Promise<SessionCredentialStatus>;
}) {
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const plan = operation?.plan;
  if (!plan) {
    return <article className="card installation-empty"><h2>План</h2><p>{operation?.error?.message || "Свежий план ещё не создан."}</p><button onClick={onCreatePlan} disabled={busy}>Сформировать свежий план</button></article>;
  }
  const requiredCodes = plan.acknowledgements.map((item) => item.code);
  const canApprove = plan.status === "EXECUTABLE" && !plan.approved && requiredCodes.every((code) => acknowledged.includes(code));
  return (
    <section>
      <article className="card">
        <h2>Свежий DeploymentPlan</h2>
        <dl>
          <dt>Статус</dt><dd>{operation.status}</dd>
          <dt>Ревизия проекта</dt><dd>{plan.projectRevision}</dd>
          <dt>Execution Node</dt><dd>{plan.executionNodeId}</dd>
          <dt>Истекает</dt><dd>{plan.expiresAt}</dd>
        </dl>
      </article>
      {plan.findings && plan.findings.length > 0 && <article className="card"><h2>Findings</h2><ul className="safe-findings">{plan.findings.map((item) => <li key={item.code}><code>{item.code}</code> {item.safeMessage}</li>)}</ul></article>}
      <article className="card"><h2>Этапы плана</h2>{plan.phases.map((phase) => <section className="plan-phase" key={phase.id}><h3>{phase.order + 1}. {phase.id}</h3>{phase.actions.map((action) => <div className="plan-action-row" key={action.id}><b>{action.summary}</b><span>{action.targets.join(", ") || "без target hosts"}</span><small>{action.mutating ? "изменяет инфраструктуру" : "проверка"}{action.dependsOn.length ? ` · после ${action.dependsOn.join(", ")}` : ""}</small></div>)}</section>)}</article>
      {plan.status === "EXECUTABLE" && !plan.approved && <article className="card"><h2>Подтверждение</h2>{plan.acknowledgements.map((item) => <label className="acknowledgement" key={item.code}><input type="checkbox" checked={acknowledged.includes(item.code)} onChange={(event) => setAcknowledged((current) => event.target.checked ? [...current, item.code] : current.filter((code) => code !== item.code))} /> <span><b>{item.code}</b><br />{item.summary}</span></label>)}<p><button onClick={() => onApprovePlan(plan.id, requiredCodes)} disabled={busy || !canApprove}>Одобрить план</button></p></article>}
      {plan.approved && <StartApproval plan={plan} busy={busy} onStart={onStart} credentialStatus={credentialStatus} onSetPKIStorePassword={onSetPKIStorePassword} />}
    </section>
  );
}

function StartApproval({ plan, busy, onStart, credentialStatus, onSetPKIStorePassword }: { plan: NonNullable<InstallationPlanOperation["plan"]>; busy: boolean; onStart: (planId: string) => void; credentialStatus: SessionCredentialStatus | null; onSetPKIStorePassword: (value: string) => Promise<SessionCredentialStatus> }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const required = plan.pkiStorePasswordRequired;
  const present = credentialStatus?.pkiStorePasswordStatus === "PRESENT";
  const save = async () => {
    setError("");
    try {
      await onSetPKIStorePassword(password);
      setPassword("");
    } catch (reason) {
      setError(typeof reason === "string" ? reason : "PKI_STORE_PASSWORD_UNAVAILABLE");
    }
  };
  return <article className="card"><h2>План одобрен</h2><p>Запуск создаёт один авторитетный run на выбранном Execution Node.</p>{required && !present && <><p className="muted">Для этого плана требуется пароль хранилища PKI. Он хранится только в памяти сеанса.</p><label>Пароль хранилища PKI<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} disabled={busy} autoComplete="off" /></label><p><button type="button" onClick={save} disabled={busy || password.length === 0}>Добавить пароль в сеанс</button></p>{error && <p className="field-error" role="alert">{error}</p>}</>}{required && present && <p className="muted">Пароль хранилища PKI доступен только для этого сеанса.</p>}<button onClick={() => onStart(plan.id)} disabled={busy || (required && !present)}>Начать выполнение</button></article>;
}

function ExecutionStage({ run, events, busy, onCancel }: { run?: InstallationRunOperation; events: InstallationEventView[]; busy: boolean; onCancel: (runId: string) => void }) {
  if (!run?.run) return <article className="card installation-empty"><h2>Выполнение</h2><p>В этом сеансе запуск ещё не начат.</p></article>;
  return <section><article className="card"><h2>Выполнение</h2><dl><dt>Run</dt><dd>{run.run.runId}</dd><dt>Состояние</dt><dd>{run.run.state}</dd></dl>{["STARTING","RUNNING","CANCELLING"].includes(run.run.state) && <button className="outline" disabled={busy} onClick={() => onCancel(run.run!.runId)}>Отменить выполнение</button>}</article><EventList events={events} /></section>;
}
function ResultStage({ run, events }: { run?: InstallationRunOperation; events: InstallationEventView[] }) { return <section><article className="card"><h2>Результат</h2><p>{run?.run ? `Последний известный статус: ${run.run.state}` : "Нет запуска в текущем сеансе."}</p></article><EventList events={events} /></section>; }
function EventList({ events }: { events: InstallationEventView[] }) { return <article className="card"><h2>Ход выполнения</h2>{events.length === 0 ? <p>События ещё не получены.</p> : <ul className="safe-findings">{events.map((event) => <li key={event.sequence}><code>{event.sequence}</code> {event.safeMessage || event.eventType}{event.host ? ` · ${event.host}` : ""}</li>)}</ul>}</article>; }
