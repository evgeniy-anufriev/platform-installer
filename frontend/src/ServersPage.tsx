import { useEffect, useState, type ReactNode } from "react";
import type {
  ExecutionNodeContext,
  ExecutionNodePreparation,
  ExecutionNodeReadiness,
  HostKeyProbeResult,
  ServerInformationResult,
  OpenResult,
  SessionCredentialInput,
  SessionCredentialStatus,
} from "./backend";
import { ServerInformationDialog, ServerInformationText } from "./ServerInformationDialog";
import {
  executionNodeCombinedStatus,
  executionNodeSelectionLabel,
  executionNodeStatusLabel,
} from "./executionNodeLabels";

const verificationLabel = (status: string): string => {
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

const sessionCredentialErrors: Record<string, string> = {
  SESSION_CREDENTIAL_INPUT_INVALID: "Проверьте имя технического пользователя.",
  SESSION_CREDENTIAL_TOO_LARGE: "Учётные данные превышают допустимый размер.",
  SESSION_CREDENTIAL_MODE_INVALID:
    "Проверьте выбранный способ SSH и обязательные поля.",
  SESSION_PRIVATE_KEY_UNREADABLE: "Не удалось прочитать файл приватного ключа.",
  SESSION_PRIVATE_KEY_NOT_REGULAR: "Приватный ключ должен быть обычным файлом.",
  SESSION_PRIVATE_KEY_ENCRYPTED_UNSUPPORTED:
    "Зашифрованный приватный ключ не поддерживается.",
  SESSION_PRIVATE_KEY_INVALID:
    "Нужен поддерживаемый незашифрованный приватный ключ PEM.",
  SESSION_CREDENTIAL_UNAVAILABLE:
    "Не удалось сохранить учётные данные в текущем сеансе.",
  INSTALLATION_RUN_ACTIVE:
    "Нельзя изменить или очистить учётные данные, пока выполняется план установки.",
};

type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";

function StatusChip({
  tone,
  children,
}: {
  tone: StatusTone;
  children: ReactNode;
}) {
  const symbol =
    tone === "success"
      ? "✓"
      : tone === "warning"
        ? "!"
        : tone === "danger"
          ? "×"
          : tone === "info"
            ? "·"
            : "?";
  return (
    <span className={`status-chip status-chip--${tone}`}>
      <span className="status-chip-symbol" aria-hidden="true">
        {symbol}
      </span>
      {children}
    </span>
  );
}

function ServerLineIcon({ kind }: { kind: "server" | "key" | "execution" }) {
  return (
    <svg
      className="server-line-icon"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {kind === "key" ? (
        <>
          <circle cx="7" cy="8" r="3.5" />
          <path d="m9.5 10.5 6.5 6.5m-2-2 2-2m-4 0 2-2" />
        </>
      ) : kind === "execution" ? (
        <>
          <rect x="2.5" y="3" width="15" height="11" rx="2" />
          <path d="M7 17h6m-3-3v3m-1-9 3 2-3 2z" />
        </>
      ) : (
        <>
          <rect x="3" y="3" width="14" height="6" rx="1.5" />
          <rect x="3" y="11" width="14" height="6" rx="1.5" />
          <path d="M6 6h.01M6 14h.01M9 6h5m-5 8h5" />
        </>
      )}
    </svg>
  );
}

function executionNodeTone(status?: string): StatusTone {
  switch (status) {
    case "READY":
    case "PREPARED":
      return "success";
    case "UNREACHABLE":
    case "INCOMPATIBLE":
    case "BROKEN":
      return "danger";
    case "NOT_CONFIGURED":
    case "NOT_PREPARED":
    case "UNPREPARED":
    case "PREPARATION_REQUIRED":
    case "UPDATE_REQUIRED":
    case "CONFIRMATION_REQUIRED":
    case "BLOCKED":
      return "warning";
    default:
      return "neutral";
  }
}

function sessionCredentialErrorText(reason: unknown): string {
  const raw =
    typeof reason === "string"
      ? reason
      : reason &&
          typeof reason === "object" &&
          "message" in reason &&
          typeof reason.message === "string"
        ? reason.message
        : "";
  const code =
    raw.match(
      /\b(?:SESSION_CREDENTIAL|SESSION_PRIVATE_KEY)_[A-Z_]+\b|\bINSTALLATION_RUN_ACTIVE\b/,
    )?.[0] ||
    "";
  return (
    sessionCredentialErrors[code] ||
    sessionCredentialErrors.SESSION_CREDENTIAL_UNAVAILABLE
  );
}

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
  | { mode: "target-key"; row: Row }
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
  structuralDisabled,
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
  onProbeExecutionNodeHostKey,
  onApproveExecutionNodeHostKey,
  onDeclineExecutionNodeHostKey,
  onProbeTargetHostKey,
  onApproveTargetHostKey,
  onDeclineTargetHostKey,
  onPlanExecutionNodePreparation,
  onPrepareExecutionNode,
  runRecoveryPanel,
  cachedNodeReadiness,
  serverInformation = {},
  onProbeServerInformation,
  onCheckServerInformation,
}: {
  snapshot: OpenResult["snapshot"];
  managed: OpenResult["managed"];
  empty: boolean;
  intents: ServerIntent[];
  serverTypes: ServerType[];
  configError: string | null;
  busy: boolean;
  structuralDisabled: boolean;
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
  onProbeExecutionNodeHostKey?: () => Promise<HostKeyProbeResult>;
  onApproveExecutionNodeHostKey?: (
    probeId: string,
  ) => Promise<HostKeyProbeResult>;
  onDeclineExecutionNodeHostKey?: () => Promise<HostKeyProbeResult>;
  onProbeTargetHostKey?: (hostId: string) => Promise<HostKeyProbeResult>;
  onApproveTargetHostKey?: (probeId: string) => Promise<HostKeyProbeResult>;
  onDeclineTargetHostKey?: () => Promise<HostKeyProbeResult>;
  onPlanExecutionNodePreparation: () => Promise<ExecutionNodePreparation>;
  onPrepareExecutionNode: (planId: string) => Promise<ExecutionNodePreparation>;
  runRecoveryPanel?: ReactNode;
  cachedNodeReadiness?: ExecutionNodeReadiness | null;
  serverInformation?: Record<string, ServerInformationResult>;
  onProbeServerInformation?: (hostId: string) => Promise<HostKeyProbeResult>;
  onCheckServerInformation?: (probeId: string) => Promise<ServerInformationResult>;
}) {
  const [dialog, setDialog] = useState<Dialog>(null);
  const [informationHost, setInformationHost] = useState<string | null>(null);
  const [approvedTargets, setApprovedTargets] = useState<string[]>([]);
  useEffect(() => setApprovedTargets([]), [managed?.projectRevision]);
  const visible = rows(snapshot, managed, intents);
  const firstSave = empty;
  const crudDisabled = busy || structuralDisabled;
  return (
    <>
      <section className="title servers-title">
        <div>
          <h1>Серверы</h1>
          <p>Желаемая конфигурация серверов проекта.</p>
        </div>
        <button
          onClick={() => setDialog({ mode: "add" })}
          disabled={crudDisabled || !!configError}
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
              disabled={crudDisabled || !!configError}
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
                    crudDisabled ||
                    row.state === "deleting" ||
                    (firstSave && created);
                  return (
                    <tr
                      key={row.hostId}
                      className={[row.state ? `draft-${row.state}` : "", serverInformation[row.hostId] ? "server-information-attached" : ""].join(" ")}
                    >
                      <td>
                        <span className="server-name-cell">
                          <ServerLineIcon kind="server" />
                          <b>{row.hostId}</b>
                        </span>
                        {serverInformation[row.hostId] && <ServerInformationText value={serverInformation[row.hostId]} />}
                      </td>
                      <td>{labelType(row.type, serverTypes)}</td>
                      <td>{row.desiredHostname || <em>Не задано</em>}</td>
                      <td>{row.address}</td>
                      <td>{row.port}</td>
                      <td>
                        {row.state === "new" ? (
                          <StatusChip tone="info">Новый</StatusChip>
                        ) : row.state === "changed" ? (
                          <StatusChip tone="warning">Изменён</StatusChip>
                        ) : row.state === "deleting" ? (
                          <StatusChip tone="danger">Будет удалён</StatusChip>
                        ) : (
                          <StatusChip tone="success">{serverInformation[row.hostId]?.status === "CHECKED" ? "Проверен" : "Сохранён"}</StatusChip>
                        )}
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
                              className="link"
                              onClick={() =>
                                onProbeServerInformation ? setInformationHost(row.hostId) : setDialog({ mode: "target-key", row })
                              }
                              disabled={
                                disableCrud ||
                                commandCount > 0 ||
                                !managed?.servers?.[row.hostId] ||
                                (!onProbeServerInformation && !onProbeTargetHostKey)
                              }
                            >
                              {onProbeServerInformation ? "Проверить сервер" : approvedTargets.includes(row.hostId)
                                ? "SSH-ключ подтверждён"
                                : "Проверить SSH-ключ"}
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
          credentialStatus={credentialStatus}
          onProbe={onProbeExecutionNodeHostKey}
          onApprove={onApproveExecutionNodeHostKey}
          onDecline={onDeclineExecutionNodeHostKey}
          onPlan={onPlanExecutionNodePreparation}
          onPrepare={onPrepareExecutionNode}
          recoveryAction={runRecoveryPanel}
          cachedReadiness={cachedNodeReadiness}
          onInformationCheck={onProbeServerInformation ? () => setInformationHost(executionNode?.selectedHostId || "") : undefined}
          information={serverInformation[executionNode?.selectedHostId || ""]}
        />
      </div>
      {commandCount > 0 && (
        <section className="card draft-actions">
          <p>
            Черновик: {commandCount}. Перед сохранением будет показан локальный
            предварительный просмотр структуры затрагиваемых документов.
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
          busy={crudDisabled}
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
          busy={crudDisabled}
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
          busy={crudDisabled}
          onClose={() => setDialog(null)}
          onAppend={async (intent) => {
            const ok = await onAppend(intent);
            if (ok) setDialog(null);
            return ok;
          }}
        />
      )}
      {dialog?.mode === "target-key" &&
        onProbeTargetHostKey &&
        onApproveTargetHostKey &&
        onDeclineTargetHostKey && (
          <TargetHostKeyDialog
            row={dialog.row}
            onProbe={onProbeTargetHostKey}
            onApprove={onApproveTargetHostKey}
            onDecline={onDeclineTargetHostKey}
            onApproved={() =>
              setApprovedTargets((items) => [
                ...new Set([...items, dialog.row.hostId]),
              ])
            }
            onClose={() => setDialog(null)}
          />
        )}
      {informationHost && onProbeServerInformation && onCheckServerInformation && <ServerInformationDialog
        hostId={informationHost} onProbe={onProbeServerInformation} onCheck={onCheckServerInformation}
        onResult={() => {}} onClose={() => setInformationHost(null)} />}
    </>
  );
}

function TargetHostKeyDialog({
  row,
  onProbe,
  onApprove,
  onDecline,
  onApproved,
  onClose,
}: {
  row: Row;
  onProbe: (hostId: string) => Promise<HostKeyProbeResult>;
  onApprove: (probeId: string) => Promise<HostKeyProbeResult>;
  onDecline: () => Promise<HostKeyProbeResult>;
  onApproved: () => void;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [probe, setProbe] = useState<HostKeyProbeResult | null>(null);
  const [error, setError] = useState("");
  const close = async () => {
    if (probe?.status === "APPROVAL_REQUIRED")
      await onDecline().catch(() => undefined);
    onClose();
  };
  const runProbe = async () => {
    setBusy(true);
    setError("");
    setProbe(null);
    try {
      const next = await onProbe(row.hostId);
      setProbe(next);
      if (next.error)
        setError(next.error.message || "Не удалось получить ключ сервера.");
    } catch {
      setError("Не удалось получить ключ сервера.");
    } finally {
      setBusy(false);
    }
  };
  const approve = async () => {
    if (!probe?.probeId) return;
    setBusy(true);
    setError("");
    try {
      const next = await onApprove(probe.probeId);
      setProbe(next);
      if (next.status === "APPROVED") onApproved();
      else setError(next.error?.message || "Подтверждение ключа отклонено.");
    } catch {
      setError("Не удалось подтвердить ключ сервера.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal" role="presentation">
      <section
        className="card dialog server-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="target-key-title"
      >
        <h1 id="target-key-title">SSH-ключ сервера {row.hostId}</h1>
        <p>
          Адрес: {row.address}:{row.port}
        </p>
        <p className="muted">
          Сверьте отпечаток с независимым доверенным источником. Получение ключа
          по сети само по себе не подтверждает его подлинность.
        </p>
        <button type="button" onClick={runProbe} disabled={busy}>
          Получить отпечаток
        </button>
        {probe?.status === "APPROVAL_REQUIRED" && (
          <div role="group" aria-label="Подтверждение ключа целевого сервера">
            <p>Тип: {probe.keyType}</p>
            <p>
              Отпечаток: <code>{probe.fingerprint}</code>
            </p>
            <button type="button" onClick={approve} disabled={busy}>
              Подтверждаю совпадение
            </button>
          </div>
        )}
        {probe?.status === "APPROVED" && (
          <p role="status">
            Ключ подтверждён для текущего проекта и сохранённой ревизии.
          </p>
        )}
        {error && (
          <p role="alert" className="field-error">
            {error}
          </p>
        )}
        <button
          type="button"
          className="outline"
          onClick={close}
          disabled={busy}
        >
          Закрыть
        </button>
      </section>
    </div>
  );
}

function ExecutionNodePanel({
  context,
  rows,
  disabled,
  onSelect,
  onCheck,
  credentialStatus,
  onProbe,
  onApprove,
  onDecline,
  onPlan,
  onPrepare,
  recoveryAction,
  cachedReadiness,
  onInformationCheck,
  information,
}: {
  context: ExecutionNodeContext | null;
  rows: Row[];
  disabled: boolean;
  onSelect: (hostId: string) => Promise<ExecutionNodeContext>;
  onCheck: () => Promise<ExecutionNodeReadiness>;
  credentialStatus: SessionCredentialStatus | null;
  onProbe?: () => Promise<HostKeyProbeResult>;
  onApprove?: (probeId: string) => Promise<HostKeyProbeResult>;
  onDecline?: () => Promise<HostKeyProbeResult>;
  onPlan: () => Promise<ExecutionNodePreparation>;
  onPrepare: (planId: string) => Promise<ExecutionNodePreparation>;
  recoveryAction?: ReactNode;
  cachedReadiness?: ExecutionNodeReadiness | null;
  onInformationCheck?: () => void;
  information?: ServerInformationResult;
}) {
  const [changing, setChanging] = useState(false);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [readiness, setReadiness] = useState<ExecutionNodeReadiness | null>(
    null,
  );
  const [preparation, setPreparation] =
    useState<ExecutionNodePreparation | null>(null);
  const [hostKeyProbe, setHostKeyProbe] = useState<HostKeyProbeResult | null>(
    null,
  );
  const [hostKeyDialogOpen, setHostKeyDialogOpen] = useState(false);
  useEffect(() => {
    setHostKeyProbe(null);
    setHostKeyDialogOpen(false);
    setReadiness(null);
    setPreparation(null);
  }, [
    context?.selectedHostId,
    context?.runtimeDigest,
    credentialStatus?.expiresAt,
    credentialStatus?.sshMode,
    credentialStatus?.status,
  ]);
  const effective: Partial<ExecutionNodeContext> & {
    status: string;
    selectionSource: string;
  } = context || {
    status: "NOT_CONFIGURED",
    selectionSource: "NONE",
  };
  const combinedStatus = executionNodeCombinedStatus(readiness || cachedReadiness, preparation);
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
    <>
    <section
      className="card execution-node-panel"
      aria-labelledby="execution-node-heading"
    >
      <div className="execution-node-heading">
        <h2 id="execution-node-heading">
          <ServerLineIcon kind="execution" />
          Узел выполнения
        </h2>
        <StatusChip tone={executionNodeTone(effective.status)}>
          {executionNodeStatusLabel(effective.status)}
        </StatusChip>
      </div>
      <div className="execution-node-detail">
        <span>Выбранный узел</span>
        <b>{effective.safeLabel || "Не выбран"}</b>
        <span>Источник выбора</span>
        <b>{executionNodeSelectionLabel(effective.selectionSource)}</b>
      </div>
      <p className="muted">
        Выбор узла хранится только в приложении и не меняет проект. Подготовка —
        только после подтверждения.
      </p>
      {!onInformationCheck && onProbe && context?.selectionKind === "PROJECT_SERVER" && (
        <div className="execution-node-host-key">
          <p className="muted">
            Нужен действующий SSH-сеанс; перед подключением сверьте SSH-отпечаток вне
            приложения.
          </p>
          <button
            className="outline"
            disabled={
              disabled ||
              busy ||
              credentialStatus?.status !== "PRESENT"
            }
            onClick={() => {
              setHostKeyProbe(null);
              setHostKeyDialogOpen(true);
            }}
          >
            Получить отпечаток SSH
          </button>
          {hostKeyProbe?.status === "APPROVAL_REQUIRED" && hostKeyDialogOpen && (
            <div role="group" aria-label="Подтверждение ключа SSH">
              <p>
                Ключ: <b>{hostKeyProbe.keyType}</b> · Отпечаток:{" "}
                <code>{hostKeyProbe.fingerprint}</code>
              </p>
              <p className="muted">
                Не подтверждайте ключ, пока не сверите отпечаток вне этого
                приложения.
              </p>
              <button
                disabled={
                  disabled || busy || !onApprove || !hostKeyProbe.probeId
                }
                onClick={async () => {
                  if (!hostKeyProbe.probeId || !onApprove) return;
                  setBusy(true);
                  setError("");
                  try {
                    setHostKeyProbe(await onApprove(hostKeyProbe.probeId));
                  } catch {
                    setError("Не удалось подтвердить ключ SSH.");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Подтверждаю совпадение
              </button>
              <button
                className="outline"
                disabled={busy || !onDecline}
                onClick={async () => {
                  if (!onDecline) return;
                  setBusy(true);
                  try {
                    setHostKeyProbe(await onDecline());
                  } catch {
                    setError("Не удалось отклонить ключ SSH.");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Отклонить
              </button>
            </div>
          )}
          {hostKeyProbe?.status === "APPROVED" && (
            <span className="execution-node-trust-status" role="status">
              <StatusChip tone="success">
                SSH-отпечаток подтверждён
              </StatusChip>
            </span>
          )}
          {hostKeyProbe?.error && (
            <p className="field-error" role="alert">
              {hostKeyProbe.error.message}
            </p>
          )}
        </div>
      )}
      <p
        className={combinedStatus.tone === "danger" ? "field-error" : "muted"}
        role={combinedStatus.tone === "danger" ? "alert" : "status"}
      >
        Статус:{" "}
        <StatusChip tone={combinedStatus.tone}>{combinedStatus.label}</StatusChip>
        {combinedStatus.detail ? ` · ${combinedStatus.detail}` : ""}
        {preparation?.verification
          ? ` · Проверка проекта: ${verificationLabel(preparation.verification.status)}`
          : ""}
      </p>
      {[...(readiness?.findings || []), ...(preparation?.findings || [])].map(
        (finding, index) => (
          <p
            className="field-error"
            key={`${index}-${finding.code}`}
            role="status"
          >
            {finding.safeMessage}
          </p>
        ),
      )}
      <div className="actions">
        {recoveryAction}
        {onInformationCheck && <button className="outline" onClick={onInformationCheck} disabled={disabled || busy || credentialStatus?.status !== "PRESENT"}>Проверить сервер</button>}
        {!onInformationCheck &&
        <button
          className="outline"
          onClick={async () => {
            setBusy(true);
            setError("");
            setPreparation(null);
            try {
              setReadiness(await onCheck());
            } catch {
              setError("EXECUTION_NODE_CHECK_UNAVAILABLE");
            } finally {
              setBusy(false);
            }
          }}
          disabled={disabled || busy}
        >
          Проверить узел
        </button>
        }
        <button
          className="outline"
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              setPreparation(await onPlan());
            } catch {
              setError("EXECUTION_NODE_PREPARATION_UNAVAILABLE");
            } finally {
              setBusy(false);
            }
          }}
          disabled={disabled || busy}
        >
          Спланировать подготовку
        </button>
        {preparation?.status === "CONFIRMATION_REQUIRED" &&
          preparation.planId && (
            <button
              onClick={async () => {
                const planId = preparation.planId;
                if (!planId) return;
                if (
                  !window.confirm(
                    "Подготовить выбранный узел выполнения? Это может активировать проверенное окружение.",
                  )
                )
                  return;
                setBusy(true);
                setError("");
                const currentPreparation = preparation;
                setPreparation({ ...preparation, status: "PREPARING" });
                try {
                  const result = await onPrepare(planId);
                  setPreparation(result);
                } catch {
                  setPreparation(currentPreparation);
                  setError("EXECUTION_NODE_PREPARATION_UNAVAILABLE");
                } finally {
                  setBusy(false);
                }
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
          aria-label="Выбрать узел выполнения"
          onClick={() => {
            setSelected(context?.selectedHostId || rows[0]?.hostId || "");
            setChanging(true);
          }}
          disabled={disabled || rows.length === 0}
        >
          Выбрать узел выполнения
        </button>
      ) : (
        <div className="execution-node-change">
          <label>
            Сервер проекта
            <select
              aria-label="Сервер проекта для узла выполнения"
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
      {information && <div className="execution-node-information"><ServerInformationText value={information} /></div>}
    </section>
    {hostKeyDialogOpen && onProbe && (
      <ExecutionNodeHostKeyDialog
        label={effective.safeLabel || effective.selectedHostId || "узел выполнения"}
        onProbe={onProbe}
        onApprove={onApprove}
        onDecline={onDecline}
        disabled={disabled}
        onApproved={(result) => setHostKeyProbe(result)}
        onClose={() => setHostKeyDialogOpen(false)}
      />
    )}
    </>
  );
}

function ExecutionNodeHostKeyDialog({
  label,
  onProbe,
  onApprove,
  onDecline,
  disabled,
  onApproved,
  onClose,
}: {
  label: string;
  onProbe: () => Promise<HostKeyProbeResult>;
  onApprove?: (probeId: string) => Promise<HostKeyProbeResult>;
  onDecline?: () => Promise<HostKeyProbeResult>;
  disabled: boolean;
  onApproved: (result: HostKeyProbeResult) => void;
  onClose: () => void;
}) {
  const [probe, setProbe] = useState<HostKeyProbeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const runProbe = async () => {
    setBusy(true);
    setError("");
    setProbe(null);
    try {
      const result = await onProbe();
      setProbe(result);
      if (result.status === "APPROVED") onApproved(result);
      if (result.error) setError(result.error.message || "Не удалось получить SSH-ключ.");
    } catch {
      setError("Не удалось получить отпечаток ключа SSH.");
    } finally {
      setBusy(false);
    }
  };
  const approve = async () => {
    if (!probe?.probeId || !onApprove) return;
    setBusy(true);
    setError("");
    try {
      const result = await onApprove(probe.probeId);
      setProbe(result);
      if (result.status === "APPROVED") onApproved(result);
      else setError(result.error?.message || "Подтверждение ключа не выполнено.");
    } catch {
      setError("Не удалось подтвердить ключ SSH.");
    } finally {
      setBusy(false);
    }
  };
  const decline = async () => {
    if (!onDecline) return;
    setBusy(true);
    setError("");
    try {
      setProbe(await onDecline());
    } catch {
      setError("Не удалось отклонить ключ SSH.");
    } finally {
      setBusy(false);
    }
  };
  const close = async () => {
    if (probe?.status === "APPROVAL_REQUIRED") await decline();
    onClose();
  };
  return (
    <div className="modal" role="presentation">
      <section
        className="card dialog server-dialog execution-node-key-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="execution-node-key-title"
      >
        <h1 id="execution-node-key-title">SSH-ключ узла выполнения</h1>
        <p>Узел: {label}</p>
        <p className="muted">
          Сверьте отпечаток с независимым доверенным источником. Получение ключа
          по сети само по себе не подтверждает его подлинность.
        </p>
        {probe?.status === "APPROVAL_REQUIRED" && (
          <div role="group" aria-label="Подтверждение ключа SSH">
            <p>Тип: <b>{probe.keyType}</b></p>
            <p>Отпечаток: <code>{probe.fingerprint}</code></p>
            <p className="muted">
              Не подтверждайте ключ, пока не сверите отпечаток вне этого приложения.
            </p>
          </div>
        )}
        {probe?.status === "APPROVED" && (
          <p role="status">Ключ SSH подтверждён для текущего сеанса.</p>
        )}
        {error && <p className="field-error" role="alert">{error}</p>}
        <div className="actions execution-node-key-actions">
          {probe?.status !== "APPROVED" && (
            <button type="button" onClick={runProbe} disabled={busy || disabled}>
              {probe?.status === "APPROVAL_REQUIRED" ? "Получить заново" : "Получить отпечаток"}
            </button>
          )}
          {probe?.status === "APPROVAL_REQUIRED" && (
            <>
              <button
                type="button"
                onClick={approve}
                disabled={busy || disabled || !onApprove || !probe.probeId}
              >
                Подтверждаю совпадение
              </button>
              <button
                type="button"
                className="outline"
                onClick={decline}
                disabled={busy || !onDecline}
              >
                Отклонить
              </button>
            </>
          )}
          <button type="button" className="outline" onClick={close} disabled={busy}>
            Закрыть
          </button>
        </div>
      </section>
    </div>
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
      setError(sessionCredentialErrorText(reason));
    } finally {
      setBusy(false);
    }
  };
  const effectiveStatus = status?.status || "MISSING";
  const expiryDate = status?.expiresAt ? new Date(status.expiresAt) : null;
  const expiryLabel = expiryDate && !Number.isNaN(expiryDate.getTime())
    ? `${new Intl.DateTimeFormat("ru-RU", {
        timeZone: "Europe/Moscow",
        day: "2-digit", month: "2-digit", year: "numeric",
        hour: "2-digit", minute: "2-digit", second: "2-digit",
        hourCycle: "h23",
      }).format(expiryDate)} МСК`
    : null;
  return (
    <section
      className="card session-credentials"
      aria-labelledby="session-credentials-heading"
    >
      <div className="session-credentials-heading">
        <h2 id="session-credentials-heading">
          <ServerLineIcon kind="key" />
          Учётные данные сеанса
        </h2>
        <p className="muted">
          Для всех серверов текущего сеанса; в проект не записываются.
        </p>
        <p className="muted session-credentials-status" aria-live="polite">
          <StatusChip
            tone={
              effectiveStatus === "PRESENT"
                ? "success"
                : effectiveStatus === "EXPIRED"
                  ? "warning"
                  : "neutral"
            }
          >
            {effectiveStatus === "PRESENT"
              ? "Доступны"
              : effectiveStatus === "EXPIRED"
                ? "Истекли"
                : "Не заданы"}
          </StatusChip>
          {effectiveStatus === "PRESENT" && expiryLabel
            ? ` до ${expiryLabel}`
            : effectiveStatus === "EXPIRED"
              ? "Добавьте учётные данные повторно"
              : "Введите данные для подключения"}
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
                setError(sessionCredentialErrorText(reason));
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
            {mode === "add" && (
              <option value="inherit">
                Наследовать порт (не задавать явно)
              </option>
            )}
            {mode === "edit" && <option value="unchanged">Не изменять</option>}
            <option value="explicit">Задать явно</option>
            {mode === "edit" && (
              <option value="clear">Убрать переопределение инсталлера</option>
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
          Сервер <b>{row.hostId}</b> будет удалён из инвентаря. Связанные
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
