import { useCallback, useEffect, useRef, useState } from "react";
import { ApplicationLibraryResources } from "./ApplicationLibraryResources";
import { ApplicationTopicBindings } from "./ApplicationTopicBindings";
import { ApplicationPorts, type PortSource } from "./ApplicationPorts";
import { ApplicationReadiness } from "./ApplicationReadiness";
import { ApplicationRegistryCredentials } from "./ApplicationRegistryCredentials";
import { ApplicationBindings } from "./ApplicationBindings";
import { ApplicationSecretBindings } from "./ApplicationSecretBindings";
import { ApplicationCredentials } from "./ApplicationCredentials";
import { ApplicationValueFields } from "./ApplicationValueFields";
import { CredentialSourceEditor } from "./ApplicationCredentials";
import { ApplicationFileSettings } from "./ApplicationFileSettings";
import { ApplicationPackageImport } from "./ApplicationPackageImport";
import type {
  OpenResult,
  RuntimeSecretDescriptorOperation,
  RuntimeSecretValuesInput,
} from "./backend";
import "./applications.css";

import {
  applicationDraft,
  objectValue,
  type ApplicationIntent,
  type ObjectValue,
} from "./application-draft";
export {
  isApplicationIntent,
  type ApplicationIntent,
} from "./application-draft";

export function ApplicationsPage({
  managed,
  snapshot,
  intents,
  busy,
  onAppend,
  onAmend,
  onReview,
  onInstallation,
  onDirtyChange,
  loadSecrets,
  saveSecrets,
  loadSecretAvailability,
  executionContextKey = "",
  choosePackage,
  onImport,
  draftActive,
  backendError,
}: {
  choosePackage?: () => Promise<string>;
  onImport: (
    source: string,
    kind: string,
    name: string,
    version: string,
    digest: string,
  ) => Promise<boolean>;
  draftActive: boolean;
  backendError?: string;
  onProviderSecrets?: (deploymentId: string) => void;
  loadSecrets?: () => Promise<RuntimeSecretDescriptorOperation>;
  saveSecrets?: (input: RuntimeSecretValuesInput) => Promise<void>;
  loadSecretAvailability?: () => Promise<RuntimeSecretDescriptorOperation>;
  executionContextKey?: string;
  managed: OpenResult["managed"];
  snapshot: OpenResult["snapshot"];
  intents: ApplicationIntent[];
  busy: boolean;
  onAppend: (intent: ApplicationIntent) => Promise<boolean>;
  onAmend: (
    previous: ApplicationIntent,
    replacement: ApplicationIntent | null,
  ) => Promise<boolean>;
  onReview: () => void;
  onInstallation: () => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const { libraries, placements } = applicationDraft(managed, intents);
  const packages = objectValue(managed?.applicationPackages);
  const [selected, setSelected] = useState("");
  const [slot, setSlot] = useState("");
  const [hostOverrides, setHostOverrides] = useState("");
  const [hostSettingsOpen, setHostSettingsOpen] = useState(false);
  const [tab, setTab] = useState("Общее");
  const [search, setSearch] = useState("");
  const [formEpoch, setFormEpoch] = useState(0);
  const [addingEnvironment, setAddingEnvironment] = useState(false);
  const [create, setCreate] = useState(false);
  const [id, setId] = useState("");
  const [ref, setRef] = useState("");
  const [runtime, setRuntime] = useState("");
  const runtimeOptions = Object.entries(managed?.deployments ?? {})
    .filter(([, row]) => row.serviceType === "docker")
    .map(([key]) => key);
  const selectedRuntime =
    runtime || (runtimeOptions.length === 1 ? runtimeOptions[0] : "");
  const [local, setLocal] = useState<Record<string, string>>({});
  const [editing, setEditing] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  // One public descriptor query per saved revision and execution context.
  // A fresh query intentionally invalidates attached service inputs on the backend.
  const secretDescriptors = useRef<
    { context: string; operation: RuntimeSecretDescriptorOperation } | undefined
  >(undefined);
  const descriptorContext = JSON.stringify([
    managed?.projectRevision,
    executionContextKey,
  ]);
  const secretScope = JSON.stringify([
    selected,
    slot,
    managed?.projectRevision,
    executionContextKey,
  ]);
  const [secretAvailability, setSecretAvailability] = useState<{
    value: RuntimeSecretDescriptorOperation;
    snapshot: OpenResult["snapshot"];
    scope: string;
  }>();
  const availabilityGeneration = useRef(0);
  const availabilityQueue = useRef<Promise<void>>(Promise.resolve());
  const secretDescriptorLoad = useRef<
    | {
        context: string;
        promise: Promise<RuntimeSecretDescriptorOperation>;
      }
    | undefined
  >(undefined);
  const loadApplicationSecrets = useCallback(async () => {
    if (
      secretDescriptors.current &&
      secretDescriptors.current.context === descriptorContext
    )
      return secretDescriptors.current.operation;
    const revision = managed?.projectRevision ?? "";
    if (secretDescriptorLoad.current?.context === descriptorContext)
      return secretDescriptorLoad.current.promise;
    const promise = loadSecrets!()
      .then((result) => {
        if (secretDescriptorLoad.current?.promise === promise) {
          secretDescriptors.current =
            result.status === "READY" && result.projectRevision === revision
              ? { context: descriptorContext, operation: result }
              : undefined;
        }
        return result;
      })
      .finally(() => {
        if (secretDescriptorLoad.current?.promise === promise)
          secretDescriptorLoad.current = undefined;
      });
    secretDescriptorLoad.current = { context: descriptorContext, promise };
    return promise;
  }, [loadSecrets, managed?.projectRevision, descriptorContext]);
  const refreshSecretAvailability = useCallback(() => {
    const generation = ++availabilityGeneration.current;
    const request = availabilityQueue.current
      .catch(() => {})
      .then(async () => {
        if (generation !== availabilityGeneration.current) return;
        try {
          const cached = secretDescriptors.current;
          const descriptors =
            cached?.context === descriptorContext
              ? cached.operation
              : undefined;
          const result = await loadSecretAvailability!();
          if (generation !== availabilityGeneration.current) return;
          setSecretAvailability(
            result.status === "READY" &&
              result.projectRevision === managed?.projectRevision &&
              descriptors?.status === "READY" &&
              result.descriptorSetFingerprint ===
                descriptors.descriptorSetFingerprint
              ? {
                  value: {
                    ...descriptors,
                    applicationSecretAvailability:
                      result.applicationSecretAvailability,
                  },
                  snapshot,
                  scope: secretScope,
                }
              : undefined,
          );
        } catch {
          if (generation === availabilityGeneration.current)
            setSecretAvailability(undefined);
        }
      });
    availabilityQueue.current = request;
    return request;
  }, [
    loadSecretAvailability,
    managed?.projectRevision,
    snapshot,
    secretScope,
    descriptorContext,
  ]);
  const saveApplicationSecrets = async (input: RuntimeSecretValuesInput) => {
    ++availabilityGeneration.current;
    setSecretAvailability(undefined);
    try {
      await saveSecrets!(input);
      if (loadSecretAvailability) await refreshSecretAvailability();
    } catch (error) {
      secretDescriptors.current = undefined;
      ++availabilityGeneration.current;
      setSecretAvailability(undefined);
      throw error;
    }
  };
  const childDirtyKeys = useRef(new Set<string>());
  const [childDirty, setChildDirty] = useState(false);
  const dirty = Object.keys(local).length > 0 || childDirty;
  const markChildDirty = (value: boolean, key = "active") => {
    if (value) childDirtyKeys.current.add(key);
    else childDirtyKeys.current.delete(key);
    setChildDirty(childDirtyKeys.current.size > 0);
    onDirtyChange(
      childDirtyKeys.current.size > 0 || Object.keys(local).length > 0,
    );
  };
  const library = libraries[selected] ?? {};
  const packageDefinition = (kind: string, reference: unknown) =>
    objectValue(
      objectValue(packages[kind + ":" + String(reference)]).definition,
    );
  const definition = packageDefinition("library", library.libraryRef);
  const declaredConnections = (value: unknown): ObjectValue =>
    Array.isArray(value)
      ? Object.fromEntries(
          value.map((key) => [
            String(key),
            objectValue(objectValue(definition.connections)[String(key)]),
          ]),
        )
      : objectValue(value);
  const recipe = objectValue(definition.slots);
  const bindingHints: Record<string, string> = {};
  for (const raw of Object.values(recipe)) {
    const def = packageDefinition(
      "application",
      objectValue(raw).applicationRef,
    );
    for (const connection of Object.values(
      declaredConnections(def.connections),
    )) {
      const name = objectValue(connection).library_binding;
      if (typeof name === "string") bindingHints[name] = "deployment";
    }
  }
  for (const raw of Object.values(objectValue(definition.shared_secrets))) {
    const source = objectValue(objectValue(raw).source);
    if (source.kind === "pki_credential" && typeof source.binding === "string")
      bindingHints[source.binding] = "pki";
  }
  const slotDefinition = objectValue(recipe[slot]);
  const appDefinition = packageDefinition(
    "application",
    slotDefinition.applicationRef,
  );
  const appConnections = declaredConnections(appDefinition.connections);
  const defaults = objectValue(appDefinition.defaults);
  const authored = objectValue(objectValue(library.applications)[slot]);
  const overrides = objectValue(authored.overrides);
  const change = (key: string, value: string) => {
    setLocal((v) => ({ ...v, [key]: value }));
    onDirtyChange(true);
  };
  const clearLocal = () => {
    setAddingEnvironment(false);
    setLocal({});
    setEditing(new Set());
    setChildDirty(false);
    childDirtyKeys.current.clear();
    setFormEpoch((v) => v + 1);
    onDirtyChange(false);
  };
  const navigate = (next: () => void) => {
    if (
      dirty &&
      !window.confirm(
        "Отбросить несохранённый ввод формы? Изменения, уже добавленные в черновик проекта, сохранятся.",
      )
    )
      return;
    clearLocal();
    setError("");
    next();
  };
  const send = async (c: ApplicationIntent) => {
    const pendingCreate =
      c.operation === "UpdateApplicationLibraryDeployment"
        ? intents.find(
            (p) =>
              p.deploymentId === c.deploymentId &&
              p.operation === "CreateApplicationLibraryDeployment",
          )
        : undefined;
    const previous =
      pendingCreate ??
      [...intents]
        .reverse()
        .find(
          (p) =>
            p.deploymentId === c.deploymentId &&
            p.entityId === c.entityId &&
            p.hostId === c.hostId &&
            p.setting === c.setting &&
            p.property === c.property &&
            p.operation.replace(/^(Set|Remove)/, "") ===
              c.operation.replace(/^(Set|Remove)/, ""),
        );
    try {
      if (
        previous &&
        c.entity &&
        (c.operation === "UpdateApplicationLibraryDeployment" ||
          c.operation === "SetApplicationLibrarySlot")
      )
        c = { ...c, entity: { ...previous.entity, ...c.entity } };
      if (pendingCreate)
        c = { ...c, operation: "CreateApplicationLibraryDeployment" };
      const ok = previous ? await onAmend(previous, c) : await onAppend(c);
      if (ok) {
        setError("");
      }
      return ok;
    } catch {
      setError(
        "Не удалось добавить изменение. Проверьте состояние черновика и повторите.",
      );
      return false;
    }
  };
  const override = (
    setting: string,
    value: unknown,
    property?: string,
  ): ApplicationIntent => ({
    operation: "SetApplicationLibraryOverride",
    deploymentId: selected,
    entityId: slot,
    setting,
    ...(property ? { property } : {}),
    value,
  });
  const remove = (setting: string, property?: string): ApplicationIntent => ({
    operation: "RemoveApplicationLibraryOverride",
    deploymentId: selected,
    entityId: slot,
    setting,
    ...(property ? { property } : {}),
  });
  const clearField = (key: string, ok: boolean) => {
    if (!ok) return;
    const next = { ...local };
    delete next[key];
    setLocal(next);
    onDirtyChange(childDirty || Object.keys(next).length > 0);
  };
  const scalar = (
    key: string,
    label: string,
    defaultValue: unknown,
    authoredValue: unknown,
    save: (v: string) => Promise<boolean>,
    reset?: () => Promise<boolean>,
    type = "text",
  ) => (
    <div
      className={
        "application-field" +
        (key === "image" ? " application-image-field" : "")
      }
      key={key}
    >
      <div className="application-field-origin">
        <span>
          {authoredValue === undefined
            ? defaultValue === undefined
              ? "Не задано в пакете"
              : "Из пакета"
            : "Переопределено"}
        </span>
        <button
          className="application-link"
          type="button"
          disabled={busy}
          aria-label={`Переопределить: ${label}`}
          onClick={() => setEditing((current) => new Set(current).add(key))}
        >
          Переопределить
        </button>
      </div>
      <label>
        {label}
        {type === "multiline" ? (
          <textarea
            value={local[key] ?? String(authoredValue ?? defaultValue ?? "")}
            disabled={
              busy || (authoredValue === undefined && !editing.has(key))
            }
            onChange={(e) => change(key, e.target.value)}
          />
        ) : (
          <input
            type={type}
            placeholder={
              key.startsWith("port:") && defaultValue === undefined
                ? "См. источники портов"
                : undefined
            }
            min={type === "number" ? 1 : undefined}
            max={type === "number" ? 65535 : undefined}
            value={local[key] ?? String(authoredValue ?? defaultValue ?? "")}
            onChange={(e) => change(key, e.target.value)}
            disabled={
              busy || (authoredValue === undefined && !editing.has(key))
            }
          />
        )}
      </label>
      <small>
        {authoredValue !== undefined
          ? "Переопределено в экземпляре"
          : "Значение пакета · без вычисления Ansible"}
      </small>
      <div className="row">
        <button
          hidden={key === "image" && local[key] === undefined}
          disabled={
            busy ||
            local[key] === undefined ||
            (type === "number" &&
              (!Number.isInteger(Number(local[key])) ||
                Number(local[key]) < 1 ||
                Number(local[key]) > 65535))
          }
          onClick={() =>
            void save(local[key]).then((ok) => clearField(key, ok))
          }
        >
          В черновик
        </button>
        {reset && (
          <button
            className="outline"
            hidden={key === "image" && authoredValue === undefined}
            disabled={busy || authoredValue === undefined}
            onClick={() =>
              void reset().then((ok) => {
                clearField(key, ok);
                if (ok)
                  setEditing((current) => {
                    const next = new Set(current);
                    next.delete(key);
                    return next;
                  });
              })
            }
          >
            Сбросить к default
          </button>
        )}
      </div>
    </div>
  );
  const tabs = slot
    ? ["Основное", "Секреты", "Файлы", "Запуск", "Состояние"]
    : ["Общее", "Общие параметры", "Подключения", "Ресурсы и секреты"];
  const selectedTab = tabs.includes(tab) ? tab : tabs[0];
  const resolved = snapshot?.applicationLibraries?.libraries?.[selected];
  const freshSecrets =
    !busy &&
    !draftActive &&
    !dirty &&
    intents.length === 0 &&
    snapshot?.projectRevision === managed?.projectRevision;
  const secretContext = JSON.stringify([
    selected,
    slot,
    managed?.projectRevision,
    freshSecrets,
  ]);
  useEffect(() => {
    ++availabilityGeneration.current;
    if (
      !slot ||
      selectedTab !== "Секреты" ||
      !freshSecrets ||
      !loadSecrets ||
      !loadSecretAvailability
    )
      return;
    let active = true;
    let pending = false;
    const refresh = async () => {
      if (!active || pending) return;
      pending = true;
      try {
        await refreshSecretAvailability();
      } finally {
        pending = false;
      }
    };
    // Descriptor discovery is an explicit context-entry operation, never a poll.
    void loadApplicationSecrets()
      .then(() => {
        if (active) void refresh();
      })
      .catch(() => {
        if (active) setSecretAvailability(undefined);
      });
    const interval = window.setInterval(() => void refresh(), 10000);
    window.addEventListener("focus", refresh);
    return () => {
      active = false;
      ++availabilityGeneration.current;
      window.clearInterval(interval);
      window.removeEventListener("focus", refresh);
    };
  }, [
    secretContext,
    slot,
    selectedTab,
    freshSecrets,
    loadSecrets,
    loadSecretAvailability,
    loadApplicationSecrets,
    refreshSecretAvailability,
  ]);
  const resolvedSecretAccounts = freshSecrets
    ? objectValue(
        Object.values(resolved?.instances ?? {}).find(
          (instance) => instance.slotId === slot,
        )?.credentialRequirements,
      )
    : {};
  const secretRefCounts: Record<string, number> = {};
  for (const resolvedLibrary of Object.values(
    snapshot?.applicationLibraries?.libraries ?? {},
  )) {
    for (const secret of Object.values(
      objectValue(resolvedLibrary.sharedSecretRequirements),
    )) {
      const source = objectValue(objectValue(secret).source);
      if (
        source.kind === "runtime_secret_ref" &&
        typeof source.ref === "string"
      )
        secretRefCounts[source.ref] = (secretRefCounts[source.ref] ?? 0) + 1;
    }
    for (const instance of Object.values(resolvedLibrary.instances ?? {})) {
      for (const account of Object.values(
        objectValue(instance.credentialRequirements),
      )) {
        for (const credential of Object.values(
          objectValue(objectValue(account).credentials),
        )) {
          const source = objectValue(objectValue(credential).source);
          if (
            source.kind === "runtime_secret_ref" &&
            typeof source.ref === "string"
          )
            secretRefCounts[source.ref] =
              (secretRefCounts[source.ref] ?? 0) + 1;
        }
      }
    }
  }
  const resolvedTopics =
    !draftActive && snapshot?.projectRevision === managed?.projectRevision
      ? objectValue(resolved?.topics)
      : {};
  const resolvedResources =
    !draftActive && snapshot?.projectRevision === managed?.projectRevision
      ? objectValue(resolved?.resources)
      : {};
  const [baselineHost, setBaselineHost] = useState("");
  const instancePlacements =
    Object.values(resolved?.instances ?? {}).find(
      (instance) => instance.slotId === slot,
    )?.placements ?? {};
  const hosts = Object.keys(instancePlacements);
  const selectedBaselineHost = hosts.includes(baselineHost)
    ? baselineHost
    : hosts[0];
  const inherited = objectValue(
    objectValue(instancePlacements[selectedBaselineHost]).inherited,
  );
  const commonActive =
    slotDefinition.inherit_defaults !== false &&
    (Object.keys(objectValue(definition.defaults)).length > 0 ||
      Object.keys(objectValue(library.overrides)).length > 0);
  const freshBaseline =
    snapshot?.projectRevision === managed?.projectRevision &&
    !draftActive &&
    intents.length === 0 &&
    Object.keys(inherited).length > 0;
  const startupDefaults = freshBaseline
    ? inherited
    : commonActive
      ? {}
      : defaults;
  const portSources: PortSource[] = [
    { label: "Пакет приложения", ports: objectValue(defaults.ports) },
    {
      label: "Пакет библиотеки · " + slot,
      ports: objectValue(objectValue(slotDefinition.overrides).ports),
    },
    { label: "Экземпляр", ports: objectValue(overrides.ports) },
    ...Object.entries(placements)
      .filter(([, members]) => Object.hasOwn(members, selected))
      .map(([host, members]) => ({
        label: "Размещение · " + host,
        ports: objectValue(
          objectValue(objectValue(members[selected]).overrides).ports,
        ),
      })),
    ...Object.entries(resolved?.instances ?? {})
      .filter(([, instance]) => instance.slotId === slot)
      .flatMap(([, instance]) =>
        Object.entries(instance.placements ?? {}).map(([host, placement]) => ({
          label:
            "Core · " +
            host +
            " · " +
            (snapshot?.projectRevision ?? "последняя проверка"),
          ports: objectValue(placement.ports),
        })),
      ),
  ];
  return (
    <section className="applications-page">
      <header className="page-heading">
        <div>
          <h1>Приложения</h1>
          <p>Пакеты, настройки экземпляров и подключения к сервисам</p>
        </div>
        <button className="outline" onClick={() => navigate(onInstallation)}>
          К плану установки
        </button>
      </header>
      {(error || backendError) && <p role="alert">{error || backendError}</p>}
      <div className="applications-layout">
        <aside className="application-list">
          <label>
            Поиск
            <input value={search} onChange={(e) => setSearch(e.target.value)} />
          </label>
          <button
            disabled={busy}
            onClick={() =>
              navigate(() => {
                setCreate(true);
                setSelected("");
                setSlot("");
              })
            }
          >
            Добавить библиотеку
          </button>
          <ApplicationPackageImport
            disabled={busy || draftActive || dirty}
            choose={choosePackage}
            review={onImport}
          />
          {Object.keys(libraries).length === 0 && (
            <p>Библиотеки ещё не добавлены.</p>
          )}
          {Object.entries(libraries)
            .filter(([key, row]) =>
              [
                key,
                String(row.libraryRef),
                ...Object.keys({
                  ...objectValue(
                    packageDefinition("library", row.libraryRef).slots,
                  ),
                  ...objectValue(row.applications),
                }),
              ]
                .join(" ")
                .toLocaleLowerCase()
                .includes(search.toLocaleLowerCase()),
            )
            .map(([key, row]) => (
              <div className="application-group" key={key}>
                <button
                  className="outline"
                  aria-current={selected === key && !slot ? "true" : undefined}
                  onClick={() =>
                    navigate(() => {
                      setSelected(key);
                      setSlot("");
                      setCreate(false);
                    })
                  }
                >
                  <strong>{key}</strong>
                  <small>{String(row.libraryRef)}</small>
                </button>
                {Object.keys({
                  ...objectValue(
                    packageDefinition("library", row.libraryRef).slots,
                  ),
                  ...objectValue(row.applications),
                }).map((name) => (
                  <button
                    className="outline application-slot"
                    key={name}
                    aria-current={
                      selected === key && slot === name ? "true" : undefined
                    }
                    onClick={() =>
                      navigate(() => {
                        setSelected(key);
                        setSlot(name);
                        setCreate(false);
                      })
                    }
                  >
                    ↳ {name}
                  </button>
                ))}
              </div>
            ))}
        </aside>
        <article className="application-editor" key={formEpoch}>
          {create ? (
            <>
              <h2>Добавить библиотеку</h2>
              <label>
                ID библиотеки
                <input
                  value={id}
                  onChange={(e) => {
                    setId(e.target.value);
                    markChildDirty(true, "create");
                  }}
                />
              </label>
              <div className="row">
                <small>
                  По умолчанию — имя выбранной библиотеки. Можно изменить до
                  создания.
                </small>
                <button
                  type="button"
                  className="outline"
                  disabled={busy || !ref || id === ref.split("@")[0]}
                  onClick={() => {
                    setId(ref.split("@")[0]);
                    markChildDirty(true, "create");
                  }}
                >
                  Сбросить ID к имени библиотеки
                </button>
              </div>
              <label>
                Пакет
                <select
                  value={ref}
                  onChange={(e) => {
                    setRef(e.target.value);
                    if (!id || id === ref.split("@")[0])
                      setId(e.target.value.split("@")[0]);
                    markChildDirty(true, "create");
                  }}
                >
                  <option value="">Выберите пакет</option>
                  {Object.values(packages)
                    .map(objectValue)
                    .filter((p) => p.kind === "library")
                    .map((p) => (
                      <option key={String(p.ref)}>{String(p.ref)}</option>
                    ))}
                </select>
              </label>
              <label>
                Docker runtime
                <select
                  value={selectedRuntime}
                  onChange={(e) => {
                    setRuntime(e.target.value);
                    markChildDirty(true, "create");
                  }}
                >
                  <option value="">Выберите deployment</option>
                  {runtimeOptions.map((key) => (
                    <option key={key}>{key}</option>
                  ))}
                </select>
              </label>
              <p>Совместимость runtime и пакета проверяет Core.</p>
              <button
                disabled={busy || !id || !ref || !selectedRuntime}
                onClick={() =>
                  void send({
                    operation: "CreateApplicationLibraryDeployment",
                    deploymentId: id,
                    entity: { libraryRef: ref, runtimeRef: selectedRuntime },
                  }).then((ok) => {
                    if (ok) {
                      markChildDirty(false, "create");
                      setSelected(id);
                      setCreate(false);
                    }
                  })
                }
              >
                В черновик
              </button>
            </>
          ) : !Object.hasOwn(libraries, selected) ? (
            <p>Выберите библиотеку или приложение.</p>
          ) : (
            <>
              <header>
                <div className="application-breadcrumb">
                  <button
                    className="application-link"
                    onClick={() =>
                      navigate(() => {
                        setSlot("");
                        setTab("Общее");
                      })
                    }
                  >
                    {selected}
                  </button>
                  {slot && <span> / {slot}</span>}
                </div>
                <h2>{slot || selected}</h2>
                <small>
                  {String(
                    slot
                      ? (slotDefinition.applicationRef ?? "Пакет недоступен")
                      : library.libraryRef,
                  )}
                </small>
                {slot && (
                  <button
                    className="outline"
                    disabled={busy || !Object.keys(authored).length}
                    onClick={() => {
                      if (
                        window.confirm(
                          "Сбросить настройки экземпляра к пакету? Это не отключает приложение и не удаляет установленные ресурсы.",
                        )
                      )
                        void send({
                          operation: "RemoveApplicationLibrarySlot",
                          deploymentId: selected,
                          entityId: slot,
                        });
                    }}
                  >
                    Сбросить настройки
                  </button>
                )}
                {((slot && selectedTab === "Запуск") ||
                  (!slot && selectedTab === "Общие параметры")) && (
                  <button
                    className="outline"
                    disabled={busy || addingEnvironment}
                    onClick={() => setAddingEnvironment(true)}
                  >
                    Добавить параметр
                  </button>
                )}
                <nav className="application-tabs">
                  {tabs.map((t) => (
                    <button
                      key={t}
                      className="outline"
                      aria-pressed={selectedTab === t}
                      onClick={() => navigate(() => setTab(t))}
                    >
                      {t}
                    </button>
                  ))}
                </nav>
              </header>
              <div className="application-content">
                {!Object.keys(definition).length && (
                  <p role="alert">
                    Определение пакета недоступно. Существующие настройки
                    сохранены.
                  </p>
                )}
                {!slot && selectedTab === "Общее" && (
                  <>
                    <section className="application-library-overview">
                      <h3>Экземпляр библиотеки</h3>
                      <label>
                        ID экземпляра библиотеки
                        <input value={selected} readOnly />
                      </label>
                      <label>
                        Среда контейнеризации
                        <select
                          aria-label="Среда контейнеризации"
                          value={String(library.runtimeRef ?? "")}
                          disabled={busy}
                          onChange={(e) =>
                            void send({
                              operation: "UpdateApplicationLibraryDeployment",
                              deploymentId: selected,
                              entity: { runtimeRef: e.target.value },
                            })
                          }
                        >
                          <option value="">Выберите среду</option>
                          {!!library.runtimeRef &&
                            !Object.hasOwn(
                              managed?.deployments ?? {},
                              String(library.runtimeRef),
                            ) && (
                              <option value={String(library.runtimeRef)}>
                                {String(library.runtimeRef)} · недоступна
                              </option>
                            )}
                          {Object.entries(managed?.deployments ?? {})
                            .filter(
                              ([key, row]) =>
                                row.serviceType === "docker" ||
                                key === library.runtimeRef,
                            )
                            .map(([key]) => (
                              <option key={key}>{key}</option>
                            ))}
                        </select>
                      </label>
                      <label>
                        Каталог библиотеки
                        <input
                          aria-label="Каталог библиотеки"
                          defaultValue={String(library.runtime_directory ?? "")}
                          key={
                            selected + String(library.runtime_directory ?? "")
                          }
                          placeholder={
                            resolved?.runtimeDirectory ||
                            "По умолчанию из пакета: ~/<ID библиотеки>"
                          }
                          disabled={busy}
                          onBlur={(e) => {
                            if (
                              e.target.value !==
                              String(library.runtime_directory ?? "")
                            )
                              void send({
                                operation: "UpdateApplicationLibraryDeployment",
                                deploymentId: selected,
                                entity: { runtime_directory: e.target.value },
                              });
                          }}
                        />
                      </label>
                      <button
                        className="outline"
                        disabled={busy || !library.runtime_directory}
                        onClick={() =>
                          void send({
                            operation: "UpdateApplicationLibraryDeployment",
                            deploymentId: selected,
                            entity: { runtime_directory: "" },
                          })
                        }
                      >
                        По умолчанию
                      </button>
                      <p className="muted">
                        Пакет: {String(library.libraryRef)} · ID задаётся при
                        создании
                      </p>
                    </section>
                    <ApplicationRegistryCredentials
                      key={selected}
                      libraryId={selected}
                      value={library.registry_credentials}
                      registries={resolved?.registries ?? []}
                      disabled={busy}
                      runtimeDisabled={busy || draftActive || dirty}
                      onChange={(value) =>
                        void send({
                          operation: "UpdateApplicationLibraryDeployment",
                          deploymentId: selected,
                          entity: { registry_credentials: value },
                        })
                      }
                      load={loadSecrets ? loadApplicationSecrets : undefined}
                      save={saveSecrets ? saveApplicationSecrets : undefined}
                    />
                    <section className="application-library-placement">
                      <h3>Размещение</h3>
                      <p className="muted">
                        Серверы для экземпляров этой библиотеки
                      </p>
                      {Object.keys(managed?.servers ?? {}).map((host) => (
                        <label className="application-placement" key={host}>
                          <input
                            type="checkbox"
                            checked={Object.hasOwn(
                              placements[host] ?? {},
                              selected,
                            )}
                            disabled={busy}
                            onChange={() =>
                              void send({
                                operation: Object.hasOwn(
                                  placements[host] ?? {},
                                  selected,
                                )
                                  ? "RemoveApplicationLibraryPlacement"
                                  : "SetApplicationLibraryPlacement",
                                deploymentId: selected,
                                hostId: host,
                                ...(Object.hasOwn(
                                  placements[host] ?? {},
                                  selected,
                                )
                                  ? {}
                                  : { placement: {} }),
                              })
                            }
                          />
                          <span>{host}</span>
                        </label>
                      ))}
                    </section>
                    <details className="application-library-package">
                      <summary>Пакет и управление библиотекой</summary>
                      {scalar(
                        "libraryRef",
                        "Пакет · точная версия",
                        undefined,
                        library.libraryRef,
                        (value) =>
                          send({
                            operation: "UpdateApplicationLibraryDeployment",
                            deploymentId: selected,
                            entity: { libraryRef: value },
                          }),
                      )}
                      <button
                        className="outline"
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              "Удалить библиотеку из проекта? Установленные ресурсы сохранятся. Сначала удалите размещения.",
                            )
                          )
                            void send({
                              operation: "DeleteApplicationLibraryDeployment",
                              deploymentId: selected,
                            }).then((ok) => {
                              if (ok) setSelected("");
                            });
                        }}
                      >
                        Удалить из проекта
                      </button>
                    </details>
                  </>
                )}
                {!slot && selectedTab === "Общее" && (
                  <details
                    className="application-host-settings"
                    open={hostSettingsOpen}
                  >
                    <summary
                      onClick={(e) => {
                        e.preventDefault();
                        setHostSettingsOpen((value) => !value);
                      }}
                    >
                      Дополнительные настройки размещения
                    </summary>
                    <p className="muted">
                      Переопределения для всех приложений библиотеки на
                      выбранном сервере. Значения из пакетов сохраняются, пока
                      не заданы переопределения.
                    </p>
                    <label>
                      Сервер для дополнительных настроек
                      <select
                        value={hostOverrides}
                        onChange={(e) =>
                          navigate(() => setHostOverrides(e.target.value))
                        }
                      >
                        <option value="">Выберите размещение</option>
                        {Object.keys(placements)
                          .filter((host) =>
                            Object.hasOwn(placements[host], selected),
                          )
                          .map((host) => (
                            <option key={host}>{host}</option>
                          ))}
                      </select>
                    </label>
                    {hostOverrides &&
                      Object.hasOwn(
                        placements[hostOverrides] ?? {},
                        selected,
                      ) &&
                      (["parameters", "ports"] as const).map((field) => {
                        const member = objectValue(
                          placements[hostOverrides][selected],
                        );
                        return (
                          <ApplicationValueFields
                            key={selected + hostOverrides + field}
                            label={
                              field === "parameters"
                                ? "Параметры приложений"
                                : "Порты приложений"
                            }
                            value={objectValue(
                              objectValue(member.overrides)[field],
                            )}
                            defaults={{}}
                            disabled={busy}
                            onDirtyChange={(v) =>
                              markChildDirty(v, "host-" + field)
                            }
                            onSave={(value) =>
                              send({
                                operation: "SetApplicationLibraryPlacement",
                                deploymentId: selected,
                                hostId: hostOverrides,
                                placement: {
                                  ...member,
                                  overrides: {
                                    ...objectValue(member.overrides),
                                    [field]: value,
                                  },
                                },
                              })
                            }
                          />
                        );
                      })}
                  </details>
                )}
                {!slot && selectedTab === "Общие параметры" && (
                  <>
                    <p className="muted">
                      Общие значения библиотеки. Изменения сохраняются в
                      group_vars; собственные значения приложений задаются в их
                      настройках.
                    </p>
                    {["environment", "parameters"].map((section) => (
                      <ApplicationValueFields
                        key={selected + section + formEpoch}
                        compact={section === "environment"}
                        addControl={
                          section === "environment"
                            ? {
                                adding: addingEnvironment,
                                setAdding: setAddingEnvironment,
                              }
                            : undefined
                        }
                        label={
                          section === "environment"
                            ? "Общие ENV"
                            : "Общие параметры конфигурации"
                        }
                        value={objectValue(
                          objectValue(library.overrides)[section],
                        )}
                        defaults={objectValue(
                          objectValue(definition.defaults)[section],
                        )}
                        disabled={busy}
                        onDirtyChange={(value) =>
                          markChildDirty(value, section)
                        }
                        onSave={(value) =>
                          send(
                            Object.keys(value).length
                              ? override(section, value)
                              : remove(section),
                          )
                        }
                      />
                    ))}
                  </>
                )}
                {!slot && selectedTab === "Подключения" && (
                  <>
                    <ApplicationBindings
                      key={selected + "bindings"}
                      vaultBinding={
                        typeof objectValue(library.vault_ref).binding ===
                        "string"
                          ? String(objectValue(library.vault_ref).binding)
                          : undefined
                      }
                      deploymentTypes={Object.fromEntries(
                        Object.entries(managed?.deployments ?? {}).map(
                          ([id, row]) => [id, row.serviceType],
                        ),
                      )}
                      onSelectVault={(binding) =>
                        send({
                          operation: "UpdateApplicationLibraryDeployment",
                          deploymentId: selected,
                          entity: {
                            vault_ref: {
                              ...objectValue(library.vault_ref),
                              binding,
                            },
                          },
                        })
                      }
                      value={objectValue(library.bindings)}
                      hints={bindingHints}
                      deployments={Object.keys(managed?.deployments ?? {})}
                      profiles={Object.keys(managed?.pki?.tlsProfiles ?? {})}
                      disabled={busy}
                      onDirtyChange={(v) => markChildDirty(v, "bindings")}
                      onSave={(bindings) =>
                        send({
                          operation: "UpdateApplicationLibraryDeployment",
                          deploymentId: selected,
                          entity: { bindings },
                        })
                      }
                    />
                  </>
                )}
                {!slot && selectedTab === "Ресурсы и секреты" && (
                  <>
                    <ApplicationLibraryResources
                      showAddActions={false}
                      deployments={managed?.deployments ?? {}}
                      key={selected + "resources"}
                      resources={objectValue(library.resources)}
                      resolvedTopics={resolvedTopics}
                      resolvedResources={resolvedResources}
                      redisDefaults={objectValue(
                        objectValue(
                          objectValue(definition.resource_defaults).redis,
                        ).keys,
                      )}
                      databaseDefaults={objectValue(
                        objectValue(
                          objectValue(definition.resource_defaults).postgresql,
                        ).databases,
                      )}
                      clickhouseDefaults={objectValue(
                        objectValue(
                          objectValue(definition.resource_defaults).clickhouse,
                        ).databases,
                      )}
                      topicDefaults={objectValue(
                        objectValue(
                          objectValue(definition.resource_defaults).kafka,
                        ).topics,
                      )}
                      bindings={objectValue(library.bindings)}
                      disabled={busy}
                      onDirtyChange={(v) => markChildDirty(v, "resources")}
                      onSave={(resources) =>
                        send({
                          operation: "UpdateApplicationLibraryDeployment",
                          deploymentId: selected,
                          entity: { resources },
                        })
                      }
                    />
                    <h3>Общие секреты · источники</h3>
                    {Object.keys({
                      ...objectValue(definition.shared_secrets),
                      ...objectValue(library.shared_secrets),
                    }).map((name) => {
                      const source = objectValue(
                        objectValue(objectValue(library.shared_secrets)[name])
                          .source,
                      );
                      return (
                        <details
                          key={selected + name + JSON.stringify(source)}
                          className="application-shared-secret"
                        >
                          <summary>
                            {name} ·{" "}
                            {String(
                              source.kind ??
                                objectValue(
                                  objectValue(
                                    objectValue(definition.shared_secrets)[
                                      name
                                    ],
                                  ).source,
                                ).kind ??
                                "Источник пакета",
                            )}
                          </summary>
                          <CredentialSourceEditor
                            label={name}
                            source={source}
                            packageSource={objectValue(
                              objectValue(
                                objectValue(definition.shared_secrets)[name],
                              ).source,
                            )}
                            allowLiteral={false}
                            disabled={busy}
                            onDirtyChange={(v) => markChildDirty(v, name)}
                            onSave={(source) =>
                              send({
                                operation: "UpdateApplicationLibraryDeployment",
                                deploymentId: selected,
                                entity: {
                                  shared_secrets: {
                                    ...objectValue(library.shared_secrets),
                                    [name]: { source },
                                  },
                                },
                              })
                            }
                            onReset={() => {
                              const next = {
                                ...objectValue(library.shared_secrets),
                              };
                              delete next[name];
                              return send({
                                operation: "UpdateApplicationLibraryDeployment",
                                deploymentId: selected,
                                entity: { shared_secrets: next },
                              });
                            }}
                          />
                        </details>
                      );
                    })}
                  </>
                )}
                {slot && selectedTab === "Основное" && (
                  <div className="application-instance-general">
                    <section className="application-section">
                      <div className="application-instance-name">
                        <span>Имя экземпляра · Core</span>
                        <strong>
                          {Object.entries(resolved?.instances ?? {}).find(
                            ([, instance]) => instance.slotId === slot,
                          )?.[0] ?? "Ещё не рассчитано"}
                        </strong>
                        <small>
                          Только чтение · по последней проверке проекта
                        </small>
                      </div>
                      {scalar(
                        "image",
                        "Образ контейнера",
                        defaults.image,
                        overrides.image,
                        (v) => send(override("image", v)),
                        () => send(remove("image")),
                      )}
                    </section>
                    <section
                      className="application-section application-general-summary"
                      aria-label="Сводка конфигурации"
                    >
                      <h3>Библиотека и подключения</h3>
                      <dl className="application-overview-lines">
                        <dt>Размещение</dt>
                        <dd>
                          {Object.keys(placements)
                            .filter((host) =>
                              Object.hasOwn(placements[host] ?? {}, selected),
                            )
                            .join(", ") || "Не задано"}
                        </dd>
                        <dt>Подключения</dt>
                        <dd>
                          {Object.entries(appConnections).map(([name, raw]) => {
                            const binding = String(
                              objectValue(raw).library_binding ?? "",
                            );
                            const target = objectValue(
                              objectValue(library.bindings)[binding],
                            );
                            return (
                              <span
                                key={name}
                                title={`${binding}: ${String(target.deploymentRef ?? target.profileRef ?? "Не задано")}`}
                              >
                                {name}
                              </span>
                            );
                          })}
                        </dd>
                      </dl>
                      <button
                        className="application-link"
                        onClick={() =>
                          navigate(() => {
                            setSlot("");
                            setTab("Подключения");
                          })
                        }
                      >
                        Настроить подключения библиотеки ↗
                      </button>
                    </section>
                    <ApplicationReadiness
                      key={
                        selected + slot + JSON.stringify(overrides.readiness)
                      }
                      value={objectValue(overrides.readiness)}
                      defaults={objectValue(defaults.readiness)}
                      disabled={busy}
                      onDirtyChange={(v) => markChildDirty(v, "readiness")}
                      onSave={(value) => send(override("readiness", value))}
                      onReset={() => send(remove("readiness"))}
                    />
                    <div className="application-general-ports">
                      <ApplicationPorts
                        compact
                        key={selected + slot + "port-sources"}
                        sources={portSources}
                        value={objectValue(overrides.ports)}
                        disabled={busy}
                        onDirtyChange={(v) => markChildDirty(v, "add-port")}
                        onSave={(name, value) =>
                          send(override(name, value, "ports"))
                        }
                      />
                      <section className="application-section application-general-port-overrides">
                        {" "}
                        <h3>Host → Container</h3>
                        {Object.entries({
                          ...objectValue(defaults.ports),
                          ...objectValue(overrides.ports),
                        }).map(([listener, raw]) => {
                          const d = objectValue(
                            objectValue(defaults.ports)[listener],
                          );
                          const a = objectValue(
                            objectValue(overrides.ports)[listener],
                          );
                          return (
                            <fieldset key={listener}>
                              <legend>{listener}</legend>
                              {(
                                [
                                  ["published", "Порт хоста"],
                                  ["container", "Порт контейнера"],
                                ] as const
                              ).map(([side, label]) =>
                                scalar(
                                  `port:${listener}:${side}`,
                                  label,
                                  d[side],
                                  a[side],
                                  (v) =>
                                    send(
                                      override(
                                        listener,
                                        { ...a, [side]: Number(v) },
                                        "ports",
                                      ),
                                    ),
                                  () => {
                                    const remaining = { ...a };
                                    delete remaining[side];
                                    return send(
                                      Object.keys(remaining).length
                                        ? override(listener, remaining, "ports")
                                        : remove(listener, "ports"),
                                    );
                                  },
                                  "number",
                                ),
                              )}
                              {raw === null && <p>Недоступная схема порта</p>}
                            </fieldset>
                          );
                        })}
                      </section>
                      <details className="application-general-endpoint">
                        <summary>Endpoint · публикация HAProxy / DNS</summary>
                        <p>
                          Публикацию и совместимость backend/TLS проверяет Core.
                        </p>
                        <ApplicationValueFields
                          key={selected + slot + "endpoint"}
                          label="Endpoint"
                          compact
                          value={objectValue(overrides.endpoint)}
                          defaults={objectValue(defaults.endpoint)}
                          disabled={busy}
                          onDirtyChange={(v) => markChildDirty(v, "endpoint")}
                          onSave={(value) =>
                            send(
                              Object.keys(value).length
                                ? override("endpoint", value)
                                : remove("endpoint"),
                            )
                          }
                        />
                      </details>
                    </div>
                  </div>
                )}

                {slot && selectedTab === "Запуск" && (
                  <>
                    <ApplicationTopicBindings
                      resolvedTopics={resolvedTopics}
                      connections={appConnections}
                      resources={objectValue(library.resources)}
                      bindings={objectValue(library.bindings)}
                      deployments={managed?.deployments ?? {}}
                      defaults={objectValue(defaults.topicBindings)}
                      authored={objectValue(overrides.topicBindings)}
                      disabled={busy}
                      onSave={(value) => send(override("topicBindings", value))}
                      onReset={() => send(remove("topicBindings"))}
                    />
                    {hosts.length > 1 && (
                      <label>
                        Наследуемые значения для сервера
                        <select
                          value={selectedBaselineHost}
                          onChange={(e) =>
                            navigate(() => setBaselineHost(e.target.value))
                          }
                        >
                          {hosts.map((host) => (
                            <option key={host}>{host}</option>
                          ))}
                        </select>
                      </label>
                    )}
                    {commonActive && !freshBaseline && (
                      <p className="muted">
                        Унаследованные значения требуют проверки сохранённого
                        проекта в Core. ENV показывают исходные defaults пакета
                        и явные переопределения без вычисления Ansible;
                        настройки конфигурации — только явные переопределения.
                      </p>
                    )}
                    <section className="application-section application-startup-policy">
                      <h3>Команда и политика запуска</h3>
                      <div className="application-startup-policy-fields">
                        {scalar(
                          "command",
                          "Команда · каждый аргумент с новой строки",
                          Array.isArray(defaults.command)
                            ? defaults.command.join("\n")
                            : undefined,
                          Array.isArray(overrides.command)
                            ? overrides.command.join("\n")
                            : undefined,
                          (v) => send(override("command", v.split("\n"))),
                          () => send(remove("command")),
                          "multiline",
                        )}
                        {(["user", "restart"] as const).map((field) =>
                          scalar(
                            field,
                            field,
                            defaults[field],
                            overrides[field],
                            (v) => send(override(field, v)),
                            () => send(remove(field)),
                          ),
                        )}
                      </div>
                    </section>
                    <section className="application-section">
                      <ApplicationValueFields
                        key={selected + slot + "environment"}
                        label="Переменные окружения (ENV)"
                        compact
                        addControl={{
                          adding: addingEnvironment,
                          setAdding: setAddingEnvironment,
                        }}
                        value={objectValue(overrides.environment)}
                        defaults={objectValue(
                          freshBaseline
                            ? inherited.environment
                            : defaults.environment,
                        )}
                        resolvedValues={
                          freshBaseline && !dirty && !busy
                            ? objectValue(
                                objectValue(
                                  instancePlacements[selectedBaselineHost],
                                ).environment,
                              )
                            : {}
                        }
                        defaultLabel={
                          freshBaseline
                            ? "Унаследовано · последний расчёт Core"
                            : undefined
                        }
                        disabled={busy}
                        onDirtyChange={(v) => markChildDirty(v, "environment")}
                        onSave={(value) =>
                          send(
                            Object.keys(value).length
                              ? override("environment", value)
                              : remove("environment"),
                          )
                        }
                      />
                      <p className="muted">
                        ENV передаются процессу контейнера.
                      </p>
                    </section>
                    {(Object.keys(objectValue(startupDefaults.parameters))
                      .length > 0 ||
                      commonActive ||
                      Object.keys(objectValue(overrides.parameters)).length >
                        0) && (
                      <section className="application-section">
                        <ApplicationValueFields
                          key={selected + slot + "parameters"}
                          label="Настройки конфигурации"
                          value={objectValue(overrides.parameters)}
                          defaults={objectValue(startupDefaults.parameters)}
                          defaultLabel={
                            freshBaseline
                              ? "Унаследовано · последний расчёт Core"
                              : undefined
                          }
                          disabled={busy}
                          onDirtyChange={(v) => markChildDirty(v, "parameters")}
                          onSave={(value) =>
                            send(
                              Object.keys(value).length
                                ? override("parameters", value)
                                : remove("parameters"),
                            )
                          }
                        />
                        <p className="muted">
                          Значения для шаблонов конфигурации пакета; не ENV.
                        </p>
                      </section>
                    )}
                  </>
                )}

                {slot && selectedTab === "Секреты" && (
                  <>
                    <h3>Секреты подключений</h3>
                    <p>
                      Подключения настраиваются в библиотеке. Здесь — источники
                      секретов, переменные приложения и права. Пароли — только в
                      сессии.
                    </p>
                    <ApplicationCredentials
                      secretSession={
                        loadSecrets && saveSecrets
                          ? {
                              projectRevision: managed?.projectRevision ?? "",
                              contextKey: executionContextKey,
                              libraryId: selected,
                              disabled: busy || !freshSecrets,
                              availability:
                                freshSecrets &&
                                secretAvailability &&
                                secretAvailability?.snapshot === snapshot &&
                                secretAvailability.scope === secretScope
                                  ? secretAvailability.value
                                  : undefined,
                              load: loadApplicationSecrets,
                              save: saveApplicationSecrets,
                            }
                          : undefined
                      }
                      resolvedAccounts={resolvedSecretAccounts}
                      sharedSecretRefs={Object.keys(secretRefCounts).filter(
                        (ref) => secretRefCounts[ref] > 1,
                      )}
                      renderVariables={(account, field) => (
                        <ApplicationSecretBindings
                          credential={{ account, field }}
                          value={objectValue(overrides.provisioner)}
                          defaults={objectValue(defaults.provisioner)}
                          accounts={[]}
                          disabled={busy}
                          onDirtyChange={(v) =>
                            markChildDirty(
                              v,
                              `secret_bindings:${account}:${field}`,
                            )
                          }
                          onSave={(value) =>
                            send(
                              Object.keys(value).length
                                ? override("provisioner", value)
                                : remove("provisioner"),
                            )
                          }
                        />
                      )}
                      variableBindings={{
                        ...objectValue(
                          objectValue(defaults.provisioner).secret_bindings,
                        ),
                        ...objectValue(
                          objectValue(overrides.provisioner).secret_bindings,
                        ),
                      }}
                      resources={objectValue(library.resources)}
                      resolvedResources={resolvedResources}
                      deploymentTypes={Object.fromEntries(
                        Object.entries(managed?.deployments ?? {}).map(
                          ([id, row]) => [id, row.serviceType],
                        ),
                      )}
                      bindings={objectValue(library.bindings)}
                      onDirtyChange={markChildDirty}
                      defaults={defaults}
                      authored={authored}
                      connections={appConnections}
                      disabled={busy}
                      onSave={(accounts) =>
                        send({
                          operation: "SetApplicationLibrarySlot",
                          deploymentId: selected,
                          entityId: slot,
                          entity: { accounts },
                        })
                      }
                    />
                    {draftActive && (
                      <p>
                        Для сессионного ввода сначала сохраните проект и
                        проверьте текущую ревизию.
                      </p>
                    )}
                  </>
                )}
                {slot && selectedTab === "Файлы" && (
                  <>
                    <ApplicationFileSettings
                      key={
                        selected + slot + JSON.stringify(overrides.config_files)
                      }
                      authored={overrides.config_files}
                      defaults={defaults.config_files}
                      disabled={busy}
                      onDirtyChange={(v) => markChildDirty(v, "files")}
                      onSave={(value) => send(override("config_files", value))}
                      onReset={() => send(remove("config_files"))}
                    />
                    <p>
                      AppRole identity и runtime paths разрешает Core. Значения
                      секретов не сохраняются в файлы проекта.
                    </p>
                  </>
                )}

                {slot && selectedTab === "Состояние" && (
                  <>
                    <p>
                      Расчёт для сохранённой ревизии:{" "}
                      {snapshot?.projectRevision ?? "Не рассчитано"}.{" "}
                      {intents.length > 0 && "Есть изменения проекта."}
                    </p>
                    <p>
                      Origin: ANSIBLE / RESOLUTION_SCOPE; точный источник
                      каждого поля не определяется.
                    </p>
                    <details className="application-state-diagnostics">
                      <summary>
                        Рассчитанная конфигурация · диагностика Core
                      </summary>
                      <pre>
                        {JSON.stringify(
                          Object.fromEntries(
                            Object.entries(resolved?.instances ?? {}).filter(
                              ([, instance]) => instance.slotId === slot,
                            ),
                          ),
                          null,
                          2,
                        )}
                      </pre>
                    </details>
                    <p>
                      Работа контейнера, подключения и endpoint Verify: нет
                      текущих данных наблюдения. Результаты запусков доступны на
                      странице установки.
                    </p>
                  </>
                )}
              </div>
            </>
          )}
          <footer>
            <div className="application-draft-status">
              <strong>
                {intents.length
                  ? `В черновике: ${intents.length}`
                  : "Нет изменений"}
              </strong>
              <small>Сохранение не запускает установку</small>
            </div>
            <button
              className="outline"
              disabled={busy || intents.length === 0 || dirty}
              onClick={onReview}
            >
              Показать изменения проекта
            </button>
            {dirty && (
              <span role="status">
                Есть ввод, ещё не добавленный в черновик
              </span>
            )}
          </footer>
        </article>
      </div>
    </section>
  );
}
