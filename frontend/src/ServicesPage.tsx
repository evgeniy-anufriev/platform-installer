import { useEffect, useMemo, useRef, useState } from "react";
import type {
  OpenResult,
  PendingRuntimeSecretFileInput,
  PendingRuntimeSecretValuesInput,
  RuntimeSecretDescriptorOperation,
  ServiceConfigurationPreview,
} from "./backend";
import type { CertificateIntent } from "./CertificatesPage";
import type { DeploymentIntent, PlacementIntent } from "./TopologyPage";

export type ConfigurationIntent =
  | {
      operation: "SetServiceConfigurationValue";
      deploymentId: string;
      scope: "DEPLOYMENT" | "MEMBER";
      memberId?: string;
      setting: string;
      value: ConfigurationValue;
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
type RuntimeSecretReference = { passwordSecretRef: string; username?: string };
type ConfigurationValue = Value | RuntimeSecretReference;
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
    value?: ConfigurationValue;
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
    value?: ConfigurationValue;
  }>,
  deploymentId: string,
  scope: Scope,
  memberId: string,
  setting: string,
  intents: ConfigurationIntent[],
): { overridePresent: boolean; state: string; value?: ConfigurationValue } {
  const saved = overrides.find((entry) => entry.setting === setting);
  let result: {
    overridePresent: boolean;
    state: string;
    value?: ConfigurationValue;
  } = {
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
    if (intent.operation === "CreateServiceDeployment")
      ids.add(intent.deploymentId);
    else ids.delete(intent.deploymentId);
  }
  return [...ids].sort((left, right) => left.localeCompare(right));
}

function inputValue(value: ConfigurationValue | undefined, shape: string) {
  if (typeof value === "object") return "";
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

function previewValue(value: unknown): string | null {
  if (typeof value === "string") {
    if (
      value.length > 4096 ||
      /[\u0000-\u001f\u007f]/u.test(value) ||
      ["{{", "}}", "{%", "%}", "{#", "#}"].some((marker) =>
        value.includes(marker),
      )
    )
      return null;
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  return null;
}

function displayedInputValue(
  setting: CatalogSetting,
  current: {
    overridePresent: boolean;
    state: string;
    value?: ConfigurationValue;
  },
  coreValue?: { state: string; value?: string | number | boolean },
  deploymentOverride?: {
    overridePresent: boolean;
    state: string;
    value?: ConfigurationValue;
  },
): string {
  const ordinary = (value: unknown): string => {
    if (previewValue(value) === null) return "";
    if (
      typeof value === "string" ||
      typeof value === "number" ||
      typeof value === "boolean"
    )
      return inputValue(value, setting.editorShape);
    return "";
  };
  if (current.overridePresent) return ordinary(current.value);
  // A current Core result takes precedence even when it says that the value
  // cannot be resolved; falling back to a literal would mislabel it as exact.
  if (coreValue)
    return coreValue.state === "RESOLVED" ? ordinary(coreValue.value) : "";
  if (deploymentOverride?.overridePresent)
    return ordinary(deploymentOverride.value);
  return setting.staticDefaultState === "LITERAL"
    ? ordinary(setting.staticDefaultValue)
    : "";
}

function SettingPreview({
  setting,
  current,
  deploymentOverride,
  coreValue,
}: {
  setting: CatalogSetting;
  current: {
    overridePresent: boolean;
    state: string;
    value?: ConfigurationValue;
  };
  deploymentOverride?: {
    overridePresent: boolean;
    state: string;
    value?: ConfigurationValue;
  };
  coreValue?: {
    state: string;
    source: string;
    value?: string | number | boolean;
  };
}) {
  if (setting.editorShape === "RUNTIME_SECRET_REFERENCE_OBJECT")
    return (
      <small className="muted">
        {current.overridePresent || deploymentOverride?.overridePresent
          ? "Ссылка на секрет задана. Наличие значения в текущей сессии здесь не подтверждается."
          : "Ссылка на секрет не задана. Настройте её через «Секреты»."}
      </small>
    );
  if (setting.kind !== "MANAGED" || setting.editorShape === "UNSUPPORTED")
    return (
      <small className="muted">
        {current.overridePresent || deploymentOverride?.overridePresent
          ? "Переопределение задано"
          : "Точное значение недоступно"}
        . Значение этого параметра недоступно для просмотра.
      </small>
    );
  const own =
    current.overridePresent && current.state === "EDITABLE"
      ? previewValue(current.value)
      : null;
  const inherited =
    deploymentOverride?.overridePresent &&
    deploymentOverride.state === "EDITABLE"
      ? previewValue(deploymentOverride.value)
      : null;
  const fallback =
    setting.staticDefaultState === "LITERAL"
      ? previewValue(setting.staticDefaultValue)
      : null;
  const resolved =
    coreValue?.state === "RESOLVED" ? previewValue(coreValue.value) : null;
  const coreSource =
    coreValue?.source === "MEMBER_OVERRIDE"
      ? "Переопределено для ноды"
      : coreValue?.source === "DEPLOYMENT_OVERRIDE"
        ? "Переопределено для сервиса"
        : coreValue?.source === "ROLE_DEFAULT"
          ? "По умолчанию"
          : "Разрешено Core";
  return (
    <small className="muted" aria-live="polite">
      {resolved !== null
        ? `${coreSource}: ${resolved}`
        : coreValue?.state === "DEFERRED"
          ? "Вычисляется при выполнении"
          : own !== null
            ? `Переопределено ${deploymentOverride ? "для ноды" : "для сервиса"}: ${own}`
            : current.overridePresent
              ? "Переопределено; итоговое значение вычисляется при выполнении"
              : inherited !== null
                ? `Задано для сервиса: ${inherited}; итоговое значение ожидает Core`
                : deploymentOverride?.overridePresent
                  ? "Задано для сервиса; итоговое значение ожидает Core"
                  : fallback !== null
                    ? `По умолчанию: ${fallback}`
                    : setting.staticDefaultState === "DEFERRED"
                      ? "Вычисляется при выполнении"
                      : "Значение по умолчанию пока недоступно"}
    </small>
  );
}

export function ServicesPage({
  managed,
  catalog,
  effectivePreview,
  corePreviewNotice,
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
  focusMemberSettings,
  onSelectedMemberChange,
  onOpenDeployment,
  onBackToList,
  onOpenTopology,
  onManageCertificates,
  onAppend,
  onAmend,
  onReview,
  onDiscard,
  onGetPendingRuntimeSecretDescriptors,
  onSetPendingDeploymentRuntimeSecretValues,
  onChoosePendingDeploymentRuntimeSecretFile,
}: {
  managed: OpenResult["managed"];
  catalog: OpenResult["catalog"];
  effectivePreview?: ServiceConfigurationPreview;
  corePreviewNotice?: string;
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
  focusMemberSettings: boolean;
  onSelectedMemberChange: (memberId: string) => void;
  onOpenDeployment: (deploymentId: string) => void;
  onBackToList: () => void;
  onOpenTopology: () => void;
  onManageCertificates: (memberId?: string) => void;
  onAppend: (intent: ConfigurationIntent) => Promise<boolean>;
  onAmend: (
    previous: ConfigurationIntent,
    replacement: ConfigurationIntent | null,
  ) => Promise<boolean>;
  onReview: () => void;
  onDiscard: () => void;
  onGetPendingRuntimeSecretDescriptors?: (
    serviceDeployment: string,
  ) => Promise<RuntimeSecretDescriptorOperation>;
  onSetPendingDeploymentRuntimeSecretValues?: (
    input: PendingRuntimeSecretValuesInput,
  ) => Promise<void>;
  onChoosePendingDeploymentRuntimeSecretFile?: (
    input: PendingRuntimeSecretFileInput,
  ) => Promise<string>;
}) {
  const [filter, setFilter] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [secretOperation, setSecretOperation] =
    useState<RuntimeSecretDescriptorOperation | null>(null);
  const secretDialogRef = useRef<HTMLDialogElement>(null);
  const [secretValues, setSecretValues] = useState<Record<string, string>>({});
  const [secretUsernames, setSecretUsernames] = useState<
    Record<string, string>
  >({});
  const [secretBusy, setSecretBusy] = useState(false);
  const [installedSecrets, setInstalledSecrets] = useState<Record<string, boolean>>({});
  const [secretStatusVersion, setSecretStatusVersion] = useState(0);
  const [secretError, setSecretError] = useState("");
  const [inputEncryptionPassword, setInputEncryptionPassword] = useState("");
  const [secretFileStates, setSecretFileStates] = useState<
    Record<string, string>
  >({});
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const listHeading = useRef<HTMLHeadingElement>(null);
  const memberSettingsHeading = useRef<HTMLHeadingElement>(null);
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
      (left.order || 0) - (right.order || 0) ||
      (left.section || "").localeCompare(right.section || "") ||
      left.id.localeCompare(right.id),
  );
  const visibleSettings = settings.filter(
    (setting) =>
      !setting.runtimeSecretRequirementRef &&
      setting.editorShape !== "RUNTIME_SECRET_REFERENCE_OBJECT",
  );
  const hasConfigurableSecrets =
    settings.some((setting) => !!setting.runtimeSecretRequirementRef) ||
    !!service?.secretInputs?.length;
  useEffect(() => {
    if (view !== "detail" || !selectedDeploymentId || !hasConfigurableSecrets || !onGetPendingRuntimeSecretDescriptors) return;
    let cancelled = false;
    const refresh = async () => {
      try {
        const operation = await onGetPendingRuntimeSecretDescriptors(selectedDeploymentId);
        if (!cancelled) setInstalledSecrets((current) => ({
          ...current,
          [selectedDeploymentId]: operation.status === "READY" && operation.secretsInstalled === true,
        }));
      } catch {
        if (!cancelled) setInstalledSecrets((current) => ({ ...current, [selectedDeploymentId]: false }));
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [view, selectedDeploymentId, hasConfigurableSecrets, onGetPendingRuntimeSecretDescriptors, secretStatusVersion, managed]);
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
    if (view !== "detail" || !focusMemberSettings || !selectedMember) return;
    memberSettingsHeading.current?.focus();
    memberSettingsHeading.current?.scrollIntoView?.({ block: "start" });
  }, [
    view,
    focusMemberSettings,
    selected?.deploymentId,
    selectedMember?.memberId,
  ]);
  useEffect(() => {
    if (view === "list") listHeading.current?.focus();
  }, [view]);
  useEffect(() => {
    if (view === "detail" && selectedDeploymentId && !selected) onBackToList();
  }, [view, selectedDeploymentId, selected, onBackToList]);
  useEffect(() => {
    const dialog = secretDialogRef.current;
    if (!dialog) return;
    if (secretOperation && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    } else if (!secretOperation && dialog.open) {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }
  }, [secretOperation]);
  useEffect(() => {
    if (
      selectedMemberId &&
      members.some((member) => member.memberId === selectedMemberId)
    )
      return;
    onSelectedMemberChange(members[0]?.memberId || "");
  }, [members, selectedMemberId, onSelectedMemberChange]);

  const closeSecrets = () => {
    setSecretValues({});
    setSecretUsernames({});
    setSecretError("");
    setSecretOperation(null);
    setInputEncryptionPassword("");
    setSecretFileStates({});
  };
  const openSecrets = async () => {
    if (!onGetPendingRuntimeSecretDescriptors || !selected) return;
    setSecretBusy(true);
    setSecretError("");
    try {
      const operation = await onGetPendingRuntimeSecretDescriptors(
        selected.deploymentId,
      );
      const descriptors = (operation.descriptors || []).filter(
        (item) =>
          [
            "SERVICE_PASSWORD",
            "SERVICE_ADMIN_TOKEN",
            "SERVICE_UNSEAL_SHARES",
          ].includes(item.purpose) &&
          item.serviceDeployment === selected.deploymentId,
      );
      if (operation.status !== "READY" || !descriptors.length) {
        setSecretError(
          operation.error?.message ||
            "Для этого deployment нет доступных требований к секретам.",
        );
        return;
      }
      setSecretOperation({ ...operation, descriptors });
    } catch {
      setSecretError("Не удалось безопасно получить требования к секретам.");
    } finally {
      setSecretBusy(false);
    }
  };
  const submitSecrets = async (event: React.FormEvent) => {
    event.preventDefault();
    if (
      !selected ||
      !secretOperation ||
      !onSetPendingDeploymentRuntimeSecretValues
    )
      return;
    const descriptors = (secretOperation.descriptors || []).filter(
      (item) => item.purpose === "SERVICE_PASSWORD",
    );
    if (descriptors.length === 0) {
      closeSecrets();
      return;
    }
    const values: Record<string, string> = {};
    for (const descriptor of descriptors)
      values[descriptor.requirementRef] =
        secretValues[descriptor.requirementRef] || "";
    if (Object.values(values).some((value) => !value)) {
      setSecretError("Заполните все обязательные значения.");
      return;
    }
    setSecretBusy(true);
    setSecretError("");
    try {
      const referencesAdded = descriptors.filter(
        (descriptor) => !descriptor.referenceConfigured && descriptor.setting &&
          !configurationIntents.some((intent) => intent.operation === "SetServiceConfigurationValue" &&
            intent.deploymentId === selected.deploymentId && intent.scope === "DEPLOYMENT" &&
            intent.setting === descriptor.setting && typeof intent.value === "object" &&
            intent.value !== null && !Array.isArray(intent.value) &&
            intent.value.passwordSecretRef === `runtime:${descriptor.requirementRef}` &&
            (!settings.find((setting) => setting.id === descriptor.setting)?.runtimeSecretUsernameRequired ||
              intent.value.username === secretUsernames[descriptor.requirementRef])),
      );
      if (
        referencesAdded.some((descriptor) => {
          const setting = settings.find(
            (item) => item.id === descriptor.setting,
          );
          return (
            setting?.runtimeSecretUsernameRequired &&
            !/^[A-Za-z_][A-Za-z0-9_]{0,62}$/.test(
              secretUsernames[descriptor.requirementRef] || "",
            )
          );
        })
      ) {
        setSecretError(
          "Укажите допустимое имя пользователя для этого секрета.",
        );
        return;
      }
      for (const descriptor of referencesAdded) {
        const setting = settings.find((item) => item.id === descriptor.setting);
        const username = secretUsernames[descriptor.requirementRef] || "";
        const appended = await onAppend({
          operation: "SetServiceConfigurationValue",
          deploymentId: selected.deploymentId,
          scope: "DEPLOYMENT",
          setting: descriptor.setting!,
          value: setting?.runtimeSecretUsernameRequired
            ? {
                username,
                passwordSecretRef: `runtime:${descriptor.requirementRef}`,
              }
            : { passwordSecretRef: `runtime:${descriptor.requirementRef}` },
        });
        if (!appended) {
          setSecretError(
            "Ссылка на секрет не добавлена в черновик. Значение не сохранено.",
          );
          return;
        }
      }
      await onSetPendingDeploymentRuntimeSecretValues({
        serviceDeployment: selected.deploymentId,
        values,
      });
      setSecretStatusVersion((current) => current + 1);
      closeSecrets();
    } catch {
      setSecretValues({});
      setSecretError(
        "Значения не приняты: обновите требования и повторите ввод.",
      );
    } finally {
      setSecretBusy(false);
    }
  };

  const chooseSecretFile = async (
    purpose: "SERVICE_ADMIN_TOKEN" | "SERVICE_UNSEAL_SHARES",
  ) => {
    if (!selected || !onChoosePendingDeploymentRuntimeSecretFile) return;
    setSecretBusy(true);
    setSecretError("");
    try {
      const status = await onChoosePendingDeploymentRuntimeSecretFile({
        serviceDeployment: selected.deploymentId,
        purpose,
        encryptionPassword: inputEncryptionPassword,
      });
      setSecretFileStates((current) => ({ ...current, [purpose]: status }));
      setSecretStatusVersion((current) => current + 1);
    } catch {
      setSecretError(
        "Файл не принят. Проверьте формат/пароль и повторите выбор.",
      );
    } finally {
      setInputEncryptionPassword("");
      setSecretBusy(false);
    }
  };

  const servicePicker = (
    <aside className="services-picker" aria-label="Список сервисов">
      <div className="services-picker-head">
        <h1 ref={listHeading} tabIndex={-1}>
          Сервисы
        </h1>
        <label>
          Поиск
          <input
            aria-label="Поиск сервисов"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="ID или тип сервиса"
          />
        </label>
      </div>
      <div className="services-picker-list">
        {filteredRows.map((row) => (
          <button
            className={`topology-row${row.state === "deleting" ? " draft-deleting" : ""}`}
            key={row.deploymentId}
            onClick={() => onOpenDeployment(row.deploymentId)}
            disabled={row.state === "deleting"}
            aria-current={
              row.deploymentId === selectedDeploymentId ? "page" : undefined
            }
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
          <div className="services-picker-empty">
            <p className="muted">Подходящие экземпляры не найдены.</p>
            {!rows.length && (
              <button className="outline" onClick={onOpenTopology}>
                Открыть Топологию
              </button>
            )}
          </div>
        )}
      </div>
    </aside>
  );

  if (selected) {
    return (
      <section className="services-workspace">
        {servicePicker}
        <section className="services-detail">
        <div className="page-title topology-title">
          <div>
            <h2 ref={detailHeading} tabIndex={-1}>
              Настройка сервиса
            </h2>
            <p>
              {selected.deploymentId} ·{" "}
              {service?.displayName || selected.serviceType}
            </p>
          </div>
          <button className="outline" onClick={onBackToList}>
            Скрыть настройки
          </button>
        </div>
        {selected.state === "deleting" && (
          <section className="card topology-warning" role="status">
            Этот экземпляр будет удалён; настройка недоступна.
          </section>
        )}
        {!catalogReady && (
          <section className="card topology-warning" role="status">
            Совместимый каталог недоступен. Сохранённые переопределения остаются
            без изменений, но редактирование отключено.
          </section>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {hasConfigurableSecrets && <section className="card service-secrets-action">
          <div>
            <h2>Секреты</h2>
            <span className={`status-chip status-chip--${installedSecrets[selected.deploymentId] ? "success" : "warning"}`} role="status">
              <span className="status-chip-symbol" aria-hidden="true">{installedSecrets[selected.deploymentId] ? "✓" : "!"}</span>
              {installedSecrets[selected.deploymentId] ? "Установлены" : "Не установлены"}
            </span>
            <p className="muted">
              Для выбранного режима показаны только разрешённые каталогом поля.
              Значения остаются в памяти приложения, не сохраняются в проекте и
              перед запуском повторно сверяются Core с новым планом.
            </p>
          </div>
          <button
            className="outline"
            disabled={
              busy ||
              structuralDisabled ||
              !!selected.state ||
              secretBusy ||
              !onGetPendingRuntimeSecretDescriptors ||
              (!onSetPendingDeploymentRuntimeSecretValues &&
                !onChoosePendingDeploymentRuntimeSecretFile)
            }
            onClick={() => void openSecrets()}
          >
            Секреты
          </button>
          {secretError && !secretOperation && (
            <p className="error" role="alert">
              {secretError}
            </p>
          )}
        </section>}
        <div
          className="services-parameter-column"
          role="region"
          aria-label="Параметры выбранного сервиса"
        >
        <section className="card services-settings">
          <h2>Параметры сервиса</h2>
          {corePreviewNotice && (
            <p className="muted" role="status">
              {corePreviewNotice}
            </p>
          )}
          {effectivePreview &&
            !effectivePreview.services[selected.deploymentId] && (
              <p className="muted" role="status">
                Core не вернул разрешённые значения для этого сервиса. Возможно,
                топология проекта ещё не завершена; показаны безопасные
                локальные значения.
              </p>
            )}
          {effectivePreview?.services[selected.deploymentId] && (
            <p className="muted" role="status">
              Значения получены из Core. Это не проверка проекта.
            </p>
          )}
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
          ) : visibleSettings.length === 0 ? (
            <>
              <p className="muted">
                Каталог не объявляет доступных параметров для этого экземпляра
                сервиса.
              </p>
              {!catalogReady && savedOverrides.length > 0 && (
                <SavedOverrides overrides={savedOverrides} />
              )}
            </>
          ) : (
            <div className="services-setting-list">
              {visibleSettings.map((setting) => {
                const current = settingValue(
                  savedOverrides,
                  selected.deploymentId,
                  "DEPLOYMENT",
                  "",
                  setting.id,
                  configurationIntents,
                );
                const pending = configurationIntents.find(
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
                  !editable ||
                  (commandCount >= 16 && !pending);
                const savedOverride = savedOverrides.some(
                  (entry) =>
                    entry.setting === setting.id && entry.overridePresent,
                );
                const draftKey = `${selected.deploymentId}\u0000${setting.id}`;
                const baseRaw = displayedInputValue(
                  setting,
                  current,
                  pending
                    ? undefined
                    : effectivePreview?.services[selected.deploymentId]
                        ?.configuration[setting.id],
                );
                const draftRaw = drafts[draftKey];
                const raw = draftRaw ?? baseRaw;
                const draftChanged =
                  draftRaw !== undefined && draftRaw !== baseRaw;
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
                      <SettingPreview
                        setting={setting}
                        current={current}
                        coreValue={
                          pending
                            ? undefined
                            : effectivePreview?.services[selected.deploymentId]
                                ?.configuration[setting.id]
                        }
                      />
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
                              <option value="">Выберите профиль TLS</option>
                              {raw && !tlsProfileIDs.includes(raw) && (
                                <option value={raw} disabled>
                                  {raw} · нет в управляемом списке
                                </option>
                              )}
                              {tlsProfileIDs.map((id) => (
                                <option key={id} value={id}>
                                  {id}
                                </option>
                              ))}
                            </select>
                            {!tlsProfileIDs.length && (
                              <small className="muted">
                                Нет доступного управляемого профиля TLS.
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
                              <option value="">
                                Выберите экземпляр сервиса
                              </option>
                              {deploymentIDs.map((id) => (
                                <option key={id} value={id}>
                                  {id}
                                </option>
                              ))}
                            </select>
                            {!deploymentIDs.length && (
                              <small className="muted">
                                Нет доступного управляемого экземпляра сервиса.
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
                              !draftChanged ||
                              value === undefined ||
                              invalidNumber ||
                              invalidTextValue
                            }
                            onClick={async () => {
                              const next: ConfigurationIntent = {
                                operation: "SetServiceConfigurationValue",
                                deploymentId: selected.deploymentId,
                                scope: "DEPLOYMENT",
                                setting: setting.id,
                                value: value as Value,
                              };
                              return pending
                                ? onAmend(pending, next)
                                : onAppend(next);
                            }}
                          >
                            Применить
                          </button>
                          <button
                            className="outline"
                            disabled={
                              disabled ||
                              (!savedOverride && !pending && !draftChanged) ||
                              (!!pending &&
                                pending.operation ===
                                  "RemoveServiceConfigurationOverride")
                            }
                            onClick={async () => {
                              if (!savedOverride && !pending) {
                                setDrafts((old) => {
                                  const next = { ...old };
                                  delete next[draftKey];
                                  return next;
                                });
                                return;
                              }
                              const next: ConfigurationIntent = {
                                operation: "RemoveServiceConfigurationOverride",
                                deploymentId: selected.deploymentId,
                                scope: "DEPLOYMENT",
                                setting: setting.id,
                              };
                              const accepted = pending
                                ? await onAmend(
                                    pending,
                                    savedOverride ? next : null,
                                  )
                                : await onAppend(next);
                              if (accepted)
                                setDrafts((old) => {
                                  const updated = { ...old };
                                  delete updated[draftKey];
                                  return updated;
                                });
                            }}
                          >
                            Сбросить
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className="muted">
                        Этот параметр доступен только для просмотра в текущем
                        интерфейсе.
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
            <h2 ref={memberSettingsHeading} tabIndex={-1}>
              Параметры экземпляра
            </h2>
            <label className="services-member-picker">
              Экземпляр
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
                settings={visibleSettings}
                deploymentOverrides={savedOverrides}
                effectivePreview={
                  effectivePreview?.services[selected.deploymentId]?.members[
                    selectedMember.memberId
                  ]
                }
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
                onAmend={onAmend}
              />
            )}
          </section>
        )}
        </div>
        <SessionActions
          commandCount={commandCount}
          busy={busy}
          onReview={onReview}
          onDiscard={onDiscard}
        />
        {secretOperation && (
          <dialog
            ref={secretDialogRef}
            className="runtime-secret-dialog"
            aria-label="Секреты сервиса"
            onCancel={(event) => {
              event.preventDefault();
              closeSecrets();
            }}
          >
            <form method="dialog" onSubmit={submitSecrets}>
              <h2>Секреты: {selected.deploymentId}</h2>
              <p className="muted">
                Значения остаются только в памяти приложения и перед запуском
                сверяются с требованиями Core.
              </p>
              {(secretOperation.descriptors || [])
                .filter(
                  (descriptor) => descriptor.purpose === "SERVICE_PASSWORD",
                )
                .map((descriptor) => (
                  <div key={descriptor.requirementRef}>
                    {settings.find((item) => item.id === descriptor.setting)
                      ?.runtimeSecretUsernameRequired &&
                      !descriptor.referenceConfigured && (
                        <label className="runtime-secret-username">
                          Имя пользователя
                          <input
                            type="text"
                            autoComplete="username"
                            value={
                              secretUsernames[descriptor.requirementRef] || ""
                            }
                            disabled={secretBusy}
                            onChange={(event) =>
                              setSecretUsernames((current) => ({
                                ...current,
                                [descriptor.requirementRef]: event.target.value,
                              }))
                            }
                          />
                        </label>
                      )}
                    <label>
                      {descriptor.displayLabel}
                      <input
                        type="password"
                        autoComplete="new-password"
                        value={secretValues[descriptor.requirementRef] || ""}
                        disabled={secretBusy}
                        onChange={(event) =>
                          setSecretValues((current) => ({
                            ...current,
                            [descriptor.requirementRef]: event.target.value,
                          }))
                        }
                      />
                    </label>
                  </div>
                ))}
              {(secretOperation.descriptors || [])
                .filter(
                  (descriptor) =>
                    descriptor.purpose === "SERVICE_ADMIN_TOKEN" ||
                    descriptor.purpose === "SERVICE_UNSEAL_SHARES",
                )
                .map((descriptor) => (
                  <div
                    key={descriptor.requirementRef}
                    className="runtime-secret-file-input"
                  >
                    <strong>{descriptor.displayLabel}</strong>
                    <p className="muted">
                      {descriptor.requiredWhen === "INITIALIZED"
                        ? "Для уже инициализированного сервиса"
                        : "Для повторного запуска запечатанного сервиса"}
                    </p>
                    <label>
                      Пароль файла age, если файл зашифрован
                      <input
                        type="password"
                        autoComplete="new-password"
                        value={inputEncryptionPassword}
                        disabled={secretBusy}
                        onChange={(event) =>
                          setInputEncryptionPassword(event.target.value)
                        }
                      />
                    </label>
                    <button
                      type="button"
                      className="outline"
                      disabled={
                        secretBusy ||
                        !onChoosePendingDeploymentRuntimeSecretFile
                      }
                      onClick={() =>
                        void chooseSecretFile(
                          descriptor.purpose as
                            "SERVICE_ADMIN_TOKEN" | "SERVICE_UNSEAL_SHARES",
                        )
                      }
                    >
                      Выбрать файл
                    </button>
                    <small aria-live="polite">
                      {secretFileStates[descriptor.purpose] === "STORED"
                        ? "Файл принят и сохранён только в сессии."
                        : secretFileStates[descriptor.purpose] === "CANCELLED"
                          ? "Выбор отменён."
                          : "Файл не выбран."}
                    </small>
                  </div>
                ))}
              {secretError && (
                <p className="error" role="alert">
                  {secretError}
                </p>
              )}
              <div className="actions">
                <button type="submit" disabled={secretBusy}>
                  {(secretOperation.descriptors || []).some(
                    (item) => item.purpose === "SERVICE_PASSWORD",
                  )
                    ? "Сохранить в сессии"
                    : "Готово"}
                </button>
                <button
                  type="button"
                  className="outline"
                  disabled={secretBusy}
                  onClick={closeSecrets}
                >
                  Отмена
                </button>
              </div>
            </form>
          </dialog>
        )}
        </section>
      </section>
    );
  }

  return (
    <section className="services-workspace">
      {servicePicker}
      <section className="services-detail-empty" aria-live="polite">
        <h2 ref={detailHeading} tabIndex={-1}>
          {view === "detail" ? "Сервис не найден" : "Выберите сервис"}
        </h2>
        <p className="muted">
          {view === "detail"
            ? "Выбранный deployment больше недоступен. Выберите сервис из списка."
            : "Настройки выбранного сервиса появятся здесь; список останется доступен слева."}
        </p>
      <SessionActions
        commandCount={commandCount}
        busy={busy}
        onReview={onReview}
        onDiscard={onDiscard}
      />
      </section>
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
      <p className="muted">Сохранённые переопределения (только просмотр):</p>
      <ul>
        {overrides.map((override) => (
          <li key={override.setting}>
            <code>{override.setting}</code> ·{" "}
            {override.overridePresent
              ? "переопределение сохранено"
              : "переопределения нет"}{" "}
            ·{" "}
            {override.state === "EDITABLE"
              ? "доступно для изменения"
              : "только просмотр"}
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
  deploymentOverrides,
  effectivePreview,
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
  onAmend,
}: {
  deploymentId: string;
  member: MemberRow;
  settings: CatalogSetting[];
  deploymentOverrides: MemberRow["configuration"];
  effectivePreview?: Record<
    string,
    { state: string; source: string; value?: string | number | boolean }
  >;
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
  onAmend: (
    previous: ConfigurationIntent,
    replacement: ConfigurationIntent | null,
  ) => Promise<boolean>;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const memberSettings = settings.filter((setting) =>
    setting.scopes.includes("member"),
  );
  if (!memberSettings.length)
    return (
      <p className="muted">
        Каталог не объявляет параметров отдельного экземпляра.
      </p>
    );
  return (
    <>
      <p className="muted">
        Сервер: {member.hostId} · Роли: {member.roles.join(", ") || "не заданы"}
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
          const deploymentOverride = settingValue(
            deploymentOverrides,
            deploymentId,
            "DEPLOYMENT",
            "",
            setting.id,
            intents,
          );
          const pending = intents.find(
            (intent) =>
              intent.deploymentId === deploymentId &&
              intent.scope === "MEMBER" &&
              intent.memberId === member.memberId &&
              intent.setting === setting.id,
          );
          const deploymentPending = intents.some(
            (intent) =>
              intent.deploymentId === deploymentId &&
              intent.scope === "DEPLOYMENT" &&
              intent.setting === setting.id,
          );
          const editable = isEditable(setting, catalogReady) && !deleting;
          const disabled =
            busy ||
            structuralDisabled ||
            !editable ||
            (commandCount >= 16 && !pending);
          const savedOverride = member.configuration.some(
            (entry) => entry.setting === setting.id && entry.overridePresent,
          );
          const draftKey = `${deploymentId}\u0000${member.memberId}\u0000${setting.id}`;
          const baseRaw = displayedInputValue(
            setting,
            current,
            pending || deploymentPending
              ? undefined
              : effectivePreview?.[setting.id],
            deploymentOverride,
          );
          const draftRaw = drafts[draftKey];
          const raw = draftRaw ?? baseRaw;
          const draftChanged = draftRaw !== undefined && draftRaw !== baseRaw;
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
                <SettingPreview
                  setting={setting}
                  current={current}
                  deploymentOverride={deploymentOverride}
                  coreValue={
                    pending || deploymentPending
                      ? undefined
                      : effectivePreview?.[setting.id]
                  }
                />
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
                        <option value="">Выберите профиль TLS</option>
                        {raw && !tlsProfileIDs.includes(raw) && (
                          <option value={raw} disabled>
                            {raw} · нет в управляемом списке
                          </option>
                        )}
                        {tlsProfileIDs.map((id) => (
                          <option key={id} value={id}>
                            {id}
                          </option>
                        ))}
                      </select>
                      {!tlsProfileIDs.length && (
                        <small className="muted">
                          Нет доступного управляемого профиля TLS.
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
                        <option value="">Выберите экземпляр сервиса</option>
                        {deploymentIDs.map((id) => (
                          <option key={id} value={id}>
                            {id}
                          </option>
                        ))}
                      </select>
                      {!deploymentIDs.length && (
                        <small className="muted">
                          Нет доступного управляемого экземпляра сервиса.
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
                        !draftChanged ||
                        value === undefined ||
                        invalidNumber ||
                        invalidTextValue
                      }
                      onClick={async () => {
                        const next: ConfigurationIntent = {
                          operation: "SetServiceConfigurationValue",
                          deploymentId,
                          scope: "MEMBER",
                          memberId: member.memberId,
                          setting: setting.id,
                          value: value as Value,
                        };
                        return pending
                          ? onAmend(pending, next)
                          : onAppend(next);
                      }}
                    >
                      Применить
                    </button>
                    <button
                      className="outline"
                      disabled={
                        disabled ||
                        (!savedOverride && !pending && !draftChanged) ||
                        (!!pending &&
                          pending.operation ===
                            "RemoveServiceConfigurationOverride")
                      }
                      onClick={async () => {
                        if (!savedOverride && !pending) {
                          setDrafts((old) => {
                            const next = { ...old };
                            delete next[draftKey];
                            return next;
                          });
                          return;
                        }
                        const next: ConfigurationIntent = {
                          operation: "RemoveServiceConfigurationOverride",
                          deploymentId,
                          scope: "MEMBER",
                          memberId: member.memberId,
                          setting: setting.id,
                        };
                        const accepted = pending
                          ? await onAmend(pending, savedOverride ? next : null)
                          : await onAppend(next);
                        if (accepted)
                          setDrafts((old) => {
                            const updated = { ...old };
                            delete updated[draftKey];
                            return updated;
                          });
                      }}
                    >
                      Сбросить
                    </button>
                  </div>
                </div>
              ) : (
                <p className="muted">
                  Этот параметр доступен только для просмотра в текущем
                  интерфейсе.
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
