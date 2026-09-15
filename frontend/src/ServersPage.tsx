import { useEffect, useState } from "react";
import type {
  ExecutionNodeContext,
  ExecutionNodePreparation,
  ExecutionNodeReadiness,
  OpenResult,
  SessionCredentialInput,
  SessionCredentialStatus,
} from "./backend";

export type ServerIntent = Record<string, unknown> & {
  operation: "CreateServer" | "UpdateServer" | "DeleteServer";
  hostId: string;
};
type Row = {
  hostId: string;
  type: string;
  desiredHostname: string;
  address: string;
  port: number;
  state?: "new" | "changed" | "deleting";
};
type Dialog =
  | { mode: "add" }
  | { mode: "edit"; row: Row }
  | { mode: "delete"; row: Row }
  | null;
type ServerType = { id: string; displayName: string };

function rows(
  snapshot: OpenResult["snapshot"],
  managed: OpenResult["managed"],
  intents: ServerIntent[],
): Row[] {
  const result = new Map<string, Row>();
  for (const [hostId, host] of Object.entries(managed?.servers || {})) {
    result.set(hostId, {
      hostId,
      type: String(host.type || ""),
      desiredHostname: String(host.desiredHostname || ""),
      address: String(host.address || ""),
      port: Number(host.sshPort || 22),
    });
  }
  for (const [hostId, raw] of Object.entries(snapshot?.hosts || {})) {
    if (result.has(hostId)) continue;
    const host = raw as Record<string, unknown>;
    result.set(hostId, {
      hostId,
      type: String(host.type || ""),
      desiredHostname: String(host.desiredHostname || ""),
      address: String(host.ansibleHost || ""),
      port: Number(host.ansiblePort || 22),
    });
  }
  for (const intent of intents) {
    const existing = result.get(intent.hostId);
    if (intent.operation === "CreateServer")
      result.set(intent.hostId, {
        hostId: intent.hostId,
        type: String(intent.type || ""),
        desiredHostname: String(intent.desiredHostname || ""),
        address: String(intent.address || ""),
        port: typeof intent.sshPort === "number" ? intent.sshPort : 22,
        state: "new",
      });
    else if (intent.operation === "UpdateServer" && existing)
      result.set(intent.hostId, {
        ...existing,
        type: intent.type === undefined ? existing.type : String(intent.type),
        desiredHostname:
          intent.desiredHostname === undefined
            ? existing.desiredHostname
            : String(intent.desiredHostname),
        address:
          intent.address === undefined
            ? existing.address
            : String(intent.address),
        port:
          typeof intent.sshPort === "number" ? intent.sshPort : existing.port,
        state: "changed",
      });
    else if (intent.operation === "DeleteServer" && existing)
      result.set(intent.hostId, { ...existing, state: "deleting" });
  }
  return [...result.values()].sort((a, b) => a.hostId.localeCompare(b.hostId));
}

export function ServersPage({
  snapshot,
  managed,
  empty,
  intents,
  serverTypes,
  configError,
  busy,
  onAppend,
  onReview,
  onDiscard,
  commandCount,
  credentialStatus,
  onSetCredential,
  onClearCredential,
  executionNode,
  onSelectExecutionNode,
  onCheckExecutionNode,
  onPlanExecutionNodePreparation,
  onPrepareExecutionNode,
}: {
  snapshot: OpenResult["snapshot"];
  managed: OpenResult["managed"];
  empty: boolean;
  intents: ServerIntent[];
  serverTypes: ServerType[];
  configError: string | null;
  busy: boolean;
  onAppend: (intent: ServerIntent) => Promise<boolean>;
  onReview: () => void;
  onDiscard: () => void;
  commandCount: number;
  credentialStatus: SessionCredentialStatus | null;
  onSetCredential: (
    input: SessionCredentialInput,
  ) => Promise<SessionCredentialStatus>;
  onClearCredential: () => Promise<SessionCredentialStatus>;
  executionNode: ExecutionNodeContext | null;
  onSelectExecutionNode: (hostId: string) => Promise<ExecutionNodeContext>;
  onCheckExecutionNode: () => Promise<ExecutionNodeReadiness>;
  onPlanExecutionNodePreparation: () => Promise<ExecutionNodePreparation>;
  onPrepareExecutionNode: (planId: string) => Promise<ExecutionNodePreparation>;
}) {
  const [dialog, setDialog] = useState<Dialog>(null);
  const visible = rows(snapshot, managed, intents);
  const firstSave = empty;
  return (
    <>
      <section className="title servers-title">
        <div>
          <h1>Серверы</h1>
          <p>Желаемая конфигурация серверов проекта.</p>
        </div>
        <button
          onClick={() => setDialog({ mode: "add" })}
          disabled={busy || !!configError}
        >
          Добавить сервер
        </button>
      </section>
      {configError && (
        <section className="field-error card" role="alert">
          {configError} Создание сервера и изменение типа недоступны.
        </section>
      )}
      <SessionCredentialsPanel
        status={credentialStatus}
        disabled={busy}
        onSet={onSetCredential}
        onClear={onClearCredential}
      />
      <div className="servers-layout">
        {visible.length === 0 ? (
          <section className="card empty server-list-scroll">
            <h2>Серверов пока нет</h2>
            <p>
              Добавление сервера создаёт typed intent. Файлы появятся только
              после проверки и общего сохранения.
            </p>
            <button
              onClick={() => setDialog({ mode: "add" })}
              disabled={busy || !!configError}
            >
              Добавить первый сервер
            </button>
          </section>
        ) : (
          <section className="card server-table server-list-scroll">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Тип</th>
                  <th>Желаемое имя</th>
                  <th>Адрес</th>
                  <th>SSH</th>
                  <th>Состояние</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => {
                  const created = row.state === "new";
                  const disableCrud =
                    busy || row.state === "deleting" || (firstSave && created);
                  return (
                    <tr
                      key={row.hostId}
                      className={row.state ? `draft-${row.state}` : ""}
                    >
                      <td>
                        <b>{row.hostId}</b>
                      </td>
                      <td>{labelType(row.type, serverTypes)}</td>
                      <td>{row.desiredHostname || <em>Не задано</em>}</td>
                      <td>{row.address}</td>
                      <td>{row.port}</td>
                      <td>
                        {row.state === "new"
                          ? "Новый"
                          : row.state === "changed"
                            ? "Изменён"
                            : row.state === "deleting"
                              ? "Будет удалён"
                              : "Сохранён"}
                      </td>
                      <td>
                        {firstSave && created ? (
                          <small>Доступно после первого сохранения</small>
                        ) : (
                          <>
                            <button
                              className="link"
                              onClick={() => setDialog({ mode: "edit", row })}
                              disabled={disableCrud}
                            >
                              Изменить
                            </button>
                            {" · "}
                            <button
                              className="link danger"
                              onClick={() => setDialog({ mode: "delete", row })}
                              disabled={disableCrud}
                            >
                              Удалить
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        )}
        <ExecutionNodePanel
          context={executionNode}
          rows={visible.filter((row) => row.state !== "deleting")}
          disabled={busy}
          onSelect={onSelectExecutionNode}
          onCheck={onCheckExecutionNode}
          onPlan={onPlanExecutionNodePreparation}
          onPrepare={onPrepareExecutionNode}
        />
      </div>
      {commandCount > 0 && (
        <section className="card draft-actions">
          <p>
            Черновик: {commandCount}. Перед сохранением будет показан локальный
            structural preview затрагиваемых документов.
          </p>
          <button className="outline" onClick={onDiscard} disabled={busy}>
            Отменить все изменения
          </button>
          <button onClick={onReview} disabled={busy}>
            Просмотреть изменения
          </button>
        </section>
      )}
      {dialog?.mode === "add" && (
        <ServerDialog
          mode="add"
          serverTypes={serverTypes}
          configError={configError}
          busy={busy}
          onClose={() => setDialog(null)}
          onAppend={async (intent) => {
            const ok = await onAppend(intent);
            if (ok) setDialog(null);
            return ok;
          }}
        />
      )}
      {dialog?.mode === "edit" && (
        <ServerDialog
          mode="edit"
          row={dialog.row}
          serverTypes={serverTypes}
          configError={configError}
          busy={busy}
          onClose={() => setDialog(null)}
          onAppend={async (intent) => {
            const ok = await onAppend(intent);
            if (ok) setDialog(null);
            return ok;
          }}
        />
      )}
      {dialog?.mode === "delete" && (
        <DeleteDialog
          row={dialog.row}
          busy={busy}
          onClose={() => setDialog(null)}
          onAppend={async (intent) => {
            const ok = await onAppend(intent);
            if (ok) setDialog(null);
            return ok;
          }}
        />
      )}
    </>
  );
}

function ExecutionNodePanel({
  context,
  rows,
  disabled,
  onSelect,
  onCheck,
  onPlan,
  onPrepare,
}: {
  context: ExecutionNodeContext | null;
  rows: Row[];
  disabled: boolean;
  onSelect: (hostId: string) => Promise<ExecutionNodeContext>;
  onCheck: () => Promise<ExecutionNodeReadiness>;
  onPlan: () => Promise<ExecutionNodePreparation>;
  onPrepare: (planId: string) => Promise<ExecutionNodePreparation>;
}) {
  const [changing, setChanging] = useState(false);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [readiness, setReadiness] = useState<ExecutionNodeReadiness | null>(null);
  const [preparation, setPreparation] = useState<ExecutionNodePreparation | null>(null);
  const effective: Partial<ExecutionNodeContext> & {
    status: string;
    selectionSource: string;
  } = context || {
    status: "NOT_CONFIGURED",
    selectionSource: "NONE",
  };
  const choose = async () => {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await onSelect(selected);
      setChanging(false);
    } catch (reason) {
      setError(
        typeof reason === "string"
          ? reason
          : "EXECUTION_NODE_SELECTION_UNAVAILABLE",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <section
      className="card execution-node-panel"
      aria-labelledby="execution-node-heading"
    >
      <div className="execution-node-heading">
        <h2 id="execution-node-heading">Execution Node</h2>
        <span className="readonly">{effective.status}</span>
      </div>
      <div className="execution-node-detail">
        <span>Выбранный узел</span>
        <b>{effective.safeLabel || "Не выбран"}</b>
        <span>Источник выбора</span>
        <b>{effective.selectionSource}</b>
      </div>
      <p className="muted">
        Выбор хранится только в приложении и не записывается в проект. Проверка
        не изменяет узел. Подготовка выполняется только после подтверждения.
      </p>
      {readiness && (
        <p className={readiness.error ? "field-error" : "muted"} role={readiness.error ? "alert" : undefined}>
          Проверка: <b>{readiness.status}</b>
          {readiness.error ? ` · ${readiness.error.message}` : ""}
        </p>
      )}
      {preparation && (
        <p className={preparation.error ? "field-error" : "muted"} role={preparation.error ? "alert" : undefined}>
          Подготовка: <b>{preparation.status}</b>
          {preparation.verification ? ` · Проверка проекта: ${preparation.verification.status}` : ""}
          {preparation.error ? ` · ${preparation.error.message}` : ""}
        </p>
      )}
      <div className="actions">
        <button
          className="outline"
          onClick={async () => {
            setBusy(true); setError("");
            try { setReadiness(await onCheck()); } catch { setError("EXECUTION_NODE_CHECK_UNAVAILABLE"); }
            finally { setBusy(false); }
          }}
          disabled={disabled || busy}
        >
          Проверить узел
        </button>
        <button
          className="outline"
          onClick={async () => {
            setBusy(true); setError("");
            try { setPreparation(await onPlan()); } catch { setError("EXECUTION_NODE_PREPARATION_UNAVAILABLE"); }
            finally { setBusy(false); }
          }}
          disabled={disabled || busy}
        >
          Спланировать подготовку
        </button>
        {preparation?.status === "CONFIRMATION_REQUIRED" && preparation.planId && (
          <button
            onClick={async () => {
              const planId = preparation.planId;
              if (!planId) return;
              if (!window.confirm("Подготовить выбранный Execution Node? Это может активировать проверенный runtime.")) return;
              setBusy(true); setError("");
              try { setPreparation(await onPrepare(planId)); } catch { setError("EXECUTION_NODE_PREPARATION_UNAVAILABLE"); }
              finally { setBusy(false); }
            }}
            disabled={disabled || busy}
          >
            Подтвердить подготовку
          </button>
        )}
      </div>
      {!changing ? (
        <button
          className="outline"
          aria-label="Выбрать Execution Node"
          onClick={() => {
            setSelected(context?.selectedHostId || rows[0]?.hostId || "");
            setChanging(true);
          }}
          disabled={disabled || rows.length === 0}
        >
          Выбрать Execution Node
        </button>
      ) : (
        <div className="execution-node-change">
          <label>
            Сервер проекта
            <select
              aria-label="Сервер проекта для Execution Node"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
              disabled={busy || disabled}
            >
              {rows.map((row) => (
                <option key={row.hostId} value={row.hostId}>
                  {row.hostId} · {row.address}
                </option>
              ))}
            </select>
          </label>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          <div className="actions">
            <button
              className="outline"
              onClick={() => setChanging(false)}
              disabled={busy}
            >
              Отмена
            </button>
            <button onClick={choose} disabled={busy || disabled || !selected}>
              Выбрать
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function SessionCredentialsPanel({
  status,
  disabled,
  onSet,
  onClear,
}: {
  status: SessionCredentialStatus | null;
  disabled: boolean;
  onSet: (input: SessionCredentialInput) => Promise<SessionCredentialStatus>;
  onClear: () => Promise<SessionCredentialStatus>;
}) {
  const [username, setUsername] = useState("");
  const [sshMode, setSSHMode] = useState<"SSH_PASSWORD" | "SSH_PRIVATE_KEY">(
    "SSH_PASSWORD",
  );
  const [sshPassword, setSSHPassword] = useState("");
  const [privateKeyPath, setPrivateKeyPath] = useState("");
  const [sudoEnabled, setSudoEnabled] = useState(false);
  const [sudoPassword, setSudoPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const clearDraft = () => {
    setSSHPassword("");
    setPrivateKeyPath("");
    setSudoPassword("");
  };
  useEffect(() => () => clearDraft(), []);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSet({
        username,
        sshMode,
        sshPassword: sshMode === "SSH_PASSWORD" ? sshPassword : "",
        privateKeyPath: sshMode === "SSH_PRIVATE_KEY" ? privateKeyPath : "",
        elevationMode: sudoEnabled ? "SUDO_PASSWORD" : "NONE",
        elevationPassword: sudoEnabled ? sudoPassword : "",
      });
      clearDraft();
    } catch (reason) {
      setError(
        typeof reason === "string" ? reason : "SESSION_CREDENTIAL_UNAVAILABLE",
      );
    } finally {
      setBusy(false);
    }
  };
  const effectiveStatus = status?.status || "MISSING";
  return (
    <section className="card session-credentials">
      <div>
        <h2>Учётные данные сеанса</h2>
        <p className="muted">
          Применяются ко всем серверам только в текущем сеансе и не записываются
          в проект.
        </p>
      </div>
      <form onSubmit={submit}>
        <label>
          Технический пользователь
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            disabled={busy || disabled}
          />
        </label>
        <label>
          SSH-аутентификация
          <select
            value={sshMode}
            onChange={(event) =>
              setSSHMode(
                event.target.value as "SSH_PASSWORD" | "SSH_PRIVATE_KEY",
              )
            }
            disabled={busy || disabled}
          >
            <option value="SSH_PASSWORD">Пароль</option>
            <option value="SSH_PRIVATE_KEY">Приватный ключ PEM</option>
          </select>
        </label>
        {sshMode === "SSH_PASSWORD" ? (
          <label>
            SSH-пароль
            <input
              type="password"
              value={sshPassword}
              onChange={(event) => setSSHPassword(event.target.value)}
              required
              disabled={busy || disabled}
              autoComplete="off"
            />
          </label>
        ) : (
          <label>
            Абсолютный путь к приватному ключу
            <input
              value={privateKeyPath}
              onChange={(event) => setPrivateKeyPath(event.target.value)}
              required
              disabled={busy || disabled}
              autoComplete="off"
            />
          </label>
        )}
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={sudoEnabled}
            onChange={(event) => setSudoEnabled(event.target.checked)}
            disabled={busy || disabled}
          />{" "}
          Требуется пароль sudo
        </label>
        {sudoEnabled && (
          <label>
            Пароль sudo
            <input
              type="password"
              value={sudoPassword}
              onChange={(event) => setSudoPassword(event.target.value)}
              required
              disabled={busy || disabled}
              autoComplete="off"
            />
          </label>
        )}
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <div className="actions">
          <button type="submit" disabled={busy || disabled}>
            Сохранить в сеансе
          </button>
          <button
            type="button"
            className="outline"
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                await onClear();
                clearDraft();
              } catch (reason) {
                setError(
                  typeof reason === "string"
                    ? reason
                    : "SESSION_CREDENTIAL_UNAVAILABLE",
                );
              } finally {
                setBusy(false);
              }
            }}
            disabled={busy || disabled}
          >
            Очистить
          </button>
        </div>
      </form>
      <p className="muted" aria-live="polite">
        {effectiveStatus === "PRESENT"
          ? `Доступны до ${status?.expiresAt || ""}`
          : effectiveStatus === "EXPIRED"
            ? "Срок хранения учётных данных истёк"
            : "Учётные данные не заданы"}
      </p>
    </section>
  );
}
function labelType(value: string, types: ServerType[]) {
  const found = types.find((item) => item.id === value);
  return found
    ? `${found.displayName} (${value})`
    : value
      ? `Неизвестный тип (${value})`
      : "Не задан";
}
function ServerDialog({
  mode,
  row,
  serverTypes,
  configError,
  busy,
  onClose,
  onAppend,
}: {
  mode: "add" | "edit";
  row?: Row;
  serverTypes: ServerType[];
  configError: string | null;
  busy: boolean;
  onClose: () => void;
  onAppend: (intent: ServerIntent) => Promise<boolean>;
}) {
  const [hostId, setHostId] = useState(row?.hostId || "");
  const [type, setType] = useState(row?.type || "");
  const [desiredHostname, setDesiredHostname] = useState(
    row?.desiredHostname || "",
  );
  const [address, setAddress] = useState(row?.address || "");
  const [portMode, setPortMode] = useState<
    "inherit" | "explicit" | "unchanged" | "clear"
  >(mode === "add" ? "inherit" : "unchanged");
  const [port, setPort] = useState(row?.port ? String(row.port) : "");
  const [error, setError] = useState("");
  const unknownCurrentType =
    mode === "edit" &&
    type !== "" &&
    !serverTypes.some((serverType) => serverType.id === type);
  useEffect(() => {
    const close = (event: KeyboardEvent) =>
      event.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [busy, onClose]);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const numericPort = Number(port);
    if (
      !hostId ||
      !address ||
      !desiredHostname ||
      (mode === "add" && (!type || configError)) ||
      (mode === "edit" && !type && !!configError) ||
      (portMode === "explicit" &&
        (!Number.isInteger(numericPort) ||
          numericPort < 1 ||
          numericPort > 65535))
    ) {
      setError(
        mode === "edit" && !type && configError
          ? "Для сервера без типа требуется доступная конфигурация приложения."
          : "Заполните обязательные поля и корректный SSH-порт.",
      );
      return;
    }
    if (mode === "add") {
      const intent: ServerIntent = {
        operation: "CreateServer",
        hostId,
        type,
        desiredHostname,
        address,
      };
      if (portMode === "explicit") intent.sshPort = numericPort;
      await onAppend(intent);
      return;
    }
    const intent: ServerIntent = { operation: "UpdateServer", hostId };
    if (type !== row?.type) intent.type = type;
    if (desiredHostname !== row?.desiredHostname)
      intent.desiredHostname = desiredHostname;
    if (address !== row?.address) intent.address = address;
    if (portMode === "explicit") intent.sshPort = numericPort;
    if (portMode === "clear") intent.clearSSHPort = true;
    if (Object.keys(intent).length === 2) {
      onClose();
      return;
    }
    await onAppend(intent);
  };
  const typeDisabled = !!configError || (mode === "edit" && !!configError);
  return (
    <div className="modal" role="presentation">
      <form
        className="card dialog server-dialog"
        onSubmit={submit}
        role="dialog"
        aria-modal="true"
        aria-labelledby="server-title"
      >
        <h1 id="server-title">
          {mode === "add" ? "Добавить сервер" : "Изменить сервер"}
        </h1>
        <label>
          ID сервера
          <input
            value={hostId}
            onChange={(event) => setHostId(event.target.value)}
            readOnly={mode === "edit"}
            required
            autoFocus
          />
        </label>
        <label>
          Тип сервера
          {configError && mode === "edit" ? (
            <input value={type || "Не задан"} readOnly />
          ) : (
            <select
              value={type}
              onChange={(event) => setType(event.target.value)}
              disabled={typeDisabled}
              required={mode === "add" || !type}
            >
              <option value="">Выберите тип</option>
              {unknownCurrentType && (
                <option value={type}>Неизвестный тип ({type})</option>
              )}
              {serverTypes.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.displayName} ({item.id})
                </option>
              ))}
            </select>
          )}
        </label>
        <label>
          Желаемое имя хоста
          <input
            value={desiredHostname}
            onChange={(event) => setDesiredHostname(event.target.value)}
            required
          />
        </label>
        <label>
          IP-адрес / DNS-имя
          <input
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            required
          />
        </label>
        <label>
          SSH-порт
          <select
            value={portMode}
            onChange={(event) =>
              setPortMode(event.target.value as typeof portMode)
            }
          >
            <option value="inherit">Использовать inherited/default</option>
            {mode === "edit" && <option value="unchanged">Не изменять</option>}
            <option value="explicit">Задать явно</option>
            {mode === "edit" && (
              <option value="clear">Убрать Installer override</option>
            )}
          </select>
        </label>
        {portMode === "explicit" && (
          <label>
            Явный SSH-порт
            <input
              type="number"
              min="1"
              max="65535"
              value={port}
              onChange={(event) => setPort(event.target.value)}
              required
            />
          </label>
        )}
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <p className="muted">
          Сохранить изменение в черновик. Файлы проекта будут изменены только
          после локального просмотра и общего сохранения проекта.
        </p>
        <div className="actions">
          <button
            type="button"
            className="outline"
            onClick={onClose}
            disabled={busy}
          >
            Отмена
          </button>
          <button
            type="submit"
            disabled={busy || (mode === "add" && !!configError)}
            title="Сохранить изменение в черновик. Файлы проекта будут изменены только после локального просмотра и общего сохранения проекта."
          >
            Сохранить
          </button>
        </div>
      </form>
    </div>
  );
}
function DeleteDialog({
  row,
  busy,
  onClose,
  onAppend,
}: {
  row: Row;
  busy: boolean;
  onClose: () => void;
  onAppend: (intent: ServerIntent) => Promise<boolean>;
}) {
  return (
    <div className="modal" role="presentation">
      <section
        className="card dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-title"
      >
        <h1 id="delete-title">Удалить сервер</h1>
        <p>
          Сервер <b>{row.hostId}</b> будет удалён из inventory. Связанные
          сервисы и размещение автоматически не удаляются.
        </p>
        <div className="actions">
          <button
            className="outline"
            autoFocus
            onClick={onClose}
            disabled={busy}
          >
            Отмена
          </button>
          <button
            className="danger-button"
            onClick={async () => {
              if (
                await onAppend({
                  operation: "DeleteServer",
                  hostId: row.hostId,
                })
              )
                onClose();
            }}
            disabled={busy}
          >
            Удалить
          </button>
        </div>
      </section>
    </div>
  );
}
