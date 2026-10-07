import { useMemo, useState } from "react";
import type { EndpointPreview, OpenResult, VerificationStatus } from "./backend";
import type { DeploymentIntent } from "./TopologyPage";

export type EndpointIntent =
  | {
      operation: "CreateEndpointGroup";
      endpointGroupId: string;
      endpointGroup: { address: { domain: string; wildcard: boolean } };
    }
  | {
      operation: "UpdateEndpointGroup";
      endpointGroupId: string;
      endpointGroup: { address: { domain: string; wildcard: boolean } };
    }
  | { operation: "DeleteEndpointGroup"; endpointGroupId: string }
  | {
      operation: "SetServiceEndpointGroup";
      deploymentId: string;
      endpointGroupId: string;
    }
  | { operation: "ClearServiceEndpointGroup"; deploymentId: string };

export type ProviderIntent =
  | {
      operation: "ReconcileEndpointProvider";
      deploymentId: string;
      endpointGroupId: string;
      virtualRouterId: number;
      virtualAddresses: Array<{ address: string; interface: string }>;
    }
  | { operation: "ClearEndpointProvider"; deploymentId: string };

type EntryPointsIntent = EndpointIntent | ProviderIntent;

type Group = {
  id: string;
  domain: string;
  wildcard: boolean;
  state?: "new" | "deleting";
};
type Deployment = {
  id: string;
  serviceType: string;
  mode: string;
  endpointGroup?: string;
  endpointGroupRef?: string;
  virtualRouterId?: number;
  virtualAddresses?: Array<{ address: string; interface: string }>;
  providerEditState?: "NONE" | "EDITABLE" | "INCOMPLETE" | "UNSUPPORTED";
  state?: "new" | "deleting";
};
const idPattern = /^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$/;

function finalGroups(
  managed: OpenResult["managed"],
  intents: EndpointIntent[],
) {
  const values = new Map<string, Group>();
  for (const [id, group] of Object.entries(managed?.endpointGroups || {}))
    values.set(id, { id, domain: group.domain, wildcard: group.wildcard });
  for (const intent of intents) {
    if (intent.operation === "CreateEndpointGroup")
      values.set(intent.endpointGroupId, {
        id: intent.endpointGroupId,
        ...intent.endpointGroup.address,
        state: "new",
      });
    if (intent.operation === "UpdateEndpointGroup") {
      const current = values.get(intent.endpointGroupId);
      if (current)
        values.set(intent.endpointGroupId, {
          ...current,
          ...intent.endpointGroup.address,
        });
    }
    if (intent.operation === "DeleteEndpointGroup") {
      const current = values.get(intent.endpointGroupId);
      if (current)
        values.set(intent.endpointGroupId, { ...current, state: "deleting" });
    }
  }
  return [...values.values()].sort((a, b) => a.id.localeCompare(b.id));
}

function finalDeployments(
  managed: OpenResult["managed"],
  deploymentIntents: DeploymentIntent[],
  intents: EndpointIntent[],
  providerIntents: ProviderIntent[],
) {
  const values = new Map<string, Deployment>();
  for (const [id, item] of Object.entries(managed?.deployments || {}))
    values.set(id, {
      id,
      serviceType: item.serviceType,
      mode: item.mode,
      endpointGroup: item.endpointGroup,
      endpointGroupRef: item.endpointGroupRef,
      virtualRouterId: item.virtualRouterId,
      virtualAddresses: item.virtualAddresses,
      providerEditState: item.providerEditState,
    });
  for (const intent of deploymentIntents) {
    if (intent.operation === "CreateServiceDeployment")
      values.set(intent.deploymentId, {
        id: intent.deploymentId,
        serviceType: intent.serviceType,
        mode: intent.mode,
        state: "new",
      });
    if (intent.operation === "DeleteServiceDeployment") {
      const current = values.get(intent.deploymentId);
      if (current)
        values.set(intent.deploymentId, { ...current, state: "deleting" });
    }
  }
  for (const intent of intents) {
    if (intent.operation === "SetServiceEndpointGroup") {
      const current = values.get(intent.deploymentId);
      if (current)
        values.set(intent.deploymentId, {
          ...current,
          endpointGroup: intent.endpointGroupId,
        });
    }
    if (intent.operation === "ClearServiceEndpointGroup") {
      const current = values.get(intent.deploymentId);
      if (current)
        values.set(intent.deploymentId, {
          ...current,
          endpointGroup: undefined,
        });
    }
  }
  for (const intent of providerIntents) {
    const current = values.get(intent.deploymentId);
    if (!current) continue;
    if (intent.operation === "ReconcileEndpointProvider")
      values.set(intent.deploymentId, {
        ...current,
        endpointGroupRef: intent.endpointGroupId,
        virtualRouterId: intent.virtualRouterId,
        virtualAddresses: intent.virtualAddresses,
        providerEditState: "EDITABLE",
      });
    if (intent.operation === "ClearEndpointProvider")
      values.set(intent.deploymentId, {
        ...current,
        endpointGroupRef: undefined,
        virtualRouterId: undefined,
        virtualAddresses: undefined,
        providerEditState: "NONE",
      });
  }
  return [...values.values()].sort((a, b) => a.id.localeCompare(b.id));
}

export function EntryPointsView({
  managed,
  catalog,
  intents,
  providerIntents,
  deploymentIntents,
  preview,
  verificationStatus,
  busy,
  disabled,
  commandCount,
  onAppend,
}: {
  managed: OpenResult["managed"];
  catalog: OpenResult["catalog"];
  intents: EndpointIntent[];
  providerIntents: ProviderIntent[];
  deploymentIntents: DeploymentIntent[];
  preview?: EndpointPreview;
  verificationStatus: VerificationStatus["status"];
  busy: boolean;
  disabled: boolean;
  commandCount: number;
  onAppend: (intent: EntryPointsIntent) => Promise<boolean>;
}) {
  const [dialog, setDialog] = useState<{
    mode: "add" | "edit";
    group?: Group;
  } | null>(null);
  const [providerDialog, setProviderDialog] = useState<Deployment | null>(null);
  const groups = useMemo(
    () => finalGroups(managed, intents),
    [managed, intents],
  );
  const deployments = useMemo(
    () =>
      finalDeployments(managed, deploymentIntents, intents, providerIntents),
    [managed, deploymentIntents, intents, providerIntents],
  );
  const catalogReady = catalog?.status === "READY";
  const limit = commandCount >= 16;
  const groupLocked = (id: string) =>
    intents.some(
      (item) => "endpointGroupId" in item && item.endpointGroupId === id,
    );
  const deploymentLocked = (id: string) =>
    intents.some((item) =>
      item.operation === "SetServiceEndpointGroup" ||
      item.operation === "ClearServiceEndpointGroup"
        ? item.deploymentId === id
        : false,
    );
  const eligible = (serviceType: string) =>
    catalog?.services?.find((item) => item.id === serviceType)
      ?.endpointConsumer === true;
  const providerEligible = (serviceType: string) =>
    catalog?.services?.find((item) => item.id === serviceType)
      ?.endpointProvider === true;
  const providerLocked = (id: string) =>
    providerIntents.some((item) => item.deploymentId === id);
  const providerDeployments = deployments.filter((item) =>
    item.state === "deleting"
      ? false
      : catalogReady
        ? providerEligible(item.serviceType)
        : !!item.endpointGroupRef ||
          item.providerEditState === "INCOMPLETE" ||
          item.providerEditState === "UNSUPPORTED",
  );
  return (
    <>
      {preview?.status === "INVALID" && (
        <section className="entry-findings" role="alert">
          <strong>Адреса и provider/VIP не показаны: проверка Core выявила ошибки.</strong>
          {preview.findings?.map((finding) => (
            <p key={`${finding.code}-${finding.subjectId || ""}`}>
              {finding.code}: {finding.summary}
            </p>
          ))}
        </section>
      )}
      {providerIntents.length > 0 && (
        <p className="entry-draft-notice" role="status">
          Конфигурация provider изменена в черновике; влияние на PKI/SAN определяет только Core.
        </p>
      )}
      {!preview && verificationStatus !== "VERIFIED" && (
        <p className="entry-draft-notice" role="status">
          {verificationStatus === "UNAVAILABLE"
            ? "Core сейчас недоступен; проект не изменён."
            : "Актуальные данные Core пока не получены; сохраните проект и выполните проверку."}
        </p>
      )}
      <section className="title topology-title">
        <div>
          <h1>Точки входа</h1>
          <p>
            Группы адресов, назначения потребителей и параметры provider/VIP.
          </p>
          {commandCount > 0 && (
            <p className="muted">
              Черновик: {commandCount} из 16 · осталось {Math.max(0, 16 - commandCount)}
            </p>
          )}
        </div>
        <button
          onClick={() => setDialog({ mode: "add" })}
          disabled={busy || disabled || limit}
        >
          Добавить группу
        </button>
      </section>
      <div className="entry-grid">
        <section className="card entry-panel">
          <h2 className="entry-panel-title">
            <EntryPointIcon kind="groups" />
            <span>Группы endpoint</span>
          </h2>
          {groups.length === 0 ? (
            <p className="muted">Групп пока нет.</p>
          ) : (
            <div className="entry-list">
              {groups.map((group) => (
                <div key={group.id} className="entry-row">
                  <div>
                    <b>{group.id}</b>
                    <span>
                      {group.domain}
                      {group.wildcard ? " · wildcard" : ""}
                    </span>
                    {group.state && (
                      <small
                        className={`entry-state-chip ${group.state === "new" ? "entry-state-chip--info" : "entry-state-chip--warning"}`}
                      >
                        <span aria-hidden="true">
                          {group.state === "new" ? "+" : "!"}
                        </span>
                        {group.state === "new" ? "Новая" : "Будет удалена"}
                      </small>
                    )}
                  </div>
                  <div className="actions">
                    <button
                      className="outline"
                      onClick={() => setDialog({ mode: "edit", group })}
                      disabled={
                        busy ||
                        disabled ||
                        limit ||
                        !!group.state ||
                        groupLocked(group.id)
                      }
                    >
                      Изменить
                    </button>
                    <button
                      className="outline danger"
                      onClick={() =>
                        onAppend({
                          operation: "DeleteEndpointGroup",
                          endpointGroupId: group.id,
                        })
                      }
                      disabled={
                        busy ||
                        disabled ||
                        limit ||
                        !!group.state ||
                        groupLocked(group.id)
                      }
                    >
                      Удалить
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
        <section className="card entry-panel entry-consumers">
          <h2 className="entry-panel-title">
            <EntryPointIcon kind="consumers" />
            <span>Назначения consumers</span>
          </h2>
          {deployments.length === 0 ? (
            <p className="muted">Нет deployments.</p>
          ) : (
            <div className="entry-list">
              {deployments
                .filter((item) => item.state !== "deleting")
                .map((deployment) => {
                  const canSet =
                    catalogReady && eligible(deployment.serviceType);
                  const choices = groups.filter((group) => !group.state);
                  const assignmentStatus = !canSet
                    ? {
                        tone: "neutral",
                        symbol: "·",
                        label: catalogReady
                          ? "Не поддерживает consumer"
                          : "Каталог недоступен",
                      }
                    : deployment.endpointGroup
                      ? {
                          tone: "success",
                          symbol: "✓",
                          label: `Назначена: ${deployment.endpointGroup}`,
                        }
                      : {
                          tone: "warning",
                          symbol: "!",
                          label: "Не назначена",
                        };
                  return (
                    <div key={deployment.id} className="entry-row">
                      <div>
                        <b>{deployment.id}</b>
                        <span>{deployment.serviceType}</span>
                        <small
                          className={`entry-state-chip entry-state-chip--${assignmentStatus.tone}`}
                        >
                          <span aria-hidden="true">{assignmentStatus.symbol}</span>
                          {assignmentStatus.label}
                        </small>
                      </div>
                      <div className="actions">
                        <select
                          aria-label={`Endpoint group for ${deployment.id}`}
                          value={deployment.endpointGroup || ""}
                          disabled={
                            busy ||
                            disabled ||
                            limit ||
                            deploymentLocked(deployment.id) ||
                            !canSet
                          }
                          onChange={(event) => {
                            if (event.target.value)
                              void onAppend({
                                operation: "SetServiceEndpointGroup",
                                deploymentId: deployment.id,
                                endpointGroupId: event.target.value,
                              });
                          }}
                        >
                          <option value="">Выберите группу</option>
                          {choices.map((group) => (
                            <option value={group.id} key={group.id}>
                              {group.id}
                            </option>
                          ))}
                        </select>
                        {deployment.endpointGroup && (
                          <button
                            className="outline"
                            onClick={() =>
                              void onAppend({
                                operation: "ClearServiceEndpointGroup",
                                deploymentId: deployment.id,
                              })
                            }
                            disabled={
                              busy ||
                              disabled ||
                              limit ||
                              deploymentLocked(deployment.id)
                            }
                          >
                            Очистить
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </section>
        <section className="card entry-panel">
          <h2 className="entry-panel-title">
            <EntryPointIcon kind="provider" />
            <span>Provider / VIP</span>
          </h2>
          {providerDeployments.length === 0 ? (
            <p className="muted">Нет доступных provider deployments.</p>
          ) : (
            <div className="entry-list">
              {providerDeployments.map((deployment) => {
                const supported = providerEligible(deployment.serviceType);
                const readOnly = !catalogReady || !supported;
                const canClear =
                  !!deployment.endpointGroupRef &&
                  !providerLocked(deployment.id);
                const providerStatus =
                  deployment.providerEditState === "INCOMPLETE"
                    ? {
                        tone: "danger",
                        symbol: "!",
                        label: "Неполная конфигурация",
                      }
                    : deployment.providerEditState === "UNSUPPORTED"
                      ? {
                          tone: "neutral",
                          symbol: "·",
                          label: "Только просмотр",
                        }
                      : deployment.endpointGroupRef
                        ? {
                            tone: "success",
                            symbol: "✓",
                            label: "Настроен",
                          }
                        : {
                            tone: "warning",
                            symbol: "!",
                            label: "Не настроен",
                          };
                return (
                  <div key={deployment.id} className="entry-row">
                    <div>
                      <b>{deployment.id}</b>
                      <span>
                        {deployment.endpointGroupRef
                          ? `${deployment.endpointGroupRef} · VRID ${deployment.virtualRouterId || "—"}`
                          : "Provider не настроен"}
                      </span>
                      <small
                        className={`entry-state-chip entry-state-chip--${providerStatus.tone}`}
                      >
                        <span aria-hidden="true">{providerStatus.symbol}</span>
                        {providerStatus.label}
                      </small>
                      {deployment.virtualAddresses?.map((address) => (
                        <small key={`${address.address}-${address.interface}`}>
                          {address.address} · {address.interface}
                        </small>
                      ))}
                      {deployment.providerEditState === "INCOMPLETE" && (
                        <small>
                          Неполная конфигурация: завершите или очистите.
                        </small>
                      )}
                      {deployment.providerEditState === "UNSUPPORTED" && (
                        <small>
                          Legacy-конфигурация вне безопасных границ редактора.
                        </small>
                      )}
                      {!catalogReady && (
                        <small>
                          Каталог недоступен: редактирование выключено.
                        </small>
                      )}
                      {catalogReady && !supported && (
                        <small>Сервис не поддерживает endpoint provider.</small>
                      )}
                    </div>
                    <div className="actions">
                      <button
                        className="outline"
                        onClick={() => setProviderDialog(deployment)}
                        disabled={
                          busy ||
                          disabled ||
                          limit ||
                          readOnly ||
                          providerLocked(deployment.id)
                        }
                      >
                        {deployment.providerEditState === "UNSUPPORTED"
                          ? "Заменить"
                          : "Настроить"}
                      </button>
                      <button
                        className="outline danger"
                        onClick={() =>
                          void onAppend({
                            operation: "ClearEndpointProvider",
                            deploymentId: deployment.id,
                          })
                        }
                        disabled={busy || disabled || limit || !canClear}
                        title="Удаляет provider tuple из черновика. После сохранения Core потребует complete tuple или удаления deployment."
                      >
                        Очистить
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
      {dialog && (
        <EndpointGroupDialog
          group={dialog.group}
          busy={busy}
          existing={new Set(groups.map((item) => item.id))}
          onClose={() => setDialog(null)}
          onAppend={async (intent) => {
            const accepted = await onAppend(intent);
            if (accepted) setDialog(null);
            return accepted;
          }}
        />
      )}
      {providerDialog && (
        <ProviderDialog
          deployment={providerDialog}
          groups={groups.filter((group) => !group.state)}
          busy={busy}
          onClose={() => setProviderDialog(null)}
          onAppend={async (intent) => {
            const accepted = await onAppend(intent);
            if (accepted) setProviderDialog(null);
            return accepted;
          }}
        />
      )}
    </>
  );
}

function EntryPointIcon({
  kind,
}: {
  kind: "groups" | "consumers" | "provider";
}) {
  return (
    <svg
      className="entry-panel-icon"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {kind === "groups" ? (
        <>
          <circle cx="4" cy="10" r="2" />
          <circle cx="15.5" cy="4.5" r="2" />
          <circle cx="15.5" cy="15.5" r="2" />
          <path d="m6 9 7.5-3.5M6 11l7.5 3.5" />
        </>
      ) : kind === "consumers" ? (
        <>
          <path d="M10 3v5m0 0-5 5m5-5 5 5" />
          <path d="M10 8v8m-2-2 2 2 2-2" />
          <path d="m3 11 2 2 2-2m6 0 2 2 2-2" />
        </>
      ) : (
        <>
          <rect x="5" y="2.5" width="10" height="5" rx="1" />
          <rect x="1.5" y="13" width="6" height="4.5" rx="1" />
          <rect x="12.5" y="13" width="6" height="4.5" rx="1" />
          <path d="M10 7.5v3M4.5 10.5h11m-11 0v2.5m11-2.5v2.5" />
        </>
      )}
    </svg>
  );
}

function EndpointGroupDialog({
  group,
  existing,
  busy,
  onClose,
  onAppend,
}: {
  group?: Group;
  existing: Set<string>;
  busy: boolean;
  onClose: () => void;
  onAppend: (intent: EndpointIntent) => Promise<boolean>;
}) {
  const [id, setID] = useState(group?.id || "");
  const [domain, setDomain] = useState(group?.domain || "");
  const [wildcard, setWildcard] = useState(group?.wildcard || false);
  const [error, setError] = useState("");
  const submit = async () => {
    const normalizedID = id.trim();
    const normalizedDomain = domain.trim().toLowerCase();
    if (!group && (!idPattern.test(normalizedID) || existing.has(normalizedID)))
      return setError("Введите уникальный ID группы.");
    if (
      !normalizedDomain ||
      normalizedDomain.length > 253 ||
      !normalizedDomain.includes(".")
    )
      return setError("Введите корректный домен.");
    const intent: EndpointIntent = group
      ? {
          operation: "UpdateEndpointGroup",
          endpointGroupId: group.id,
          endpointGroup: { address: { domain: normalizedDomain, wildcard } },
        }
      : {
          operation: "CreateEndpointGroup",
          endpointGroupId: normalizedID,
          endpointGroup: { address: { domain: normalizedDomain, wildcard } },
        };
    await onAppend(intent);
  };
  return (
    <div className="modal" role="dialog" aria-modal="true">
      <section className="card dialog">
        <h2>{group ? "Изменить группу" : "Добавить группу"}</h2>
        {!group && (
          <label>
            ID
            <input
              value={id}
              onChange={(event) => setID(event.target.value)}
              maxLength={128}
            />
          </label>
        )}
        <label>
          Домен
          <input
            value={domain}
            onChange={(event) => setDomain(event.target.value)}
            maxLength={253}
          />
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={wildcard}
            onChange={(event) => setWildcard(event.target.checked)}
          />
          Wildcard
        </label>
        {error && <p className="field-error">{error}</p>}
        <div className="actions">
          <button className="outline" onClick={onClose} disabled={busy}>
            Отмена
          </button>
          <button onClick={() => void submit()} disabled={busy}>
            {group ? "Сохранить" : "Добавить"}
          </button>
        </div>
      </section>
    </div>
  );
}

function ProviderDialog({
  deployment,
  groups,
  busy,
  onClose,
  onAppend,
}: {
  deployment: Deployment;
  groups: Group[];
  busy: boolean;
  onClose: () => void;
  onAppend: (intent: ProviderIntent) => Promise<boolean>;
}) {
  const [endpointGroupId, setEndpointGroupID] = useState(
    deployment.endpointGroupRef || "",
  );
  const [vrid, setVRID] = useState(
    deployment.virtualRouterId ? String(deployment.virtualRouterId) : "",
  );
  const [addresses, setAddresses] = useState(
    deployment.providerEditState === "UNSUPPORTED"
      ? [{ address: "", interface: "" }]
      : deployment.virtualAddresses?.length
        ? deployment.virtualAddresses
        : [{ address: "", interface: "" }],
  );
  const [error, setError] = useState("");
  const submit = async () => {
    const normalized = addresses.map((item) => ({
      address: item.address.trim(),
      interface: item.interface.trim(),
    }));
    const parsedVRID = Number(vrid);
    const ipv4 =
      /^(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}$/;
    if (
      !endpointGroupId ||
      !Number.isInteger(parsedVRID) ||
      parsedVRID < 1 ||
      parsedVRID > 255
    )
      return setError("Выберите группу и укажите VRID от 1 до 255.");
    if (
      normalized.length === 0 ||
      normalized.length > 64 ||
      normalized.some(
        (item) =>
          !ipv4.test(item.address) ||
          !item.interface ||
          item.interface.length > 128,
      ) ||
      new Set(
        normalized.map((item) => `${item.address}\\u0000${item.interface}`),
      ).size !== normalized.length
    )
      return setError(
        "Добавьте до 64 уникальных IPv4-адресов с interface длиной не более 128 символов.",
      );
    await onAppend({
      operation: "ReconcileEndpointProvider",
      deploymentId: deployment.id,
      endpointGroupId,
      virtualRouterId: parsedVRID,
      virtualAddresses: normalized,
    });
  };
  return (
    <div
      className="modal"
      role="dialog"
      aria-modal="true"
      aria-label="Настроить provider"
    >
      <section className="card dialog provider-dialog">
        <h2>Provider: {deployment.id}</h2>
        <p className="muted">
          Настройка сохраняется в общий черновик и будет проверена Core только
          после сохранения.
        </p>
        <label>
          Endpoint group
          <select
            value={endpointGroupId}
            onChange={(event) => setEndpointGroupID(event.target.value)}
          >
            <option value="">Выберите группу</option>
            {groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          VRID
          <input
            value={vrid}
            inputMode="numeric"
            onChange={(event) => setVRID(event.target.value)}
          />
        </label>
        <h3>Virtual IP addresses</h3>
        <div className="provider-addresses">
          {addresses.map((item, index) => (
            <div className="provider-address" key={index}>
              <input
                aria-label={`IPv4 ${index + 1}`}
                value={item.address}
                placeholder="192.0.2.42"
                onChange={(event) =>
                  setAddresses((current) =>
                    current.map((row, rowIndex) =>
                      rowIndex === index
                        ? { ...row, address: event.target.value }
                        : row,
                    ),
                  )
                }
              />
              <input
                aria-label={`Interface ${index + 1}`}
                value={item.interface}
                placeholder="eth0"
                maxLength={128}
                onChange={(event) =>
                  setAddresses((current) =>
                    current.map((row, rowIndex) =>
                      rowIndex === index
                        ? { ...row, interface: event.target.value }
                        : row,
                    ),
                  )
                }
              />
              <button
                className="outline danger"
                aria-label={`Удалить адрес ${index + 1}`}
                onClick={() =>
                  setAddresses((current) =>
                    current.filter((_, rowIndex) => rowIndex !== index),
                  )
                }
                disabled={addresses.length === 1}
              >
                Удалить
              </button>
            </div>
          ))}
        </div>
        <button
          className="outline"
          onClick={() =>
            setAddresses((current) =>
              current.length < 64
                ? [...current, { address: "", interface: "" }]
                : current,
            )
          }
          disabled={addresses.length >= 64}
        >
          Добавить адрес
        </button>
        {error && <p className="field-error">{error}</p>}
        <div className="actions">
          <button className="outline" onClick={onClose} disabled={busy}>
            Отмена
          </button>
          <button onClick={() => void submit()} disabled={busy}>
            Применить к черновику
          </button>
        </div>
      </section>
    </div>
  );
}
