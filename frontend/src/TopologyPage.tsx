import { useEffect, useMemo, useState } from "react";
import type { OpenResult } from "./backend";

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
  intents: DeploymentIntent[],
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
    const existing = result.get(intent.deploymentId);
    if (existing)
      result.set(intent.deploymentId, { ...existing, state: "deleting" });
  }
  return [...result.values()].sort((left, right) =>
    left.deploymentId.localeCompare(right.deploymentId),
  );
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
  busy,
  structuralDisabled,
  commandCount,
  onAppend,
  onReview,
  onDiscard,
}: {
  managed: OpenResult["managed"];
  catalog: OpenResult["catalog"];
  intents: DeploymentIntent[];
  busy: boolean;
  structuralDisabled: boolean;
  commandCount: number;
  onAppend: (intent: DeploymentIntent) => Promise<boolean>;
  onReview: () => void;
  onDiscard: () => void;
}) {
  const [dialog, setDialog] = useState<"add" | "delete" | null>(null);
  const [selectedID, setSelectedID] = useState("");
  const [filter, setFilter] = useState("");
  const rows = useMemo(
    () => deploymentRows(managed, intents),
    [managed, intents],
  );
  const normalizedFilter = filter.trim().toLocaleLowerCase("ru");
  const filteredRows = rows.filter((row) => {
    const service = catalogService(catalog, row.serviceType);
    return `${row.deploymentId} ${row.serviceType} ${service?.displayName || ""}`
      .toLocaleLowerCase("ru")
      .includes(normalizedFilter);
  });
  const selected = rows.find((row) => row.deploymentId === selectedID);
  const selectedVisible = filteredRows.some(
    (row) => row.deploymentId === selectedID,
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
    if (selectedID && rows.some((row) => row.deploymentId === selectedID))
      return;
    setSelectedID(rows[0]?.deploymentId || "");
  }, [rows, selectedID]);

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
        <button className="active" aria-selected="true">
          По сервисам
        </button>
        <button disabled title="Будет реализовано в UI-01F4">
          По серверам
        </button>
        <button disabled title="Будет реализовано в UI-01F5">
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
                    className={`topology-row ${selectedID === row.deploymentId ? "selected" : ""} ${row.state ? `draft-${row.state}` : ""}`}
                    onClick={() => setSelectedID(row.deploymentId)}
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
              Выбранный deployment скрыт фильтром. Очистите поиск, чтобы открыть
              подробности.
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
              setSelectedID(intent.deploymentId);
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
    </>
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
