import { useEffect, useState } from "react";
import type {
  EditResult,
  ExecutionNodeContext,
  OpenResult,
  ProjectBackend,
  SessionCredentialInput,
  SessionCredentialStatus,
} from "./backend";
import { backend } from "./backend";
import { type ServerIntent, ServersPage } from "./ServersPage";
import "./edit.css";

type Page = "project" | "servers";
const navigation: Array<{ id: Page | string; label: string }> = [
  { id: "project", label: "Проект" },
  { id: "servers", label: "Серверы" },
  { id: "topology", label: "Топология" },
  { id: "certificates", label: "Сертификаты" },
  { id: "services", label: "Сервисы" },
  { id: "installation", label: "Установка" },
  { id: "logs", label: "Логи" },
  { id: "help", label: "Справка" },
  { id: "about", label: "О программе" },
  { id: "settings", label: "Настройки" },
];
const count = (value: unknown) =>
  value && typeof value === "object" ? Object.keys(value).length : 0;

export function App({ api = backend }: { api?: ProjectBackend }) {
  const [result, setResult] = useState<OpenResult>({
    status: "NO_PROJECT",
  } as OpenResult);
  const [page, setPage] = useState<Page>("project");
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [projectDialog, setProjectDialog] = useState(false);
  const [name, setName] = useState("");
  const [root, setRoot] = useState("");
  const [parent, setParent] = useState("");
  const [separator, setSeparator] = useState("\\");
  const [nameRequired, setNameRequired] = useState(false);
  const [edit, setEdit] = useState<EditResult | null>(null);
  const [editError, setEditError] = useState<EditResult["error"] | null>(null);
  const [editBusy, setEditBusy] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const [commandCount, setCommandCount] = useState(0);
  const [intents, setIntents] = useState<ServerIntent[]>([]);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [staleSnapshot, setStaleSnapshot] = useState(false);
  const [serverTypes, setServerTypes] = useState<
    Array<{ id: string; displayName: string }>
  >([]);
  const [configError, setConfigError] = useState<string | null>(null);
  const [credentialStatus, setCredentialStatus] =
    useState<SessionCredentialStatus | null>(null);
  const [executionNode, setExecutionNode] =
    useState<ExecutionNodeContext | null>(null);
  const destination = parent ? `${parent}${separator}${name.trim()}` : root;
  const snapshot = result.snapshot;
  const local = result.project;
  const project = snapshot?.project as Record<string, unknown> | undefined;
  const empty =
    result.status === "OPEN" &&
    result.classification === "EMPTY_MANAGED_PROJECT" &&
    local &&
    !snapshot;
  const projectOpen = result.status === "OPEN";
  const stale = projectOpen && staleSnapshot;
  const title = empty
    ? local.name
    : project?.name
      ? String(project.name)
      : local?.name || "Проект не открыт";

  useEffect(() => {
    let live = true;
    api
      .getApplicationConfig()
      .then((value) => {
        if (!live) return;
        if (value.status === "READY" && value.config) {
          setServerTypes(value.config.serverTypes || []);
          setConfigError(null);
        } else {
          setServerTypes([]);
          setConfigError(
            value.error?.message || "Конфигурация типов серверов недоступна.",
          );
        }
      })
      .catch(
        () => live && setConfigError("Конфигурация типов серверов недоступна."),
      );
    return () => {
      live = false;
    };
  }, [api]);

  useEffect(() => {
    let live = true;
    if (!projectOpen) {
      setCredentialStatus(null);
      return () => {
        live = false;
      };
    }
    if (!api.getSessionCredentialStatus)
      return () => {
        live = false;
      };
    api
      .getSessionCredentialStatus()
      .then((value) => live && setCredentialStatus(value))
      .catch(() => live && setCredentialStatus(null));
    return () => {
      live = false;
    };
  }, [api, projectOpen, result.root]);

  useEffect(() => {
    let live = true;
    if (!projectOpen || !api.getExecutionNodeContext) {
      setExecutionNode(null);
      return () => {
        live = false;
      };
    }
    api
      .getExecutionNodeContext()
      .then((value) => live && setExecutionNode(value))
      .catch(() => live && setExecutionNode(null));
    return () => {
      live = false;
    };
  }, [api, projectOpen, result.root, commandCount]);

  const clearDraft = () => {
    setEdit(null);
    setEditError(null);
    setSessionId("");
    setCommandCount(0);
    setIntents([]);
    setReviewOpen(false);
  };
  const open = async () => {
    setLoading(true);
    try {
      const next = await api.chooseProject();
      setResult(next);
      setPage("project");
      setStaleSnapshot(false);
    } finally {
      setLoading(false);
    }
  };
  const chooseParent = async () => {
    const selected = await api.chooseProjectParent();
    if (selected) {
      setParent(selected);
      setSeparator("\\");
    }
  };
  const updateDestination = (value: string) => {
    setParent("");
    setRoot(value);
  };
  const adoptDestinationParent = () => {
    const index = Math.max(root.lastIndexOf("\\"), root.lastIndexOf("/"));
    if (index >= 0) {
      setParent(root.slice(0, index));
      setSeparator(root[index]);
    }
  };
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setNameRequired(true);
      return;
    }
    setCreating(true);
    try {
      const next = await api.createProject({
        projectRoot: destination,
        displayName: name,
        compatibilitySourceId: "default",
      });
      setResult(next);
      setProjectDialog(false);
      setPage("project");
      setStaleSnapshot(false);
      if (next.status === "OPEN") {
        setName("");
        setRoot("");
        setParent("");
        setSeparator("\\");
        setNameRequired(false);
      }
    } finally {
      setCreating(false);
    }
  };
  const close = async () => {
    setResult(await api.closeProject());
    setPage("project");
    setStaleSnapshot(false);
  };

  const appendServerIntent = async (intent: ServerIntent): Promise<boolean> => {
    setEditBusy(true);
    let id = sessionId;
    let created = false;
    try {
      if (!id) {
        const started = await api.startEditSession();
        if (started.error || !started.session?.sessionId) {
          setEdit(started);
          setEditError(
            started.error || {
              code: "EDIT_SESSION_UNAVAILABLE",
              message: "Не удалось начать черновик изменений.",
            },
          );
          return false;
        }
        id = started.session.sessionId;
        created = true;
        setEdit(started);
        setSessionId(id);
      }
      const next = await api.appendEditCommand(id, intent);
      if (next.error || !next.session) {
        if (created) {
          await api.discardEditSession(id);
          clearDraft();
        } else {
          setEdit(next);
          setEditError(
            next.error || {
              code: "EDIT_COMMAND_BLOCKED",
              message: "Изменение не добавлено в черновик.",
            },
          );
        }
        return false;
      }
      setEdit(next);
      setEditError(null);
      setSessionId(id);
      setCommandCount(next.session.commandCount);
      setIntents((current) => [...current, intent]);
      return true;
    } finally {
      setEditBusy(false);
    }
  };
  const review = async () => {
    if (!sessionId || commandCount === 0) return;
    setEditBusy(true);
    setReviewOpen(true);
    try {
      const next = await api.reviewEditSession(sessionId);
      setEdit(next);
      setEditError(next.error || null);
    } finally {
      setEditBusy(false);
    }
  };
  const save = async () => {
    const planId = edit?.plan?.planId;
    if (!sessionId || !planId) return;
    setEditBusy(true);
    try {
      const next = await api.commitEditPlan(sessionId, planId);
      if (next.error) {
        setEdit(next);
        setEditError(next.error);
        return;
      }
      if (next.status === "COMMITTED") {
        setResult(
          (current) =>
            ({
              ...current,
              classification: "MANAGED_PROJECT",
              snapshot: next.commit?.snapshot,
            }) as OpenResult,
        );
        setStaleSnapshot(false);
        clearDraft();
        return;
      }
      if (next.status === "COMMITTED_REFRESH_FAILED") {
        setResult(
          (current) =>
            ({
              ...current,
              classification: "MANAGED_PROJECT",
              snapshot: undefined,
            }) as OpenResult,
        );
        setStaleSnapshot(true);
        clearDraft();
        return;
      }
      setEdit(next);
      setEditError(
        next.commit?.finding
          ? {
              code: next.commit.finding.code,
              message: next.commit.finding.safeMessage,
            }
          : {
              code: "WRITE_FAILED",
              message: "Сохранение изменений заблокировано.",
            },
      );
    } finally {
      setEditBusy(false);
    }
  };
  const discard = async () => {
    if (!sessionId) return;
    setEditBusy(true);
    try {
      await api.discardEditSession(sessionId);
      clearDraft();
    } finally {
      setEditBusy(false);
    }
  };
  const refreshSnapshot = async () => {
    if (!result.root) return;
    setLoading(true);
    try {
      const next = await api.openProject(result.root);
      setResult(next);
      if (next.status === "OPEN" && next.snapshot) setStaleSnapshot(false);
    } finally {
      setLoading(false);
    }
  };
  const setSessionCredential = async (input: SessionCredentialInput) => {
    if (!api.setSessionCredential)
      throw new Error("SESSION_CREDENTIAL_UNAVAILABLE");
    const status = await api.setSessionCredential(input);
    setCredentialStatus(status);
    return status;
  };
  const clearSessionCredential = async () => {
    if (!api.clearSessionCredential)
      throw new Error("SESSION_CREDENTIAL_UNAVAILABLE");
    const status = await api.clearSessionCredential();
    setCredentialStatus(status);
    return status;
  };
  const selectExecutionNode = async (hostId: string) => {
    if (!api.selectExecutionNode)
      throw new Error("EXECUTION_NODE_SELECTION_UNAVAILABLE");
    const context = await api.selectExecutionNode(hostId);
    setExecutionNode(context);
    return context;
  };

  return (
    <div className="shell">
      <aside>
        <div className="brand">
          Platform
          <br />
          <span>Installer</span>
        </div>
        <nav>
          {navigation.map((item) => {
            const enabled =
              item.id === "project" || (item.id === "servers" && projectOpen);
            return (
              <button
                key={item.id}
                className={item.id === page ? "active" : "future"}
                disabled={!enabled}
                onClick={() =>
                  (item.id === "project" || item.id === "servers") &&
                  setPage(item.id)
                }
              >
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>
      <main>
        <header>
          <div>
            <strong>{title}</strong>
            <span>
              {result.root || "Выберите существующий проект или создайте новый"}
            </span>
          </div>
          {sessionId && (
            <div className="unsaved">Есть несохранённые изменения</div>
          )}
          {projectOpen && !sessionId && !stale && (
            <div className="readonly">
              {empty ? "Не настроен" : "Проверено Core"}
            </div>
          )}
          {projectOpen && (
            <button
              className="execution-node-badge"
              aria-label="Открыть Execution Node"
              onClick={() => setPage("servers")}
              title="Открыть Execution Node на странице Серверы"
            >
              Execution Node: {executionNode?.status || "NOT_CONFIGURED"}
              {executionNode?.safeLabel ? ` · ${executionNode.safeLabel}` : ""}
            </button>
          )}
          <button
            className="outline"
            onClick={() => setProjectDialog(true)}
            disabled={loading || creating || !!sessionId}
          >
            Создать проект
          </button>
          <button
            className="outline"
            onClick={open}
            disabled={loading || creating || !!sessionId}
          >
            Открыть проект
          </button>
          {sessionId && commandCount > 0 && (
            <button onClick={review} disabled={editBusy}>
              Просмотреть изменения
            </button>
          )}
        </header>
        <section className="banner">
          Изменения остаются в transient session до проверки полного candidate
          на READY Execution Node и явного сохранения.
        </section>
        {(loading || creating) && (
          <section className="card">
            {creating ? "Безопасное создание проекта…" : "Открытие проекта…"}
          </section>
        )}
        {!loading && !creating && result.status === "NO_PROJECT" && (
          <section className="empty card">
            <h1>Создайте или откройте проект</h1>
            <p>
              Новый проект содержит только metadata и compatibility locks из
              verified local bundle.
            </p>
            <button onClick={() => setProjectDialog(true)}>
              Создать проект
            </button>
            <button className="outline" onClick={open}>
              Открыть папку проекта
            </button>
          </section>
        )}
        {!loading && !creating && result.status === "ERROR" && (
          <section className="error card">
            <h1>Проект не открыт</h1>
            <p>{result.error?.message}</p>
            <code>{result.error?.code}</code>
            <button onClick={() => setProjectDialog(true)}>
              Создать проект
            </button>
            <button className="outline" onClick={open}>
              Открыть другой проект
            </button>
          </section>
        )}
        {!loading && !creating && projectOpen && page === "project" && (
          <ProjectPage
            empty={!!empty}
            snapshot={snapshot}
            local={local}
            onClose={close}
            onServers={() => setPage("servers")}
            closeDisabled={!!sessionId}
          />
        )}
        {!loading && !creating && projectOpen && page === "servers" && (
          <ServersPage
            snapshot={snapshot}
            empty={!!empty}
            stale={stale}
            intents={intents}
            serverTypes={serverTypes}
            configError={configError}
            busy={editBusy}
            onAppend={appendServerIntent}
            onReview={review}
            onDiscard={discard}
            commandCount={commandCount}
            onRefresh={refreshSnapshot}
            credentialStatus={credentialStatus}
            onSetCredential={setSessionCredential}
            onClearCredential={clearSessionCredential}
            executionNode={executionNode}
            onSelectExecutionNode={selectExecutionNode}
          />
        )}
        {projectDialog && (
          <div className="modal" role="presentation">
            <form className="card dialog" onSubmit={create}>
              <h1>Создать проект</h1>
              <label>
                Название проекта
                <input
                  maxLength={256}
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                    setNameRequired(false);
                  }}
                  autoFocus
                  aria-invalid={nameRequired}
                />
              </label>
              {nameRequired && (
                <p className="field-error" role="alert">
                  Заполните «Название проекта»: оно задаёт новую папку проекта.
                </p>
              )}
              <label>
                Новая папка проекта
                <input
                  required
                  value={destination}
                  onChange={(event) => updateDestination(event.target.value)}
                  onBlur={adoptDestinationParent}
                  placeholder="C:\\Projects\\production"
                />
              </label>
              <div className="actions">
                <button
                  type="button"
                  className="outline"
                  onClick={chooseParent}
                >
                  Выбрать parent
                </button>
                <button
                  type="button"
                  className="outline"
                  onClick={() => setProjectDialog(false)}
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={creating || !destination.trim()}
                >
                  Создать проект
                </button>
              </div>
              <p>
                Название проекта всегда задаёт последнюю папку в пути. Будет
                создан только <code>project.yml</code>.
              </p>
            </form>
          </div>
        )}
        {reviewOpen && (
          <ReviewDialog
            edit={edit}
            error={editError}
            busy={editBusy}
            onClose={() => setReviewOpen(false)}
            onReview={review}
            onSave={save}
            onDiscard={discard}
          />
        )}
      </main>
    </div>
  );
}

function ProjectPage({
  empty,
  snapshot,
  local,
  onClose,
  onServers,
  closeDisabled,
}: {
  empty: boolean;
  snapshot: OpenResult["snapshot"];
  local: OpenResult["project"];
  onClose: () => void;
  onServers: () => void;
  closeDisabled: boolean;
}) {
  if (empty && local)
    return (
      <>
        <section className="title">
          <div>
            <h1>Проект ещё не настроен</h1>
            <p>
              Это корректный metadata-only проект. Добавьте серверы, затем
              проверьте и сохраните проект.
            </p>
          </div>
          <button
            className="outline"
            onClick={onClose}
            disabled={closeDisabled}
          >
            Закрыть проект
          </button>
        </section>
        <section className="grid">
          <Stat label="Серверы" value={0} />
          <Stat label="Deployments / Сервисы" value={0} />
          <Stat label="Выполнения" value={0} />
          <Stat label="Inventory" value="Не создан" />
        </section>
        <section className="card">
          <h2>Сведения проекта</h2>
          <dl>
            <dt>Название</dt>
            <dd>{local.name}</dd>
            <dt>Project ID</dt>
            <dd>{local.id}</dd>
            <dt>Compatibility source</dt>
            <dd>{local.source?.bundleDigest}</dd>
          </dl>
          <button onClick={onServers}>Добавить первый сервер</button>
        </section>
      </>
    );
  return (
    <>
      <section className="title">
        <div>
          <h1>
            {(snapshot?.project as Record<string, unknown> | undefined)?.name
              ? String((snapshot?.project as Record<string, unknown>).name)
              : "Проект"}
          </h1>
          <p>Авторитетный снимок Core.</p>
        </div>
        <button className="outline" onClick={onClose} disabled={closeDisabled}>
          Закрыть проект
        </button>
      </section>
      <section className="grid">
        <Stat label="Хосты" value={count(snapshot?.hosts)} />
        <Stat
          label="Развёртывания"
          value={count(snapshot?.serviceDeployments)}
        />
        <Stat label="PKI профили" value={count(snapshot?.pki)} />
        <Stat label="Findings" value={snapshot?.findings?.length ?? 0} />
      </section>
      <section className="card">
        <h2>Состояние проекта</h2>
        <dl>
          <dt>Статус</dt>
          <dd>{snapshot?.status}</dd>
          <dt>Revision</dt>
          <dd>{snapshot?.projectRevision}</dd>
        </dl>
        <button onClick={onServers}>Открыть серверы</button>
      </section>
    </>
  );
}
function ReviewDialog({
  edit,
  error,
  busy,
  onClose,
  onReview,
  onSave,
  onDiscard,
}: {
  edit: EditResult | null;
  error: EditResult["error"] | null;
  busy: boolean;
  onClose: () => void;
  onReview: () => void;
  onSave: () => void;
  onDiscard: () => void;
}) {
  const plan = edit?.plan;
  const findings = plan?.validation?.findings || [];
  return (
    <div className="modal" role="presentation">
      <section
        className="card dialog review-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="review-title"
      >
        <h1 id="review-title">Изменения конфигурации</h1>
        {error && (
          <p className="field-error" role="alert">
            <code>{error.code}</code> {error.message}
          </p>
        )}
        {plan ? (
          <>
            <p>
              Core: {plan.validation?.status}. Документов:{" "}
              {plan.affectedDocuments?.length ?? 0}.
            </p>
            <ul>
              {plan.semanticChanges?.map((change, index) => (
                <li key={index}>{change.safeSummary}</li>
              ))}
            </ul>
            {plan.affectedDocuments && plan.affectedDocuments.length > 0 && (
              <>
                <h2>Затрагиваемые документы</h2>
                <ul>
                  {plan.affectedDocuments.map((document) => (
                    <li key={document.logicalPath}>
                      {document.logicalPath}: {document.before?.state} →{" "}
                      {document.after?.state}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {plan.impacts && plan.impacts.length > 0 && (
              <>
                <h2>Последствия</h2>
                <ul>
                  {plan.impacts.map((impact) => (
                    <li key={impact}>{impact}</li>
                  ))}
                </ul>
              </>
            )}
            <ul>
              {findings.map((finding, index) => (
                <li key={index}>
                  <code>{finding.code}</code> {finding.safeMessage}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p>Проверка черновика ещё не вернула план.</p>
        )}
        <div className="actions">
          <button className="outline" onClick={onClose}>
            Вернуться к редактированию
          </button>
          <button className="outline" onClick={onDiscard} disabled={busy}>
            Отменить все изменения
          </button>
          {plan?.commitAllowed ? (
            <button onClick={onSave} disabled={busy}>
              Сохранить проект
            </button>
          ) : (
            <button onClick={onReview} disabled={busy}>
              Повторить проверку
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <article className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {value === 0 && <small>Нет данных</small>}
    </article>
  );
}
