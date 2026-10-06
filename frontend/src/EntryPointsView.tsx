import { useMemo, useState } from "react";
import type { EndpointPreview, OpenResult } from "./backend";
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
  verificationStatus: NonNullable<OpenResult["verification"]>["status"];
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
  const previewStatus = preview?.status || "NOT_VERIFIED";
  return (
    <>
      <section className="title topology-title">
        <div>
          <h1>Точки входа</h1>
          <p>
            Группы адресов, назначения потребителей и read-only результат Core.
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
        <section className="card">
          <h2>Группы endpoint</h2>
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
                      <small>
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
        <section className="card entry-consumers">
          <h2>Назначения consumers</h2>
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
                  return (
                    <div key={deployment.id} className="entry-row">
                      <div>
                        <b>{deployment.id}</b>
                        <span>
                          {deployment.serviceType} ·{" "}
                          {deployment.endpointGroup || "не назначена"}
                        </span>
                        {!canSet && (
                          <small>
                            {catalogReady
                              ? "Сервис не поддерживает endpoint consumer"
                              : "Каталог недоступен"}
                          </small>
                        )}
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
        <section className="card">
          <h2>Provider / VIP</h2>
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
                return (
                  <div key={deployment.id} className="entry-row">
                    <div>
                      <b>{deployment.id}</b>
                      <span>
                        {deployment.endpointGroupRef
                          ? `${deployment.endpointGroupRef} · VRID ${deployment.virtualRouterId || "—"}`
                          : "Provider не настроен"}
                      </span>
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
        <PreviewCard
          preview={preview}
          status={previewStatus}
          verificationStatus={verificationStatus}
          providerChangePending={providerIntents.length !== 0}
        />
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

function PreviewCard({
  preview,
  status,
  verificationStatus,
  providerChangePending,
}: {
  preview?: EndpointPreview;
  status: string;
  verificationStatus: NonNullable<OpenResult["verification"]>["status"];
  providerChangePending: boolean;
}) {
  if (status !== "CURRENT")
    return (
      <section className="card">
        <h2>Результат Core</h2>
        <p className="muted">
          {status === "INVALID"
            ? "Проверка выявила ошибки. Адреса и provider/VIP не показаны."
            : status === "STALE"
              ? providerChangePending
                ? "Конфигурация provider изменена в черновике. Проверка устарела; влияние на PKI/SAN определяет только Core после сохранения и проверки."
                : "Проверка устарела из-за черновика или смены Execution Node."
              : verificationStatus === "VERIFYING"
                ? "Core проверяет сохранённую ревизию проекта."
                : status === "UNAVAILABLE"
                  ? preview?.error?.message || "Read-only preview недоступен."
                  : "Сохраните проект и выполните Проверить."}
        </p>
        {status === "INVALID" &&
          preview?.findings?.map((finding) => (
            <p
              className="field-error"
              key={`${finding.code}-${finding.subjectId || ""}`}
            >
              {finding.code}: {finding.summary}
            </p>
          ))}
      </section>
    );
  return (
    <section className="card">
      <h2>Результат Core</h2>
      <p className="muted">
        Актуальные FQDN и provider/VIP получены из последней проверки Core.
        Редактор не выводит влияние на PKI/SAN самостоятельно.
      </p>
      {preview?.endpoints?.length ? (
        <>
          <h3>FQDN</h3>
          {preview.endpoints.map((item) => (
            <p key={item.deploymentId}>
              <b>{item.deploymentId}</b> · {item.fqdn}
            </p>
          ))}
        </>
      ) : (
        <p className="muted">Core не вернул FQDN.</p>
      )}
      <h3>Providers / VIP</h3>
      {preview?.providers?.length ? (
        preview.providers.map((item) => (
          <div
            className="entry-preview"
            key={`${item.endpointGroupId}-${item.providerDeploymentId}`}
          >
            <b>{item.providerDeploymentId}</b>
            <span>
              {item.endpointGroupRef} · VRID {item.virtualRouterId}
            </span>
            {item.virtualAddresses.map((address) => (
              <small key={`${address.address}-${address.interface}`}>
                {address.address} · {address.interface}
              </small>
            ))}
          </div>
        ))
      ) : (
        <p className="muted">Core не вернул provider/VIP.</p>
      )}
      {preview?.truncated && (
        <p className="muted">Показана ограниченная часть результата.</p>
      )}
    </section>
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
