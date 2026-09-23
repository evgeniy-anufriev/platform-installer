import { useEffect, useMemo, useRef, useState } from "react";
import type { OpenResult } from "./backend";
import type { CertificateIntent } from "./CertificatesPage";
import type { DeploymentIntent, PlacementIntent } from "./TopologyPage";

export type ConfigurationIntent =
  | {
      operation: "SetServiceConfigurationValue";
      deploymentId: string;
      scope: "DEPLOYMENT" | "MEMBER";
      memberId?: string;
      setting: string;
      value: string | number | boolean;
    }
  | {
      operation: "RemoveServiceConfigurationOverride";
      deploymentId: string;
      scope: "DEPLOYMENT" | "MEMBER";
      memberId?: string;
      setting: string;
    };

type CatalogService = NonNullable<OpenResult["catalog"]>["services"] extends
  Array<infer Service> | undefined
  ? Service
  : never;
type CatalogSetting = CatalogService["configurationSettings"][number];
type Row = {
  deploymentId: string;
  serviceType: string;
  mode: string;
  state?: "new" | "deleting";
};
type Value = string | number | boolean;
type Scope = "DEPLOYMENT" | "MEMBER";
type MemberRow = {
  deploymentId: string;
  memberId: string;
  hostId: string;
  roles: string[];
  configuration: Array<{
    setting: string;
    overridePresent: boolean;
    state: string;
    value?: Value;
  }>;
};

const supportedShapes = new Set([
  "BOOLEAN",
  "INTEGER",
  "NUMBER",
  "ENUM",
  "BOUNDED_STRING",
  "DNS_DOMAIN",
]);

const dnsDomainPattern =
  /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z]{2,63}$/;

function invalidText(setting: CatalogSetting, raw: string) {
  return setting.editorShape === "DNS_DOMAIN" && !dnsDomainPattern.test(raw);
}

function rowsFor(
  managed: OpenResult["managed"],
  intents: DeploymentIntent[],
): Row[] {
  const rows = new Map<string, Row>();
  for (const deployment of Object.values(managed?.deployments || {}))
    rows.set(deployment.deploymentId, {
      deploymentId: deployment.deploymentId,
      serviceType: deployment.serviceType,
      mode: deployment.mode,
    });
  for (const intent of intents) {
    if (intent.operation === "CreateServiceDeployment") {
      rows.set(intent.deploymentId, {
        deploymentId: intent.deploymentId,
        serviceType: intent.serviceType,
        mode: intent.mode,
        state: "new",
      });
      continue;
    }
    const row = rows.get(intent.deploymentId);
    if (row) rows.set(intent.deploymentId, { ...row, state: "deleting" });
  }
  return [...rows.values()].sort((left, right) =>
    left.deploymentId.localeCompare(right.deploymentId),
  );
}

function catalogService(
  catalog: OpenResult["catalog"],
  serviceType: string,
): CatalogService | undefined {
  return catalog?.services?.find((service) => service.id === serviceType);
}

function settingValue(
  overrides: Array<{
    setting: string;
    overridePresent: boolean;
    state: string;
    value?: Value;
  }>,
  deploymentId: string,
  scope: Scope,
  memberId: string,
  setting: string,
  intents: ConfigurationIntent[],
): { overridePresent: boolean; state: string; value?: Value } {
  const saved = overrides.find((entry) => entry.setting === setting);
  let result = {
    overridePresent: saved?.overridePresent || false,
    state: saved?.state || "EDITABLE",
    value: saved?.value,
  };
  for (const intent of intents) {
    if (
      intent.deploymentId !== deploymentId ||
      intent.scope !== scope ||
      (scope === "MEMBER" && intent.memberId !== memberId) ||
      intent.setting !== setting
    )
      continue;
    result =
      intent.operation === "SetServiceConfigurationValue"
        ? { overridePresent: true, state: "EDITABLE", value: intent.value }
        : { overridePresent: false, state: "EDITABLE", value: undefined };
  }
  return result;
}

function isEditable(setting: CatalogSetting, catalogReady: boolean) {
  return (
    catalogReady &&
    setting.kind === "MANAGED" &&
    (supportedShapes.has(setting.editorShape) ||
      (setting.editorShape === "TLS_PROFILE" &&
        setting.referenceKind === "TLS_PROFILE") ||
      (setting.editorShape === "SERVICE_DEPLOYMENT" &&
        setting.referenceKind === "SERVICE_DEPLOYMENT"))
  );
}

function finalMembers(
  managed: OpenResult["managed"],
  intents: PlacementIntent[],
  deploymentId: string,
): MemberRow[] {
  const rows = new Map<string, MemberRow>();
  for (const member of managed?.memberPlacements || []) {
    if (member.deploymentId !== deploymentId) continue;
    rows.set(member.memberId, {
      ...member,
      configuration: member.configuration || [],
    });
  }
  for (const intent of intents) {
    if (intent.deploymentId !== deploymentId) continue;
    if (intent.operation === "ReconcileDeploymentPlacement") {
      rows.clear();
      for (const member of intent.members)
        rows.set(member.memberId, {
          ...member,
          deploymentId,
          roles: member.roles || [],
          configuration: [],
        });
    }
    if (intent.operation === "ReconcileHostScopedDeploymentPlacement")
      rows.clear();
  }
  return [...rows.values()].sort((left, right) =>
    left.memberId.localeCompare(right.memberId),
  );
}

function finalTLSProfileIDs(
  managed: OpenResult["managed"],
  intents: CertificateIntent[],
) {
  const ids = new Set(Object.keys(managed?.pki?.tlsProfiles || {}));
  for (const intent of intents) {
    if (
      intent.operation === "CreateTLSProfile" ||
      intent.operation === "UpdateTLSProfile"
    )
      ids.add(intent.entityId);
    if (intent.operation === "DeleteTLSProfile") ids.delete(intent.entityId);
  }
  return [...ids].sort();
}

function finalDeploymentIDs(
  managed: OpenResult["managed"],
  intents: DeploymentIntent[],
) {
  const ids = new Set(Object.keys(managed?.deployments || {}));
  for (const intent of intents) {
    if (intent.operation === "CreateServiceDeployment") ids.add(intent.deploymentId);
    else ids.delete(intent.deploymentId);
  }
  return [...ids].sort((left, right) => left.localeCompare(right));
}

function inputValue(value: Value | undefined, shape: string) {
  if (shape === "BOOLEAN") return value === true ? "true" : "false";
  return value === undefined ? "" : String(value);
}

function valueFor(setting: CatalogSetting, raw: string): Value | undefined {
  if (setting.editorShape === "BOOLEAN") return raw === "true";
  if (setting.editorShape === "INTEGER" || setting.editorShape === "NUMBER") {
    if (!raw.trim()) return undefined;
    const value = Number(raw);
    return Number.isFinite(value) ? value : undefined;
  }
  return raw;
}

function settingTitle(setting: CatalogSetting) {
  return setting.label || setting.id;
}

export function ServicesPage({
  managed,
  catalog,
  deploymentIntents,
  placementIntents,
  certificateIntents,
  configurationIntents,
  busy,
  structuralDisabled,
  commandCount,
  error,
  view,
  selectedDeploymentId,
  selectedMemberId,
  onSelectedMemberChange,
  onOpenDeployment,
  onBackToList,
  onOpenTopology,
  onManageCertificates,
  onAppend,
  onReview,
  onDiscard,
}: {
  managed: OpenResult["managed"];
  catalog: OpenResult["catalog"];
  deploymentIntents: DeploymentIntent[];
  placementIntents: PlacementIntent[];
  certificateIntents: CertificateIntent[];
  configurationIntents: ConfigurationIntent[];
  busy: boolean;
  structuralDisabled: boolean;
  commandCount: number;
  error?: string;
  view: "list" | "detail";
  selectedDeploymentId: string;
  selectedMemberId: string;
  onSelectedMemberChange: (memberId: string) => void;
  onOpenDeployment: (deploymentId: string) => void;
  onBackToList: () => void;
  onOpenTopology: () => void;
  onManageCertificates: (memberId?: string) => void;
  onAppend: (intent: ConfigurationIntent) => Promise<boolean>;
  onReview: () => void;
  onDiscard: () => void;
}) {
  const [filter, setFilter] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const listHeading = useRef<HTMLHeadingElement>(null);
  const rows = useMemo(
    () => rowsFor(managed, deploymentIntents),
    [managed, deploymentIntents],
  );
  const catalogReady = catalog?.status === "READY";
  const selected = rows.find(
    (row) => row.deploymentId === selectedDeploymentId,
  );
  const savedOverrides = selected
    ? managed?.deployments?.[selected.deploymentId]?.configuration || []
    : [];
  const service = selected
    ? catalogService(catalog, selected.serviceType)
    : undefined;
  const settings = [...(service?.configurationSettings || [])].sort(
    (left, right) =>
      (left.section || "").localeCompare(right.section || "") ||
      (left.order || 0) - (right.order || 0) ||
      left.id.localeCompare(right.id),
  );
  const members = selected
    ? finalMembers(managed, placementIntents, selected.deploymentId)
    : [];
  const selectedMember = members.find(
    (member) => member.memberId === selectedMemberId,
  );
  const tlsProfileIDs = finalTLSProfileIDs(managed, certificateIntents);
  const deploymentIDs = finalDeploymentIDs(managed, deploymentIntents);
  const normalizedFilter = filter.trim().toLocaleLowerCase("ru");
  const filteredRows = rows.filter((row) =>
    `${row.deploymentId} ${row.serviceType} ${catalogService(catalog, row.serviceType)?.displayName || ""}`
      .toLocaleLowerCase("ru")
      .includes(normalizedFilter),
  );

  useEffect(() => {
    if (view === "detail") detailHeading.current?.focus();
  }, [view, selectedDeploymentId]);
  useEffect(() => {
    if (view === "list") listHeading.current?.focus();
  }, [view]);
  useEffect(() => {
    if (view === "detail" && selectedDeploymentId && !selected) onBackToList();
  }, [view, selectedDeploymentId, selected, onBackToList]);
  useEffect(() => {
    if (
      selectedMemberId &&
      members.some((member) => member.memberId === selectedMemberId)
    )
      return;
    onSelectedMemberChange(members[0]?.memberId || "");
  }, [members, selectedMemberId, onSelectedMemberChange]);

  if (view === "detail") {
    if (!selected)
      return (
        <section className="card" aria-live="polite">
          <h1 ref={detailHeading} tabIndex={-1}>
            Сервис не найден
          </h1>
          <p className="muted">
            Вернитесь к списку и выберите существующий deployment.
          </p>
          <button className="outline" onClick={onBackToList}>
            К списку сервисов
          </button>
        </section>
      );
    return (
      <section className="services-detail">
        <div className="page-title topology-title">
          <div>
            <h1 ref={detailHeading} tabIndex={-1}>
              Настройка сервиса
            </h1>
            <p>
              {selected.deploymentId} ·{" "}
              {service?.displayName || selected.serviceType}
            </p>
          </div>
          <button className="outline" onClick={onBackToList}>
            К списку сервисов
          </button>
        </div>
        {selected.state === "deleting" && (
          <section className="card topology-warning" role="status">
            Этот deployment будет удалён; настройка недоступна.
          </section>
        )}
        {!catalogReady && (
          <section className="card topology-warning" role="status">
            Совместимый READY-каталог недоступен. Сохранённые overrides остаются
            без изменений, но редактирование отключено.
          </section>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <section className="card services-settings">
          <h2>Параметры deployment</h2>
          {!service ? (
            <>
              <p className="muted">
                Для сохранённого типа сервиса нет совместимого описания
                параметров.
              </p>
              {!catalogReady && savedOverrides.length > 0 && (
                <SavedOverrides overrides={savedOverrides} />
              )}
            </>
          ) : settings.length === 0 ? (
            <>
              <p className="muted">
                Каталог не объявляет доступных параметров для этого deployment.
              </p>
              {!catalogReady && savedOverrides.length > 0 && (
                <SavedOverrides overrides={savedOverrides} />
              )}
            </>
          ) : (
            <div className="services-setting-list">
              {settings.map((setting) => {
                const current = settingValue(
                  savedOverrides,
                  selected.deploymentId,
                  "DEPLOYMENT",
                  "",
                  setting.id,
                  configurationIntents,
                );
                const locked = configurationIntents.some(
                  (intent) =>
                    intent.deploymentId === selected.deploymentId &&
                    intent.scope === "DEPLOYMENT" &&
                    intent.setting === setting.id,
                );
                const editable =
                  isEditable(setting, catalogReady) &&
                  setting.scopes.includes("deployment") &&
                  !selected.state;
                const disabled =
                  busy ||
                  structuralDisabled ||
                  locked ||
                  !editable ||
                  commandCount >= 16;
                const draftKey = `${selected.deploymentId}\u0000${setting.id}`;
                const raw =
                  drafts[draftKey] ??
                  inputValue(current.value, setting.editorShape);
                const value = valueFor(setting, raw);
                const invalidNumber =
                  (setting.editorShape === "INTEGER" ||
                    setting.editorShape === "NUMBER") &&
                  raw.trim() !== "" &&
                  value === undefined;
                const invalidTextValue = invalidText(setting, raw);
                return (
                  <div className="services-setting" key={setting.id}>
                    <div>
                      <strong>{settingTitle(setting)}</strong>
                      <small>{setting.id}</small>
                      {setting.description && (
                        <p className="muted">{setting.description}</p>
                      )}
                    </div>
                    {editable ? (
                      <div className="services-control">
                        {setting.editorShape === "BOOLEAN" ? (
                          <label className="services-checkbox">
                            <input
                              aria-label={settingTitle(setting)}
                              type="checkbox"
                              checked={raw === "true"}
                              disabled={disabled}
                              onChange={(event) =>
                                setDrafts((currentDrafts) => ({
                                  ...currentDrafts,
                                  [draftKey]: String(event.target.checked),
                                }))
                              }
                            />
                            Включено
                          </label>
                        ) : setting.editorShape === "TLS_PROFILE" ? (
                          <>
                            <select
                              aria-label={settingTitle(setting)}
                              value={raw}
                              disabled={disabled || !tlsProfileIDs.length}
                              onChange={(event) =>
                                setDrafts((currentDrafts) => ({
                                  ...currentDrafts,
                                  [draftKey]: event.target.value,
                                }))
                              }
                            >
                              <option value="">Выберите TLS profile</option>
                              {tlsProfileIDs.map((id) => (
                                <option key={id} value={id}>
                                  {id}
                                </option>
                              ))}
                            </select>
                            {!tlsProfileIDs.length && (
                              <small className="muted">
                                Нет доступного managed TLS profile.
                              </small>
                            )}
                            <button
                              className="outline"
                              disabled={busy || structuralDisabled}
                              onClick={() => onManageCertificates()}
                            >
                              Настроить сертификаты
                            </button>
                          </>
                        ) : setting.editorShape === "SERVICE_DEPLOYMENT" ? (
                          <>
                            <select
                              aria-label={settingTitle(setting)}
                              value={raw}
                              disabled={disabled || !deploymentIDs.length}
                              onChange={(event) =>
                                setDrafts((currentDrafts) => ({
                                  ...currentDrafts,
                                  [draftKey]: event.target.value,
                                }))
                              }
                            >
                              <option value="">Выберите deployment</option>
                              {deploymentIDs.map((id) => (
                                <option key={id} value={id}>
                                  {id}
                                </option>
                              ))}
                            </select>
                            {!deploymentIDs.length && (
                              <small className="muted">
                                Нет доступного managed deployment.
                              </small>
                            )}
                          </>
                        ) : setting.editorShape === "ENUM" ? (
                          <select
                            aria-label={settingTitle(setting)}
                            value={raw}
                            disabled={disabled}
                            onChange={(event) =>
                              setDrafts((currentDrafts) => ({
                                ...currentDrafts,
                                [draftKey]: event.target.value,
                              }))
                            }
                          >
                            <option value="">Выберите значение</option>
                            {(setting.enum || [])
                              .filter(
                                (item): item is string =>
                                  typeof item === "string",
                              )
                              .map((item) => (
                                <option key={item} value={item}>
                                  {item}
                                </option>
                              ))}
                          </select>
                        ) : (
                          <input
                            aria-label={settingTitle(setting)}
                            type={
                              setting.editorShape === "INTEGER" ||
                              setting.editorShape === "NUMBER"
                                ? "number"
                                : "text"
                            }
                            value={raw}
                            min={setting.minimum}
                            max={setting.maximum}
                            minLength={setting.minLength}
                            maxLength={setting.maxLength}
                            pattern={
                              setting.editorShape === "DNS_DOMAIN"
                                ? dnsDomainPattern.source
                                : undefined
                            }
                            disabled={disabled}
                            onChange={(event) =>
                              setDrafts((currentDrafts) => ({
                                ...currentDrafts,
                                [draftKey]: event.target.value,
                              }))
                            }
                          />
                        )}
                        {invalidNumber && (
                          <small className="field-error">Введите число.</small>
                        )}
                        {invalidTextValue && (
                          <small className="field-error">
                            Введите доменное имя в нижнем регистре, например
                            scada.local.
                          </small>
                        )}
                        <div className="actions">
                          <button
                            disabled={
                              disabled ||
                              value === undefined ||
                              invalidNumber ||
                              invalidTextValue
                            }
                            onClick={() =>
                              onAppend({
                                operation: "SetServiceConfigurationValue",
                                deploymentId: selected.deploymentId,
                                scope: "DEPLOYMENT",
                                setting: setting.id,
                                value: value as Value,
                              })
                            }
                          >
                            Применить
                          </button>
                          <button
                            className="outline"
                            disabled={disabled || !current.overridePresent}
                            onClick={() =>
                              onAppend({
                                operation: "RemoveServiceConfigurationOverride",
                                deploymentId: selected.deploymentId,
                                scope: "DEPLOYMENT",
                                setting: setting.id,
                              })
                            }
                          >
                            Сбросить
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className="muted">
                        {locked
                          ? "Изменение уже добавлено в текущий черновик."
                          : "Этот параметр доступен только для просмотра в текущем интерфейсе."}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
        {members.length > 0 && (
          <section className="card services-settings">
            <h2>Параметры member</h2>
            <label className="services-member-picker">
              Member
              <select
                value={selectedMemberId}
                onChange={(event) => onSelectedMemberChange(event.target.value)}
                disabled={busy || structuralDisabled || !!selected.state}
              >
                {members.map((member) => (
                  <option key={member.memberId} value={member.memberId}>
                    {member.memberId} · {member.hostId}
                  </option>
                ))}
              </select>
            </label>
            {selectedMember && (
              <MemberSettings
                deploymentId={selected.deploymentId}
                member={selectedMember}
                settings={settings}
                catalogReady={catalogReady}
                tlsProfileIDs={tlsProfileIDs}
                deploymentIDs={deploymentIDs}
                intents={configurationIntents}
                busy={busy}
                structuralDisabled={structuralDisabled}
                commandCount={commandCount}
                deleting={!!selected.state}
                onManageCertificates={() =>
                  onManageCertificates(selectedMember.memberId)
                }
                onAppend={onAppend}
              />
            )}
          </section>
        )}
        <SessionActions
          commandCount={commandCount}
          busy={busy}
          onReview={onReview}
          onDiscard={onDiscard}
        />
      </section>
    );
  }

  return (
    <section className="services-list">
      <div className="page-title topology-title">
        <div>
          <h1 ref={listHeading} tabIndex={-1}>
            Сервисы
          </h1>
          <p>
            Выберите deployment для настройки безопасно поддерживаемых
            параметров.
          </p>
        </div>
      </div>
      <section className="card topology-list">
        <label>
          Поиск deployment
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="ID или тип сервиса"
          />
        </label>
        <div className="topology-list-scroll">
          {filteredRows.map((row) => (
            <button
              className={`topology-row${row.state === "deleting" ? " draft-deleting" : ""}`}
              key={row.deploymentId}
              onClick={() => onOpenDeployment(row.deploymentId)}
              disabled={row.state === "deleting"}
            >
              <strong>{row.deploymentId}</strong>
              <span>
                {catalogService(catalog, row.serviceType)?.displayName ||
                  row.serviceType}
              </span>
              <small>
                {row.state === "new"
                  ? "Новый черновик"
                  : row.state === "deleting"
                    ? "Будет удалён"
                    : "Сохранён"}
              </small>
            </button>
          ))}
          {!filteredRows.length && (
            <div>
              <p className="muted">Подходящие deployments не найдены.</p>
              {!rows.length && (
                <button className="outline" onClick={onOpenTopology}>
                  Открыть Топологию
                </button>
              )}
            </div>
          )}
        </div>
      </section>
      <SessionActions
        commandCount={commandCount}
        busy={busy}
        onReview={onReview}
        onDiscard={onDiscard}
      />
    </section>
  );
}

function SavedOverrides({
  overrides,
}: {
  overrides: Array<{
    setting: string;
    overridePresent: boolean;
    state: string;
  }>;
}) {
  return (
    <div className="services-saved-overrides">
      <p className="muted">Сохранённые overrides (только просмотр):</p>
      <ul>
        {overrides.map((override) => (
          <li key={override.setting}>
            <code>{override.setting}</code> ·{" "}
            {override.overridePresent
              ? "override сохранён"
              : "override отсутствует"}{" "}
            · {override.state}
          </li>
        ))}
      </ul>
    </div>
  );
}

function MemberSettings({
  deploymentId,
  member,
  settings,
  catalogReady,
  tlsProfileIDs,
  deploymentIDs,
  intents,
  busy,
  structuralDisabled,
  commandCount,
  deleting,
  onManageCertificates,
  onAppend,
}: {
  deploymentId: string;
  member: MemberRow;
  settings: CatalogSetting[];
  catalogReady: boolean;
  tlsProfileIDs: string[];
  deploymentIDs: string[];
  intents: ConfigurationIntent[];
  busy: boolean;
  structuralDisabled: boolean;
  commandCount: number;
  deleting: boolean;
  onManageCertificates: () => void;
  onAppend: (intent: ConfigurationIntent) => Promise<boolean>;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const memberSettings = settings.filter((setting) =>
    setting.scopes.includes("member"),
  );
  if (!memberSettings.length)
    return (
      <p className="muted">Каталог не объявляет member-scoped параметров.</p>
    );
  return (
    <>
      <p className="muted">
        Host: {member.hostId} · Роли: {member.roles.join(", ") || "не заданы"}
      </p>
      <div className="services-setting-list">
        {memberSettings.map((setting) => {
          const current = settingValue(
            member.configuration,
            deploymentId,
            "MEMBER",
            member.memberId,
            setting.id,
            intents,
          );
          const locked = intents.some(
            (intent) =>
              intent.deploymentId === deploymentId &&
              intent.scope === "MEMBER" &&
              intent.memberId === member.memberId &&
              intent.setting === setting.id,
          );
          const editable = isEditable(setting, catalogReady) && !deleting;
          const disabled =
            busy ||
            structuralDisabled ||
            locked ||
            !editable ||
            commandCount >= 16;
          const draftKey = `${deploymentId}\u0000${member.memberId}\u0000${setting.id}`;
          const raw =
            drafts[draftKey] ?? inputValue(current.value, setting.editorShape);
          const value = valueFor(setting, raw);
          const invalidNumber =
            (setting.editorShape === "INTEGER" ||
              setting.editorShape === "NUMBER") &&
            raw.trim() !== "" &&
            value === undefined;
          const invalidTextValue = invalidText(setting, raw);
          return (
            <div className="services-setting" key={setting.id}>
              <div>
                <strong>{settingTitle(setting)}</strong>
                <small>{setting.id}</small>
                {setting.description && (
                  <p className="muted">{setting.description}</p>
                )}
              </div>
              {editable ? (
                <div className="services-control">
                  {setting.editorShape === "BOOLEAN" ? (
                    <label className="services-checkbox">
                      <input
                        aria-label={`${member.memberId}: ${settingTitle(setting)}`}
                        type="checkbox"
                        checked={raw === "true"}
                        disabled={disabled}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [draftKey]: String(event.target.checked),
                          }))
                        }
                      />
                      Включено
                    </label>
                  ) : setting.editorShape === "TLS_PROFILE" ? (
                    <>
                      <select
                        aria-label={`${member.memberId}: ${settingTitle(setting)}`}
                        value={raw}
                        disabled={disabled || !tlsProfileIDs.length}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [draftKey]: event.target.value,
                          }))
                        }
                      >
                        <option value="">Выберите TLS profile</option>
                        {tlsProfileIDs.map((id) => (
                          <option key={id} value={id}>
                            {id}
                          </option>
                        ))}
                      </select>
                      {!tlsProfileIDs.length && (
                        <small className="muted">
                          Нет доступного managed TLS profile.
                        </small>
                      )}
                      <button
                        className="outline"
                        disabled={busy || structuralDisabled}
                        onClick={onManageCertificates}
                      >
                        Настроить сертификаты
                      </button>
                    </>
                  ) : setting.editorShape === "SERVICE_DEPLOYMENT" ? (
                    <>
                      <select
                        aria-label={`${member.memberId}: ${settingTitle(setting)}`}
                        value={raw}
                        disabled={disabled || !deploymentIDs.length}
                        onChange={(event) =>
                          setDrafts((current) => ({
                            ...current,
                            [draftKey]: event.target.value,
                          }))
                        }
                      >
                        <option value="">Выберите deployment</option>
                        {deploymentIDs.map((id) => (
                          <option key={id} value={id}>
                            {id}
                          </option>
                        ))}
                      </select>
                      {!deploymentIDs.length && (
                        <small className="muted">
                          Нет доступного managed deployment.
                        </small>
                      )}
                    </>
                  ) : setting.editorShape === "ENUM" ? (
                    <select
                      aria-label={`${member.memberId}: ${settingTitle(setting)}`}
                      value={raw}
                      disabled={disabled}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [draftKey]: event.target.value,
                        }))
                      }
                    >
                      <option value="">Выберите значение</option>
                      {(setting.enum || [])
                        .filter(
                          (item): item is string => typeof item === "string",
                        )
                        .map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                    </select>
                  ) : (
                    <input
                      aria-label={`${member.memberId}: ${settingTitle(setting)}`}
                      type={
                        setting.editorShape === "INTEGER" ||
                        setting.editorShape === "NUMBER"
                          ? "number"
                          : "text"
                      }
                      value={raw}
                      min={setting.minimum}
                      max={setting.maximum}
                      minLength={setting.minLength}
                      maxLength={setting.maxLength}
                      pattern={
                        setting.editorShape === "DNS_DOMAIN"
                          ? dnsDomainPattern.source
                          : undefined
                      }
                      disabled={disabled}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [draftKey]: event.target.value,
                        }))
                      }
                    />
                  )}
                  {invalidNumber && (
                    <small className="field-error">Введите число.</small>
                  )}
                  {invalidTextValue && (
                    <small className="field-error">
                      Введите доменное имя в нижнем регистре, например
                      scada.local.
                    </small>
                  )}
                  <div className="actions">
                    <button
                      disabled={
                        disabled ||
                        value === undefined ||
                        invalidNumber ||
                        invalidTextValue
                      }
                      onClick={() =>
                        onAppend({
                          operation: "SetServiceConfigurationValue",
                          deploymentId,
                          scope: "MEMBER",
                          memberId: member.memberId,
                          setting: setting.id,
                          value: value as Value,
                        })
                      }
                    >
                      Применить
                    </button>
                    <button
                      className="outline"
                      disabled={disabled || !current.overridePresent}
                      onClick={() =>
                        onAppend({
                          operation: "RemoveServiceConfigurationOverride",
                          deploymentId,
                          scope: "MEMBER",
                          memberId: member.memberId,
                          setting: setting.id,
                        })
                      }
                    >
                      Сбросить
                    </button>
                  </div>
                </div>
              ) : (
                <p className="muted">
                  {locked
                    ? "Изменение уже добавлено в текущий черновик."
                    : "Этот параметр доступен только для просмотра в текущем интерфейсе."}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

function SessionActions({
  commandCount,
  busy,
  onReview,
  onDiscard,
}: {
  commandCount: number;
  busy: boolean;
  onReview: () => void;
  onDiscard: () => void;
}) {
  if (!commandCount) return null;
  return (
    <div className="actions services-session-actions">
      <span className="muted">Изменений в черновике: {commandCount} из 16</span>
      <button className="outline" disabled={busy} onClick={onDiscard}>
        Отменить черновик
      </button>
      <button disabled={busy} onClick={onReview}>
        Проверить и сохранить
      </button>
    </div>
  );
}
