import { useEffect, useMemo, useState } from "react";
import type { EndpointPreview, OpenResult } from "./backend";
import { type EndpointIntent, EntryPointsView } from "./EntryPointsView";
import type { ServerIntent } from "./ServersPage";

export type { EndpointIntent } from "./EntryPointsView";

export type DeploymentIntent =
  | {
      operation: "CreateServiceDeployment";
      deploymentId: string;
      serviceType: string;
      mode: string;
    }
  | {
      operation: "DeleteServiceDeployment";
      deploymentId: string;
    };

export type PlacementIntent =
  | {
      operation: "ReconcileDeploymentPlacement";
      deploymentId: string;
      members: Array<{ memberId: string; hostId: string; roles?: string[] }>;
    }
  | {
      operation: "ReconcileHostScopedDeploymentPlacement";
      deploymentId: string;
      hosts: Array<{ hostId: string; roles?: string[] }>;
    };
type TopologyIntent = DeploymentIntent | PlacementIntent | EndpointIntent;

type CatalogService = NonNullable<OpenResult["catalog"]>["services"] extends
  Array<infer Service> | undefined
  ? Service
  : never;
type CatalogMode = CatalogService["modes"][number];

type DeploymentRow = {
  deploymentId: string;
  serviceType: string;
  mode: string;
  state?: "new" | "deleting";
};

function deploymentRows(
  managed: OpenResult["managed"],
  intents: TopologyIntent[],
): DeploymentRow[] {
  const result = new Map<string, DeploymentRow>();
  for (const [deploymentId, deployment] of Object.entries(
    managed?.deployments || {},
  )) {
    result.set(deploymentId, {
      deploymentId,
      serviceType: deployment.serviceType,
      mode: deployment.mode,
    });
  }
  for (const intent of intents) {
    if (intent.operation === "CreateServiceDeployment") {
      result.set(intent.deploymentId, {
        deploymentId: intent.deploymentId,
        serviceType: intent.serviceType,
        mode: intent.mode,
        state: "new",
      });
      continue;
    }
    if (intent.operation !== "DeleteServiceDeployment") continue;
    const existing = result.get(intent.deploymentId);
    if (existing)
      result.set(intent.deploymentId, { ...existing, state: "deleting" });
  }
  return [...result.values()].sort((left, right) =>
    left.deploymentId.localeCompare(right.deploymentId),
  );
}

type ServerRow = { hostId: string; label: string; state?: "new" | "deleting" };
type MemberRow = { memberId: string; hostId: string; roles: string[] };
type HostRow = { hostId: string; roles: string[] };
type Placement =
  | { kind: "MEMBER_SCOPED"; members: MemberRow[] }
  | { kind: "HOST_SCOPED"; hosts: HostRow[] };

function finalServers(
  managed: OpenResult["managed"],
  intents: ServerIntent[],
): ServerRow[] {
  const rows = new Map<string, ServerRow>();
  for (const [hostId, host] of Object.entries(managed?.servers || {}))
    rows.set(hostId, {
      hostId,
      label: host.address ? `${hostId} · ${host.address}` : hostId,
    });
  for (const intent of intents) {
    const existing = rows.get(intent.hostId);
    if (intent.operation === "CreateServer")
      rows.set(intent.hostId, {
        hostId: intent.hostId,
        label: intent.address
          ? `${intent.hostId} · ${String(intent.address)}`
          : intent.hostId,
        state: "new",
      });
    else if (intent.operation === "DeleteServer" && existing)
      rows.set(intent.hostId, { ...existing, state: "deleting" });
  }
  return [...rows.values()].sort((a, b) => a.hostId.localeCompare(b.hostId));
}

function finalPlacements(
  managed: OpenResult["managed"],
  intents: TopologyIntent[],
): Map<string, Placement> {
  const result = new Map<string, Placement>();
  for (const item of managed?.memberPlacements || []) {
    const current = result.get(item.deploymentId);
    const members = current?.kind === "MEMBER_SCOPED" ? current.members : [];
    result.set(item.deploymentId, {
      kind: "MEMBER_SCOPED",
      members: [
        ...members,
        {
          memberId: item.memberId,
          hostId: item.hostId,
          roles: item.roles || [],
        },
      ],
    });
  }
  for (const item of managed?.hostPlacements || []) {
    const current = result.get(item.deploymentId);
    const hosts = current?.kind === "HOST_SCOPED" ? current.hosts : [];
    result.set(item.deploymentId, {
      kind: "HOST_SCOPED",
      hosts: [...hosts, { hostId: item.hostId, roles: item.roles || [] }],
    });
  }
  for (const intent of intents) {
    if (intent.operation === "ReconcileDeploymentPlacement")
      result.set(intent.deploymentId, {
        kind: "MEMBER_SCOPED",
        members: intent.members.map((item) => ({
          ...item,
          roles: item.roles || [],
        })),
      });
    if (intent.operation === "ReconcileHostScopedDeploymentPlacement")
      result.set(intent.deploymentId, {
        kind: "HOST_SCOPED",
        hosts: intent.hosts.map((item) => ({
          ...item,
          roles: item.roles || [],
        })),
      });
  }
  return result;
}

function catalogService(
  catalog: OpenResult["catalog"],
  serviceType: string,
): CatalogService | undefined {
  return catalog?.services?.find((service) => service.id === serviceType);
}

function catalogMode(
  service: CatalogService | undefined,
  mode: string,
): CatalogMode | undefined {
  return service?.modes.find((item) => item.id === mode);
}

function serviceLabel(service: CatalogService | undefined, id: string) {
  return service
    ? `${service.displayName} (${id})`
    : `Неизвестный сохранённый тип (${id})`;
}

function modeLabel(mode: CatalogMode | undefined, id: string) {
  return mode
    ? `${mode.displayName} (${id})`
    : `Неизвестный сохранённый режим (${id})`;
}

export function TopologyPage({
  managed,
  catalog,
  intents,
  serverIntents,
  busy,
  structuralDisabled,
  commandCount,
  onAppend,
  onReview,
  onDiscard,
  activeTab,
  onActiveTabChange,
  selectedDeploymentId,
  onSelectedDeploymentChange,
  selectedHostId,
  onSelectedHostChange,
  preview,
}: {
  managed: OpenResult["managed"];
  catalog: OpenResult["catalog"];
  intents: TopologyIntent[];
  serverIntents: ServerIntent[];
  busy: boolean;
  structuralDisabled: boolean;
  commandCount: number;
  onAppend: (intent: TopologyIntent) => Promise<boolean>;
  onReview: () => void;
  onDiscard: () => void;
  activeTab: "services" | "servers" | "entryPoints";
  onActiveTabChange: (tab: "services" | "servers" | "entryPoints") => void;
  selectedDeploymentId: string;
  onSelectedDeploymentChange: (id: string) => void;
  selectedHostId: string;
  onSelectedHostChange: (id: string) => void;
  preview?: EndpointPreview;
}) {
  const [dialog, setDialog] = useState<"add" | "delete" | "placement" | null>(
    null,
  );
  const [placementHostContext, setPlacementHostContext] = useState("");
  const [placementDeploymentId, setPlacementDeploymentId] = useState("");
  const [filter, setFilter] = useState("");
  const rows = useMemo(
    () => deploymentRows(managed, intents),
    [managed, intents],
  );
  const servers = useMemo(
    () => finalServers(managed, serverIntents),
    [managed, serverIntents],
  );
  const placements = useMemo(
    () => finalPlacements(managed, intents),
    [managed, intents],
  );
  const normalizedFilter = filter.trim().toLocaleLowerCase("ru");
  const filteredRows = rows.filter((row) => {
    const service = catalogService(catalog, row.serviceType);
    return `${row.deploymentId} ${row.serviceType} ${service?.displayName || ""}`
      .toLocaleLowerCase("ru")
      .includes(normalizedFilter);
  });
  const selected = rows.find(
    (row) => row.deploymentId === selectedDeploymentId,
  );
  const selectedVisible = filteredRows.some(
    (row) => row.deploymentId === selectedDeploymentId,
  );
  const selectedService = selected
    ? catalogService(catalog, selected.serviceType)
    : undefined;
  const selectedMode = selected
    ? catalogMode(selectedService, selected.mode)
    : undefined;
  const catalogReady = catalog?.status === "READY";
  const commandLimitReached = commandCount >= 16;
  const crudDisabled = busy || structuralDisabled;

  useEffect(() => {
    if (
      selectedDeploymentId &&
      rows.some((row) => row.deploymentId === selectedDeploymentId)
    )
      return;
    onSelectedDeploymentChange(rows[0]?.deploymentId || "");
  }, [rows, selectedDeploymentId, onSelectedDeploymentChange]);

  useEffect(() => {
    if (selectedHostId && servers.some((row) => row.hostId === selectedHostId))
      return;
    onSelectedHostChange(servers[0]?.hostId || "");
  }, [servers, selectedHostId, onSelectedHostChange]);

  const placementLocked =
    !!selected &&
    intents.some(
      (intent) =>
        (intent.operation === "ReconcileDeploymentPlacement" ||
          intent.operation === "ReconcileHostScopedDeploymentPlacement") &&
        intent.deploymentId === selected.deploymentId,
    );
  const placementTarget = rows.find(
    (row) => row.deploymentId === placementDeploymentId,
  );

  return (
    <>
      <section className="title topology-title">
        <div>
          <h1>Топология</h1>
          <p>Экземпляры сервисов и их размещение в проекте.</p>
        </div>
        <button
          onClick={() => setDialog("add")}
          disabled={crudDisabled || !catalogReady || commandLimitReached}
          title={
            commandLimitReached
              ? "Достигнут общий лимит 16 изменений. Сохраните или отмените черновик."
              : undefined
          }
        >
          Добавить экземпляр
        </button>
      </section>

      <nav className="topology-tabs" aria-label="Представления топологии">
        <button
          className={activeTab === "services" ? "active" : "outline"}
          aria-selected={activeTab === "services"}
          onClick={() => onActiveTabChange("services")}
        >
          По сервисам
        </button>
        <button
          className={activeTab === "servers" ? "active" : "outline"}
          aria-selected={activeTab === "servers"}
          onClick={() => onActiveTabChange("servers")}
        >
          По серверам
        </button>
        <button
          className={activeTab === "entryPoints" ? "active" : "outline"}
          aria-selected={activeTab === "entryPoints"}
          onClick={() => onActiveTabChange("entryPoints")}
        >
          Точки входа
        </button>
      </nav>

      {!catalogReady && (
        <section className="card topology-warning" role="status">
          <b>Каталог недоступен: новые экземпляры нельзя добавить.</b>
          <p>
            Сохранённые deployment остаются видимыми, а guarded Delete доступен.
            {catalog?.error?.message ? ` ${catalog.error.message}` : ""}
          </p>
        </section>
      )}

      {activeTab === "entryPoints" ? (
        <EntryPointsView
          managed={managed}
          catalog={catalog}
          intents={intents.filter(
            (intent): intent is EndpointIntent =>
              intent.operation === "CreateEndpointGroup" ||
              intent.operation === "UpdateEndpointGroup" ||
              intent.operation === "DeleteEndpointGroup" ||
              intent.operation === "SetServiceEndpointGroup" ||
              intent.operation === "ClearServiceEndpointGroup",
          )}
          deploymentIntents={intents.filter(
            (intent): intent is DeploymentIntent =>
              intent.operation === "CreateServiceDeployment" ||
              intent.operation === "DeleteServiceDeployment",
          )}
          preview={preview}
          busy={busy}
          disabled={crudDisabled}
          commandCount={commandCount}
          onAppend={onAppend}
        />
      ) : activeTab === "services" ? (
        <div className="topology-grid">
          <section className="card topology-list">
            <h2>Deployments</h2>
            <label>
              Поиск
              <input
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="ID или сервис"
              />
            </label>
            <div className="topology-list-scroll">
              {filteredRows.length === 0 ? (
                <p className="muted">
                  {rows.length === 0
                    ? "Экземпляров сервисов пока нет."
                    : "По фильтру ничего не найдено."}
                </p>
              ) : (
                filteredRows.map((row) => {
                  const service = catalogService(catalog, row.serviceType);
                  return (
                    <button
                      key={row.deploymentId}
                      className={`topology-row ${selectedDeploymentId === row.deploymentId ? "selected" : ""} ${row.state ? `draft-${row.state}` : ""}`}
                      onClick={() =>
                        onSelectedDeploymentChange(row.deploymentId)
                      }
                    >
                      <b>{row.deploymentId}</b>
                      <span>{service?.displayName || row.serviceType}</span>
                      {row.state && (
                        <small>
                          {row.state === "new" ? "Новый" : "Будет удалён"}
                        </small>
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </section>

          <section className="card topology-detail">
            <h2>Выбранный deployment</h2>
            {!selected ? (
              <p className="muted">Выберите или добавьте экземпляр сервиса.</p>
            ) : !selectedVisible ? (
              <p className="muted">
                Выбранный deployment скрыт фильтром. Очистите поиск, чтобы
                открыть подробности.
              </p>
            ) : (
              <>
                <dl>
                  <dt>ID</dt>
                  <dd>{selected.deploymentId}</dd>
                  <dt>Сервис</dt>
                  <dd>{serviceLabel(selectedService, selected.serviceType)}</dd>
                  <dt>Режим</dt>
                  <dd>{modeLabel(selectedMode, selected.mode)}</dd>
                  <dt>Размещение</dt>
                  <dd>
                    {selectedMode?.placementKind || "Недоступно без каталога"}
                  </dd>
                  <dt>Состояние</dt>
                  <dd>
                    {selected.state === "new"
                      ? "Новый черновик"
                      : selected.state === "deleting"
                        ? "Будет удалён"
                        : "Сохранён"}
                  </dd>
                </dl>
                <div className="actions topology-actions">
                  <button
                    onClick={() => {
                      setPlacementHostContext("");
                      setPlacementDeploymentId(selected.deploymentId);
                      setDialog("placement");
                    }}
                    disabled={
                      crudDisabled ||
                      !!selected.state ||
                      placementLocked ||
                      commandLimitReached ||
                      (!catalogReady && !placements.has(selected.deploymentId))
                    }
                    title={
                      placementLocked
                        ? "Размещение этого deployment уже добавлено в текущий черновик."
                        : undefined
                    }
                  >
                    {placements.has(selected.deploymentId)
                      ? "Изменить размещение"
                      : "Добавить размещение"}
                  </button>
                  {placements.has(selected.deploymentId) && (
                    <button
                      className="outline"
                      onClick={() => {
                        setPlacementHostContext("");
                        setPlacementDeploymentId(selected.deploymentId);
                        setDialog("placement");
                      }}
                      disabled={
                        crudDisabled ||
                        !!selected.state ||
                        placementLocked ||
                        commandLimitReached
                      }
                    >
                      Очистить размещение
                    </button>
                  )}
                  <button
                    className="outline"
                    disabled
                    title="Редактор сервиса будет реализован отдельным milestone"
                  >
                    Настроить сервис
                  </button>
                  <button
                    className="outline danger"
                    onClick={() => setDialog("delete")}
                    disabled={
                      crudDisabled || !!selected.state || commandLimitReached
                    }
                  >
                    Удалить deployment
                  </button>
                </div>
              </>
            )}
          </section>

          <section className="card topology-summary">
            <h2>Состояние топологии</h2>
            <dl>
              <dt>Deployments</dt>
              <dd>{rows.filter((row) => row.state !== "deleting").length}</dd>
              <dt>Черновик</dt>
              <dd>{commandCount} / 16 изменений</dd>
              <dt>Размещение</dt>
              <dd>UI-01F4</dd>
              <dt>Проверка Core</dt>
              <dd>Запускается отдельно после сохранения</dd>
            </dl>
            <p className="muted">
              F3 не рассчитывает members, роли, cardinality или результат Core.
            </p>
          </section>
        </div>
      ) : (
        <ByServersView
          servers={servers}
          rows={rows}
          placements={placements}
          selectedHostId={selectedHostId}
          onSelectedHostChange={onSelectedHostChange}
          onSelectedDeploymentChange={onSelectedDeploymentChange}
          onEdit={(deploymentId, hostId) => {
            onSelectedDeploymentChange(deploymentId);
            setPlacementHostContext(hostId);
            setPlacementDeploymentId(deploymentId);
            setDialog("placement");
          }}
          disabled={crudDisabled || commandLimitReached}
          placementLocked={(deploymentId) =>
            intents.some(
              (intent) =>
                (intent.operation === "ReconcileDeploymentPlacement" ||
                  intent.operation ===
                    "ReconcileHostScopedDeploymentPlacement") &&
                intent.deploymentId === deploymentId,
            )
          }
        />
      )}

      {commandCount > 0 && (
        <section className="card draft-actions">
          <p>
            Общий черновик: {commandCount} / 16. Файлы изменятся только после
            локального Review и общего сохранения.
          </p>
          <button className="outline" onClick={onDiscard} disabled={busy}>
            Отменить все изменения
          </button>
          <button onClick={onReview} disabled={busy}>
            Просмотреть изменения
          </button>
        </section>
      )}

      {dialog === "add" && (
        <AddDeploymentDialog
          services={catalog?.services || []}
          existingIDs={new Set(rows.map((row) => row.deploymentId))}
          busy={busy}
          onClose={() => setDialog(null)}
          onAppend={async (intent) => {
            const accepted = await onAppend(intent);
            if (accepted) {
              onSelectedDeploymentChange(intent.deploymentId);
              setDialog(null);
            }
            return accepted;
          }}
        />
      )}

      {dialog === "delete" && selected && (
        <DeleteDeploymentDialog
          row={selected}
          busy={busy}
          onClose={() => setDialog(null)}
          onAppend={async (intent) => {
            const accepted = await onAppend(intent);
            if (accepted) setDialog(null);
            return accepted;
          }}
        />
      )}
      {dialog === "placement" && placementTarget && (
        <PlacementDialog
          row={placementTarget}
          mode={catalogMode(
            catalogService(catalog, placementTarget.serviceType),
            placementTarget.mode,
          )}
          placement={placements.get(placementTarget.deploymentId)}
          servers={servers}
          preferredHostId={placementHostContext}
          busy={busy}
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

function ByServersView({
  servers,
  rows,
  placements,
  selectedHostId,
  onSelectedHostChange,
  onSelectedDeploymentChange,
  onEdit,
  disabled,
  placementLocked,
}: {
  servers: ServerRow[];
  rows: DeploymentRow[];
  placements: Map<string, Placement>;
  selectedHostId: string;
  onSelectedHostChange: (id: string) => void;
  onSelectedDeploymentChange: (id: string) => void;
  onEdit: (deploymentId: string, hostId: string) => void;
  disabled: boolean;
  placementLocked: (deploymentId: string) => boolean;
}) {
  const selected = servers.find((server) => server.hostId === selectedHostId);
  const assignments = rows.flatMap((deployment) => {
    const placement = placements.get(deployment.deploymentId);
    if (placement?.kind === "MEMBER_SCOPED")
      return placement.members
        .filter((member) => member.hostId === selectedHostId)
        .map((member) => ({
          deployment,
          key: `member:${member.memberId}`,
          text: `${member.memberId}${member.roles.length ? ` · ${member.roles.join(", ")}` : ""}`,
        }));
    if (placement?.kind === "HOST_SCOPED")
      return placement.hosts
        .filter((host) => host.hostId === selectedHostId)
        .map((host) => ({
          deployment,
          key: `host:${host.hostId}`,
          text: host.roles.join(", ") || "без ролей",
        }));
    return [];
  });
  return (
    <div className="topology-grid topology-servers-grid">
      <section className="card topology-list">
        <h2>Серверы</h2>
        <div className="topology-list-scroll">
          {servers.map((server) => (
            <button
              key={server.hostId}
              className={`topology-row ${server.hostId === selectedHostId ? "selected" : ""}`}
              onClick={() => onSelectedHostChange(server.hostId)}
            >
              <b>{server.hostId}</b>
              <span>{server.label}</span>
              {server.state && (
                <small>
                  {server.state === "new" ? "Новый" : "Будет удалён"}
                </small>
              )}
            </button>
          ))}
        </div>
      </section>
      <section className="card topology-detail">
        <h2>Размещение на сервере</h2>
        {!selected ? (
          <p className="muted">Добавьте сервер или выберите его в списке.</p>
        ) : selected.state === "deleting" ? (
          <p className="muted">
            Сервер будет удалён и не предлагается для нового размещения.
          </p>
        ) : (
          <>
            <div className="topology-list-scroll">
              {assignments.length === 0 ? (
                <p className="muted">На этом сервере пока нет размещений.</p>
              ) : (
                assignments.map(({ deployment, key, text }) => (
                  <article
                    className="topology-assignment"
                    key={`${deployment.deploymentId}:${key}`}
                  >
                    <b>{deployment.deploymentId}</b>
                    <span>{text}</span>
                    <button
                      className="outline"
                      onClick={() => {
                        onSelectedDeploymentChange(deployment.deploymentId);
                        onEdit(deployment.deploymentId, selected.hostId);
                      }}
                      disabled={
                        disabled ||
                        !!deployment.state ||
                        placementLocked(deployment.deploymentId)
                      }
                    >
                      Изменить
                    </button>
                  </article>
                ))
              )}
            </div>
            <label className="topology-add-placement">
              Добавить размещение
              <select
                aria-label="Deployment для размещения"
                defaultValue=""
                onChange={(event) => {
                  const deploymentId = event.target.value;
                  if (deploymentId) {
                    onSelectedDeploymentChange(deploymentId);
                    onEdit(deploymentId, selected.hostId);
                    event.currentTarget.value = "";
                  }
                }}
                disabled={disabled}
              >
                <option value="">Выберите deployment</option>
                {rows
                  .filter(
                    (row) => !row.state && !placements.has(row.deploymentId),
                  )
                  .map((deployment) => (
                    <option
                      key={deployment.deploymentId}
                      value={deployment.deploymentId}
                    >
                      {deployment.deploymentId}
                    </option>
                  ))}
              </select>
            </label>
          </>
        )}
      </section>
      <section className="card topology-summary">
        <h2>Сводка</h2>
        <dl>
          <dt>Сервер</dt>
          <dd>{selected?.hostId || "—"}</dd>
          <dt>Размещений</dt>
          <dd>{assignments.length}</dd>
          <dt>Проверка Core</dt>
          <dd>После сохранения</dd>
        </dl>
        <p className="muted">
          Изменение открывает общий editor deployment; отдельной команды для
          сервера нет.
        </p>
      </section>
    </div>
  );
}

function normalizedMemberBase(serviceType: string, suffixLength: number) {
  const normalized = serviceType
    .toLowerCase()
    .replace(/[_.]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized.slice(0, Math.max(0, 63 - suffixLength));
}

function candidateMemberId(serviceType: string, members: MemberRow[]) {
  const used = new Set(members.map((member) => member.memberId));
  for (let n = 1; n < 10000; n += 1) {
    const suffix = `-${n}`;
    const base = normalizedMemberBase(serviceType, suffix.length);
    if (!base) return "";
    const candidate = `${base}${suffix}`;
    if (!used.has(candidate)) return candidate;
  }
  return "";
}

function PlacementDialog({
  row,
  mode,
  placement,
  servers,
  preferredHostId,
  busy,
  onClose,
  onAppend,
}: {
  row: DeploymentRow;
  mode: CatalogMode | undefined;
  placement: Placement | undefined;
  servers: ServerRow[];
  preferredHostId: string;
  busy: boolean;
  onClose: () => void;
  onAppend: (intent: PlacementIntent) => Promise<boolean>;
}) {
  const kind = mode?.placementKind as
    "MEMBER_SCOPED" | "HOST_SCOPED" | undefined;
  const [members, setMembers] = useState<MemberRow[]>(
    placement?.kind === "MEMBER_SCOPED" ? placement.members : [],
  );
  const [hosts, setHosts] = useState<HostRow[]>(
    placement?.kind === "HOST_SCOPED" ? placement.hosts : [],
  );
  const [error, setError] = useState("");
  const selectable = servers.filter((server) => server.state !== "deleting");
  const roleOptions = mode?.roles || [];
  const addMember = () => {
    const hostId =
      preferredHostId &&
      selectable.some((server) => server.hostId === preferredHostId)
        ? preferredHostId
        : selectable[0]?.hostId || "";
    setMembers((current) => [
      ...current,
      {
        memberId: candidateMemberId(row.serviceType, current),
        hostId,
        roles: [],
      },
    ]);
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!kind) {
      setError("Для непустого размещения требуется READY catalog.");
      return;
    }
    if (kind === "MEMBER_SCOPED") {
      const ids = new Set<string>();
      if (
        members.some(
          (member) =>
            !/^[a-z0-9][a-z0-9-]{0,62}$/.test(member.memberId) ||
            !member.hostId ||
            ids.has(member.memberId) ||
            (ids.add(member.memberId), false),
        )
      ) {
        setError("Укажите уникальные member ID и сервер для каждой строки.");
        return;
      }
      if (
        !(await onAppend({
          operation: "ReconcileDeploymentPlacement",
          deploymentId: row.deploymentId,
          members,
        }))
      )
        setError("Размещение не добавлено в общий черновик.");
      return;
    }
    const seen = new Set<string>();
    if (
      hosts.some(
        (host) =>
          !host.hostId ||
          seen.has(host.hostId) ||
          (seen.add(host.hostId), false),
      )
    ) {
      setError("Серверы в host-scoped размещении должны быть уникальны.");
      return;
    }
    if (
      !(await onAppend({
        operation: "ReconcileHostScopedDeploymentPlacement",
        deploymentId: row.deploymentId,
        hosts,
      }))
    )
      setError("Размещение не добавлено в общий черновик.");
  };
  if (!kind)
    return (
      <div className="modal">
        <section className="card dialog">
          <h1>Размещение недоступно</h1>
          <p>Для нового размещения требуется READY catalog.</p>
          {placement && (
            <button
              onClick={async () => {
                const accepted = await onAppend(
                  placement.kind === "MEMBER_SCOPED"
                    ? {
                        operation: "ReconcileDeploymentPlacement",
                        deploymentId: row.deploymentId,
                        members: [],
                      }
                    : {
                        operation: "ReconcileHostScopedDeploymentPlacement",
                        deploymentId: row.deploymentId,
                        hosts: [],
                      },
                );
                if (!accepted)
                  setError("Очистка размещения не добавлена в общий черновик.");
              }}
              disabled={busy}
            >
              Очистить существующее размещение
            </button>
          )}
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          <button className="outline" onClick={onClose}>
            Закрыть
          </button>
        </section>
      </div>
    );
  return (
    <div className="modal" role="presentation">
      <form className="card dialog topology-dialog" onSubmit={submit}>
        <h1>Размещение: {row.deploymentId}</h1>
        <p className="muted">
          {kind === "MEMBER_SCOPED" ? "Members и роли" : "Серверы и роли"}.
          Apply заменяет полное размещение deployment.
        </p>
        {kind === "MEMBER_SCOPED" ? (
          <>
            <div className="placement-rows">
              {members.map((member, index) => (
                <div
                  className="placement-row"
                  key={`${member.memberId}-${index}`}
                >
                  <input
                    aria-label={`Member ID ${index + 1}`}
                    value={member.memberId}
                    placeholder={`${row.serviceType}-1`}
                    onChange={(event) =>
                      setMembers((current) =>
                        current.map((value, i) =>
                          i === index
                            ? { ...value, memberId: event.target.value }
                            : value,
                        ),
                      )
                    }
                  />
                  <select
                    aria-label={`Сервер ${index + 1}`}
                    value={member.hostId}
                    onChange={(event) =>
                      setMembers((current) =>
                        current.map((value, i) =>
                          i === index
                            ? { ...value, hostId: event.target.value }
                            : value,
                        ),
                      )
                    }
                  >
                    {selectable.map((server) => (
                      <option key={server.hostId} value={server.hostId}>
                        {server.hostId}
                      </option>
                    ))}
                  </select>
                  <RoleSelector
                    roles={roleOptions}
                    value={member.roles}
                    onChange={(roles) =>
                      setMembers((current) =>
                        current.map((value, i) =>
                          i === index ? { ...value, roles } : value,
                        ),
                      )
                    }
                  />
                  <button
                    type="button"
                    className="outline"
                    onClick={() =>
                      setMembers((current) =>
                        current.filter((_, i) => i !== index),
                      )
                    }
                  >
                    Удалить
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="outline"
              onClick={addMember}
              disabled={!selectable.length}
            >
              Добавить member
            </button>
          </>
        ) : (
          <>
            <div className="placement-rows">
              {hosts.map((host, index) => (
                <div className="placement-row" key={`${host.hostId}-${index}`}>
                  <select
                    aria-label={`Сервер ${index + 1}`}
                    value={host.hostId}
                    onChange={(event) =>
                      setHosts((current) =>
                        current.map((value, i) =>
                          i === index
                            ? { ...value, hostId: event.target.value }
                            : value,
                        ),
                      )
                    }
                  >
                    {selectable.map((server) => (
                      <option key={server.hostId} value={server.hostId}>
                        {server.hostId}
                      </option>
                    ))}
                  </select>
                  <RoleSelector
                    roles={roleOptions}
                    value={host.roles}
                    onChange={(roles) =>
                      setHosts((current) =>
                        current.map((value, i) =>
                          i === index ? { ...value, roles } : value,
                        ),
                      )
                    }
                  />
                  <button
                    type="button"
                    className="outline"
                    onClick={() =>
                      setHosts((current) =>
                        current.filter((_, i) => i !== index),
                      )
                    }
                  >
                    Удалить
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="outline"
              onClick={() =>
                setHosts((current) => [
                  ...current,
                  {
                    hostId: preferredHostId || selectable[0]?.hostId || "",
                    roles: [],
                  },
                ])
              }
              disabled={!selectable.length}
            >
              Добавить сервер
            </button>
          </>
        )}
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <div className="actions">
          <button
            type="button"
            className="outline"
            onClick={onClose}
            disabled={busy}
          >
            Отмена
          </button>
          <button type="submit" disabled={busy}>
            Применить
          </button>
        </div>
      </form>
    </div>
  );
}

function RoleSelector({
  roles,
  value,
  onChange,
}: {
  roles: string[];
  value: string[];
  onChange: (roles: string[]) => void;
}) {
  if (!roles.length) return <span className="muted">Без ролей</span>;
  return (
    <label className="role-selector">
      Роли
      <select
        multiple
        value={value}
        onChange={(event) =>
          onChange(
            [...event.currentTarget.selectedOptions].map(
              (option) => option.value,
            ),
          )
        }
      >
        {roles.map((role) => (
          <option key={role} value={role}>
            {role}
          </option>
        ))}
      </select>
    </label>
  );
}

function AddDeploymentDialog({
  services,
  existingIDs,
  busy,
  onClose,
  onAppend,
}: {
  services: CatalogService[];
  existingIDs: Set<string>;
  busy: boolean;
  onClose: () => void;
  onAppend: (
    intent: DeploymentIntent & { operation: "CreateServiceDeployment" },
  ) => Promise<boolean>;
}) {
  const [deploymentID, setDeploymentID] = useState("");
  const [serviceType, setServiceType] = useState(services[0]?.id || "");
  const selectedService = services.find(
    (service) => service.id === serviceType,
  );
  const [mode, setMode] = useState(selectedService?.modes[0]?.id || "");
  const [error, setError] = useState("");
  const selectedMode = selectedService?.modes.find((item) => item.id === mode);

  const selectService = (id: string) => {
    setServiceType(id);
    const next = services.find((service) => service.id === id);
    setMode(next?.modes[0]?.id || "");
    setError("");
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const id = deploymentID.trim();
    if (!/^[a-z0-9][a-z0-9-]{0,62}$/.test(id)) {
      setError("ID: 1–63 символа, строчные латинские буквы, цифры и дефис.");
      return;
    }
    if (existingIDs.has(id)) {
      setError(
        "Deployment с таким ID уже есть в сохранённом состоянии или черновике.",
      );
      return;
    }
    if (!serviceType || !mode) {
      setError("Выберите сервис и режим.");
      return;
    }
    const accepted = await onAppend({
      operation: "CreateServiceDeployment",
      deploymentId: id,
      serviceType,
      mode,
    });
    if (!accepted) setError("Изменение не добавлено в общий черновик.");
  };

  return (
    <div className="modal" role="presentation">
      <form className="card dialog topology-dialog" onSubmit={submit}>
        <h1>Добавить экземпляр сервиса</h1>
        <label>
          Технический ID deployment
          <input
            value={deploymentID}
            onChange={(event) => {
              setDeploymentID(event.target.value);
              setError("");
            }}
            required
            autoFocus
          />
        </label>
        <small className="muted">ID стабилен и не переименовывается.</small>
        <label>
          Сервис
          <select
            value={serviceType}
            onChange={(event) => selectService(event.target.value)}
          >
            {services.map((service) => (
              <option key={service.id} value={service.id}>
                {service.displayName} ({service.id})
              </option>
            ))}
          </select>
        </label>
        <label>
          Режим
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value)}
          >
            {selectedService?.modes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.displayName} ({item.id})
              </option>
            ))}
          </select>
        </label>
        {selectedMode && (
          <p className="topology-guidance">
            Размещение: <b>{selectedMode.placementKind}</b>
            {selectedMode.description ? ` · ${selectedMode.description}` : ""}
          </p>
        )}
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <p className="muted">
          Размещение, endpoint groups и настройки сервиса здесь не создаются.
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
          <button type="submit" disabled={busy || services.length === 0}>
            Добавить в черновик
          </button>
        </div>
      </form>
    </div>
  );
}

function DeleteDeploymentDialog({
  row,
  busy,
  onClose,
  onAppend,
}: {
  row: DeploymentRow;
  busy: boolean;
  onClose: () => void;
  onAppend: (
    intent: DeploymentIntent & { operation: "DeleteServiceDeployment" },
  ) => Promise<boolean>;
}) {
  const [error, setError] = useState("");
  return (
    <div className="modal" role="presentation">
      <section
        className="card dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-deployment-title"
      >
        <h1 id="delete-deployment-title">Удалить deployment</h1>
        <p>
          <b>{row.deploymentId}</b> будет удалён только после Review и общего
          сохранения. Размещение, endpoint, dependency, provider и certificate
          references автоматически не удаляются.
        </p>
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <div className="actions">
          <button className="outline" onClick={onClose} disabled={busy}>
            Отмена
          </button>
          <button
            className="danger-button outline"
            disabled={busy}
            onClick={async () => {
              const accepted = await onAppend({
                operation: "DeleteServiceDeployment",
                deploymentId: row.deploymentId,
              });
              if (!accepted)
                setError("Удаление не добавлено в общий черновик.");
            }}
          >
            Удалить deployment
          </button>
        </div>
      </section>
    </div>
  );
}
