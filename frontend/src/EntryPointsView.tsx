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
) {
  const values = new Map<string, Deployment>();
  for (const [id, item] of Object.entries(managed?.deployments || {}))
    values.set(id, {
      id,
      serviceType: item.serviceType,
      mode: item.mode,
      endpointGroup: item.endpointGroup,
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
  return [...values.values()].sort((a, b) => a.id.localeCompare(b.id));
}

export function EntryPointsView({
  managed,
  catalog,
  intents,
  deploymentIntents,
  preview,
  busy,
  disabled,
  commandCount,
  onAppend,
}: {
  managed: OpenResult["managed"];
  catalog: OpenResult["catalog"];
  intents: EndpointIntent[];
  deploymentIntents: DeploymentIntent[];
  preview?: EndpointPreview;
  busy: boolean;
  disabled: boolean;
  commandCount: number;
  onAppend: (intent: EndpointIntent) => Promise<boolean>;
}) {
  const [dialog, setDialog] = useState<{
    mode: "add" | "edit";
    group?: Group;
  } | null>(null);
  const groups = useMemo(
    () => finalGroups(managed, intents),
    [managed, intents],
  );
  const deployments = useMemo(
    () => finalDeployments(managed, deploymentIntents, intents),
    [managed, deploymentIntents, intents],
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
  const previewStatus = preview?.status || "NOT_VERIFIED";
  return (
    <>
      <section className="title topology-title">
        <div>
          <h1>Точки входа</h1>
          <p>
            Группы адресов, назначения потребителей и read-only результат Core.
          </p>
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
        <section className="card">
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
        <PreviewCard preview={preview} status={previewStatus} />
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
    </>
  );
}

function PreviewCard({
  preview,
  status,
}: {
  preview?: EndpointPreview;
  status: string;
}) {
  if (status !== "CURRENT")
    return (
      <section className="card">
        <h2>Результат Core</h2>
        <p className="muted">
          {status === "INVALID"
            ? "Проверка выявила ошибки. Адреса и provider/VIP не показаны."
            : status === "STALE"
              ? "Проверка устарела из-за черновика или смены Execution Node."
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
