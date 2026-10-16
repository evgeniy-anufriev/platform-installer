import { useRef, useState } from "react";
import { ApplicationSecretInputs } from "./ApplicationSecretInputs";
import { ApplicationBindings } from "./ApplicationBindings";
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
  choosePackage,
  onImport,
  draftActive,
  backendError,
  onProviderSecrets,
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
  const [tab, setTab] = useState("Общее");
  const [search, setSearch] = useState("");
  const [formEpoch, setFormEpoch] = useState(0);
  const [create, setCreate] = useState(false);
  const [id, setId] = useState("");
  const [ref, setRef] = useState("");
  const [runtime, setRuntime] = useState("");
  const [local, setLocal] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  // One public descriptor query per saved revision while this page is open.
  // A fresh query intentionally invalidates attached service inputs on the backend.
  const secretDescriptors = useRef<
    RuntimeSecretDescriptorOperation | undefined
  >(undefined);
  const loadApplicationSecrets = async () => {
    if (
      secretDescriptors.current &&
      secretDescriptors.current.projectRevision === managed?.projectRevision
    )
      return secretDescriptors.current;
    const result = await loadSecrets!();
    secretDescriptors.current = result.status === "READY" ? result : undefined;
    return result;
  };
  const saveApplicationSecrets = async (input: RuntimeSecretValuesInput) => {
    try {
      await saveSecrets!(input);
    } catch (error) {
      secretDescriptors.current = undefined;
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
  const recipe = objectValue(definition.slots);
  const bindingHints: Record<string, string> = {};
  for (const raw of Object.values(recipe)) {
    const def = packageDefinition(
      "application",
      objectValue(raw).applicationRef,
    );
    for (const connection of Object.values(objectValue(def.connections))) {
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
  const defaults = objectValue(appDefinition.defaults);
  const authored = objectValue(objectValue(library.applications)[slot]);
  const overrides = objectValue(authored.overrides);
  const change = (key: string, value: string) => {
    setLocal((v) => ({ ...v, [key]: value }));
    onDirtyChange(true);
  };
  const clearLocal = () => {
    setLocal({});
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
    <div className="application-field" key={key}>
      <label>
        {label}
        {type === "multiline" ? (
          <textarea
            value={local[key] ?? String(authoredValue ?? defaultValue ?? "")}
            disabled={busy}
            onChange={(e) => change(key, e.target.value)}
          />
        ) : (
          <input
            type={type}
            min={type === "number" ? 1 : undefined}
            max={type === "number" ? 65535 : undefined}
            value={local[key] ?? String(authoredValue ?? defaultValue ?? "")}
            onChange={(e) => change(key, e.target.value)}
            disabled={busy}
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
            disabled={busy || authoredValue === undefined}
            onClick={() => void reset().then((ok) => clearField(key, ok))}
          >
            Сбросить к default
          </button>
        )}
      </div>
    </div>
  );
  const tabs = slot
    ? ["Параметры", "Секреты", "УЗ и файлы", "Endpoint", "Расчёт и состояние"]
    : ["Общее", "Подключения", "Ресурсы и секреты", "Размещение"];
  const selectedTab = tabs.includes(tab) ? tab : tabs[0];
  const resolved = snapshot?.applicationLibraries?.libraries?.[selected];
  return (
    <section className="applications-page">
      <header className="page-heading">
        <div>
          <h1>Приложения</h1>
          <p>Библиотеки, приложения из recipe и явные переопределения</p>
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
              <label>
                Пакет
                <select
                  value={ref}
                  onChange={(e) => {
                    setRef(e.target.value);
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
                  value={runtime}
                  onChange={(e) => {
                    setRuntime(e.target.value);
                    markChildDirty(true, "create");
                  }}
                >
                  <option value="">Выберите deployment</option>
                  {Object.keys(managed?.deployments ?? {}).map((key) => (
                    <option key={key}>{key}</option>
                  ))}
                </select>
              </label>
              <p>Совместимость runtime и пакета проверяет Core.</p>
              <button
                disabled={busy || !id || !ref || !runtime}
                onClick={() =>
                  void send({
                    operation: "CreateApplicationLibraryDeployment",
                    deploymentId: id,
                    entity: { libraryRef: ref, runtimeRef: runtime },
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
                <h2>
                  {slot ? `Приложение · ${slot}` : `Библиотека · ${selected}`}
                </h2>
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
                          "Удалить authored настройки slot? Recipe defaults сохраняются; это не отключает приложение и не удаляет runtime ресурсы.",
                        )
                      )
                        void send({
                          operation: "RemoveApplicationLibrarySlot",
                          deploymentId: selected,
                          entityId: slot,
                        });
                    }}
                  >
                    Сбросить настройки slot
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
                    <p>
                      ID: {selected} · Runtime: {String(library.runtimeRef)}
                    </p>
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
                    {scalar(
                      "runtimeRef",
                      "Docker runtime deployment",
                      undefined,
                      library.runtimeRef,
                      (value) =>
                        send({
                          operation: "UpdateApplicationLibraryDeployment",
                          deploymentId: selected,
                          entity: { runtimeRef: value },
                        }),
                    )}
                    <button
                      className="outline"
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Удалить библиотеку из проекта? Установленные ресурсы этим действием не удаляются. Сначала удалите размещения.",
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
                  </>
                )}
                {!slot &&
                  selectedTab === "Размещение" &&
                  Object.keys(managed?.servers ?? {}).map((host) => (
                    <div className="row" key={host}>
                      <span>{host}</span>
                      <button
                        disabled={busy}
                        onClick={() =>
                          void send({
                            operation: Object.hasOwn(
                              placements[host] ?? {},
                              selected,
                            )
                              ? "RemoveApplicationLibraryPlacement"
                              : "SetApplicationLibraryPlacement",
                            deploymentId: selected,
                            hostId: host,
                            ...(Object.hasOwn(placements[host] ?? {}, selected)
                              ? {}
                              : { placement: {} }),
                          })
                        }
                      >
                        {Object.hasOwn(placements[host] ?? {}, selected)
                          ? "Убрать размещение"
                          : "Разместить"}
                      </button>
                    </div>
                  ))}
                {!slot && selectedTab === "Размещение" && (
                  <section>
                    <label>
                      Настройки membership хоста
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
                            label={field + " · membership хоста, все slots"}
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
                  </section>
                )}
                {!slot && selectedTab === "Подключения" && (
                  <>
                    <p>
                      deploymentRef выбирает существующий deployment; profileRef
                      — PKI профиль. Совместимость проверяет Core.
                    </p>
                    <ApplicationBindings
                      key={selected + "bindings"}
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
                    <ApplicationValueFields
                      key={selected + "vault"}
                      label="Vault reference"
                      value={objectValue(library.vault_ref)}
                      defaults={{}}
                      disabled={busy}
                      onDirtyChange={(v) => markChildDirty(v, "vault")}
                      onSave={(vault_ref) =>
                        send({
                          operation: "UpdateApplicationLibraryDeployment",
                          deploymentId: selected,
                          entity: { vault_ref },
                        })
                      }
                    />
                  </>
                )}
                {!slot && selectedTab === "Ресурсы и секреты" && (
                  <>
                    <ApplicationValueFields
                      key={selected + "resources"}
                      label="Общие ресурсы"
                      value={objectValue(library.resources)}
                      defaults={objectValue(definition.resources)}
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
                        <CredentialSourceEditor
                          key={selected + name + JSON.stringify(source)}
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
                      );
                    })}
                  </>
                )}
                {slot && selectedTab === "Параметры" && (
                  <>
                    {scalar(
                      "image",
                      "Образ · image",
                      defaults.image,
                      overrides.image,
                      (v) => send(override("image", v)),
                      () => send(remove("image")),
                    )}
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
                    <p>
                      Поля показывают пакет приложения и authored overrides.
                      Recipe и host overrides проверяйте в последнем расчёте
                      Core.
                    </p>
                    <ApplicationValueFields
                      key={selected + slot + "readiness"}
                      label="Readiness"
                      value={objectValue(overrides.readiness)}
                      defaults={objectValue(defaults.readiness)}
                      disabled={busy}
                      onDirtyChange={(v) => markChildDirty(v, "readiness")}
                      onSave={(value) =>
                        send(
                          Object.keys(value).length
                            ? override("readiness", value)
                            : remove("readiness"),
                        )
                      }
                    />
                    <h3>Порты</h3>
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
                    {(["parameters", "environment"] as const).map((field) => (
                      <ApplicationValueFields
                        key={selected + slot + field}
                        label={
                          field === "parameters" ? "Параметры" : "Environment"
                        }
                        value={objectValue(overrides[field])}
                        defaults={objectValue(defaults[field])}
                        disabled={busy}
                        onDirtyChange={(v) => markChildDirty(v, field)}
                        onSave={(value) =>
                          send(
                            Object.keys(value).length
                              ? override(field, value)
                              : remove(field),
                          )
                        }
                      />
                    ))}
                  </>
                )}
                {slot && selectedTab === "Секреты" && (
                  <>
                    <h3>Credentials всех подключений</h3>
                    <p>
                      Источники credentials — настройки проекта; значения
                      секретов — только сессия.
                    </p>
                    {scalar(
                      "vault_binding",
                      "Vault binding приложения",
                      undefined,
                      objectValue(authored.credentials).vault_binding,
                      (v) =>
                        send({
                          operation: "SetApplicationLibrarySlot",
                          deploymentId: selected,
                          entityId: slot,
                          entity: {
                            credentials: {
                              ...objectValue(authored.credentials),
                              vault_binding: v,
                            },
                          },
                        }),
                      () =>
                        send({
                          operation: "SetApplicationLibrarySlot",
                          deploymentId: selected,
                          entityId: slot,
                          entity: { credentials: {} },
                        }),
                    )}
                    <ApplicationCredentials
                      bindings={objectValue(library.bindings)}
                      onProviderSecrets={
                        onProviderSecrets
                          ? (deployment) =>
                              navigate(() => onProviderSecrets(deployment))
                          : undefined
                      }
                      onDirtyChange={markChildDirty}
                      defaults={defaults}
                      authored={authored}
                      connections={objectValue(appDefinition.connections)}
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
                    <ApplicationValueFields
                      key={selected + slot + "provisioner"}
                      label="Vault Agent · provisioner и variable bindings"
                      value={objectValue(overrides.provisioner)}
                      defaults={objectValue(defaults.provisioner)}
                      disabled={busy}
                      onDirtyChange={(v) => markChildDirty(v, "provisioner")}
                      onSave={(value) =>
                        send(
                          Object.keys(value).length
                            ? override("provisioner", value)
                            : remove("provisioner"),
                        )
                      }
                    />
                    {loadSecrets && saveSecrets && (
                      <ApplicationSecretInputs
                        disabled={busy || draftActive || dirty}
                        key={selected + slot + managed?.projectRevision}
                        title={"Секреты: " + selected + " / " + slot}
                        load={loadApplicationSecrets}
                        save={saveApplicationSecrets}
                        libraryId={selected}
                      />
                    )}
                    {draftActive && (
                      <p>
                        Для сессионного ввода сначала сохраните проект и
                        проверьте текущую ревизию.
                      </p>
                    )}
                  </>
                )}
                {slot && selectedTab === "УЗ и файлы" && (
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
                {slot && selectedTab === "Endpoint" && (
                  <>
                    <p>
                      Публикацию и совместимость backend/TLS проверяет Core.
                    </p>
                    <ApplicationValueFields
                      key={selected + slot + "endpoint"}
                      label="Endpoint"
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
                  </>
                )}
                {slot && selectedTab === "Расчёт и состояние" && (
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
                    <p>
                      Running / connection checks / endpoint Verify: нет текущих
                      данных наблюдения. Результаты запусков доступны на
                      странице установки.
                    </p>
                  </>
                )}
              </div>
            </>
          )}
          <footer>
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
