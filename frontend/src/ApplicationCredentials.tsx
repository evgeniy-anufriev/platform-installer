import { useRef, useState, type ReactNode } from "react";
import { objectValue } from "./application-draft";
import { ApplicationValueFields } from "./ApplicationValueFields";
import { ApplicationKafkaAccess } from "./ApplicationKafkaAccess";
import {
  ApplicationRuntimeSecretField,
  ApplicationSecretAvailabilityBadge,
  type ApplicationSecretSession,
} from "./ApplicationRuntimeSecretField";
import {
  ApplicationAccountAccess,
  ApplicationRedisAccess,
} from "./ApplicationAccountAccess";

type Obj = Record<string, unknown>;
export function CredentialSourceEditor({
  label,
  source,
  packageSource,
  allowLiteral,
  disabled,
  onSave,
  onReset,
  onDirtyChange,
  compact = false,
  runtimeInput,
  resolvedLiteralValue,
}: {
  label: string;
  source: Obj;
  packageSource: Obj;
  allowLiteral: boolean;
  disabled: boolean;
  onSave: (source: Obj) => Promise<boolean>;
  onReset: () => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
  compact?: boolean;
  runtimeInput?: ReactNode;
  resolvedLiteralValue?: string;
}) {
  const initial = Object.keys(source).length ? source : packageSource;
  const [kind, setKind] = useState(
    String(initial.kind ?? "runtime_secret_ref"),
  );
  const [values, setValues] = useState<Obj>({ ...initial });
  const [dirty, setDirty] = useState(false);
  const [valueFocused, setValueFocused] = useState(false);
  const showResolvedLiteral =
    kind === "literal" &&
    !dirty &&
    !valueFocused &&
    resolvedLiteralValue !== undefined;
  const fields: Record<string, string[]> = {
    generated: [],
    runtime_secret_ref: ["ref"],
    vault_ref: ["binding", "mount", "document", "field"],
    pki_credential: ["binding", "credential"],
    literal: ["value"],
  };
  const labels: Record<string, string> = {
    ref: "Runtime secret ref · имя ссылки",
    binding: "Binding",
    mount: "Vault mount",
    document: "Vault document",
    field: "Поле секрета",
    credential: "PKI credential",
    value: "Имя пользователя",
  };
  const keys = fields[kind] ?? [];
  const change = () => {
    setDirty(true);
    onDirtyChange(true);
  };
  const finish = (ok: boolean) => {
    if (ok) {
      setDirty(false);
      onDirtyChange(false);
    }
  };
  return (
    <fieldset
      className={
        compact
          ? `application-credential-source${keys.length > 1 ? " application-credential-source-expanded" : ""}`
          : undefined
      }
      title={
        compact
          ? `Пакет: ${String(packageSource.kind ?? "Не объявлен")} · ${Object.keys(source).length ? "Явное переопределение" : "Наследуется"}`
          : undefined
      }
    >
      <legend>{label}</legend>
      {!compact && (
        <p>
          Пакет: {String(packageSource.kind ?? "Не объявлен")} ·{" "}
          {Object.keys(source).length ? "Явное переопределение" : "Наследуется"}
        </p>
      )}
      <label>
        <span className={compact ? "application-credential-label" : undefined}>
          Источник
        </span>
        <select
          disabled={disabled}
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            setValues(
              e.target.value === "runtime_secret_ref" &&
                runtimeInput !== undefined
                ? {
                    ref:
                      initial.kind === "runtime_secret_ref" && initial.ref
                        ? initial.ref
                        : `application-${crypto.randomUUID()}`,
                  }
                : {},
            );
            change();
          }}
        >
          <option value="runtime_secret_ref">Сессионный секрет</option>
          <option value="generated">Генерируемый</option>
          <option value="vault_ref">Существующий Vault secret</option>
          <option value="pki_credential">PKI credential</option>
          {allowLiteral && <option value="literal">Имя пользователя</option>}
        </select>
      </label>
      {kind === "runtime_secret_ref" && runtimeInput !== undefined ? (
        dirty ? (
          <small>
            Сохраните источник в черновик и проект перед вводом секрета.
          </small>
        ) : (
          runtimeInput
        )
      ) : (
        keys.map((key) => (
          <label key={key}>
            <span
              className={compact ? "application-credential-label" : undefined}
            >
              {labels[key]}
            </span>
            <input
              placeholder={compact ? labels[key] : undefined}
              disabled={disabled}
              value={
                key === "value" && showResolvedLiteral
                  ? resolvedLiteralValue
                  : String(values[key] ?? "")
              }
              title={
                key === "value" && resolvedLiteralValue !== undefined
                  ? `Вычислено Core: ${resolvedLiteralValue}. Для редактирования исходного значения нажмите на поле.`
                  : undefined
              }
              autoComplete="off"
              onFocus={() => {
                if (key === "value") setValueFocused(true);
              }}
              onBlur={() => {
                if (key === "value") setValueFocused(false);
              }}
              onChange={(e) => {
                setValues((v) => ({ ...v, [key]: e.target.value }));
                change();
              }}
            />
          </label>
        ))
      )}
      <div
        className={
          compact
            ? "application-credential-actions"
            : "application-credential-actions-default"
        }
      >
        {(kind !== "runtime_secret_ref" ||
          runtimeInput === undefined ||
          dirty) && (
          <button
            aria-label="В черновик"
            title="В черновик"
            disabled={
              disabled ||
              !dirty ||
              keys.some((k) => !String(values[k] ?? "").trim())
            }
            onClick={() =>
              void onSave({
                kind,
                ...Object.fromEntries(keys.map((k) => [k, values[k]])),
              }).then(finish)
            }
          >
            {compact ? "✓" : "В черновик"}
          </button>
        )}
        <button
          aria-label="Сбросить к default"
          title="Сбросить к default"
          className="outline"
          disabled={disabled || !Object.keys(source).length}
          onClick={() => void onReset().then(finish)}
        >
          {compact ? "↺" : "Сбросить к default"}
        </button>
      </div>
    </fieldset>
  );
}

export function ApplicationCredentials({
  defaults,
  authored,
  connections,
  disabled,
  onSave,
  onDirtyChange,
  bindings,
  resources = {},
  resolvedResources = {},
  deploymentTypes = {},
  variableBindings = {},
  renderVariables,
  secretSession,
  resolvedAccounts = {},
  sharedSecretRefs = [],
}: {
  defaults: Obj;
  authored: Obj;
  connections: Obj;
  disabled: boolean;
  onSave: (accounts: Obj) => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
  bindings: Obj;
  resources?: Obj;
  resolvedResources?: Obj;
  deploymentTypes?: Record<string, string>;
  variableBindings?: Obj;
  renderVariables?: (account: string, field: string) => ReactNode;
  secretSession?: ApplicationSecretSession;
  resolvedAccounts?: Obj;
  sharedSecretRefs?: string[];
}) {
  const dirtyFields = useRef(new Set<string>());
  const mark = (key: string, dirty: boolean) => {
    if (dirty) dirtyFields.current.add(key);
    else dirtyFields.current.delete(key);
    onDirtyChange(dirtyFields.current.size > 0);
  };
  const accounts = objectValue(authored.accounts);
  const names = Object.keys({
    ...connections,
    ...objectValue(defaults.accounts),
    ...accounts,
    ...objectValue(authored.accounts),
  });
  return (
    <>
      {names.length === 0 && (
        <p>Пакет не объявляет подключений или credentials.</p>
      )}
      {names
        .filter(
          (name) =>
            Object.keys(
              objectValue(
                objectValue(objectValue(defaults.accounts)[name]).credentials,
              ),
            ).length > 0 ||
            Object.keys(objectValue(objectValue(accounts[name]).credentials))
              .length > 0,
        )
        .map((name) => {
          const account = objectValue(accounts[name]);
          const packageAccount = objectValue(
            objectValue(defaults.accounts)[name],
          );
          const credentials = objectValue(account.credentials);
          const base = objectValue(packageAccount.credentials);
          const binding = String(
            objectValue(connections[name]).library_binding ?? name,
          );
          const deployment = String(
            objectValue(bindings[binding]).deploymentRef ?? "",
          );
          const serviceType = deploymentTypes[deployment] ?? "";
          const save = (value: Obj) => {
            const next = { ...accounts };
            if (Object.keys(value).length) next[name] = value;
            else delete next[name];
            return onSave(next);
          };
          return (
            <section className="application-account-card" key={name}>
              <h3 title={`Подключение: ${binding}`}>
                {deployment || name} <small>{serviceType}</small>
                {secretSession && (
                  <ApplicationSecretAvailabilityBadge
                    session={secretSession}
                    resolved={
                      Object.keys(objectValue(resolvedAccounts[name])).length >
                      0
                    }
                    sourceRefs={Object.values(
                      objectValue(
                        objectValue(resolvedAccounts[name]).credentials,
                      ),
                    )
                      .map((credential) =>
                        objectValue(objectValue(credential).source),
                      )
                      .filter((source) => source.kind === "runtime_secret_ref")
                      .map((source) => String(source.ref ?? ""))}
                  />
                )}
                {secretSession &&
                  (secretSession.disabled ||
                    !Object.keys(objectValue(resolvedAccounts[name]))
                      .length) && (
                    <small className="application-secret-prerequisite">
                      Сохраните проект и получите актуальную проверку Core перед
                      вводом секрета.
                    </small>
                  )}
              </h3>
              <details className="application-account-settings">
                <summary>Настройки</summary>
                <div className="application-account-settings-content">
                  {Object.keys(packageAccount).length > 0 && (
                    <label>
                      Управление учётной записью
                      <select
                        aria-label="Управление учётной записью"
                        disabled={disabled}
                        value={String(account.mode ?? "")}
                        onChange={(event) => {
                          const next = { ...account };
                          if (event.target.value) {
                            next.mode = event.target.value;
                            next.credentials = credentials;
                          } else delete next.mode;
                          void save(next);
                        }}
                      >
                        <option value="">Из пакета</option>
                        <option value="managed">Создавать и настраивать</option>
                        <option value="existing">
                          Использовать существующую
                        </option>
                      </select>
                    </label>
                  )}
                  {Object.keys(packageAccount).length > 0 && (
                    <details className="application-legacy-grants">
                      <summary>Расширенные настройки аккаунта</summary>
                      <ApplicationValueFields
                        label="Режим и grants"
                        value={Object.fromEntries(
                          Object.entries(account).filter(([key]) =>
                            [
                              "databaseRef",
                              "grants",
                              "databaseAccess",
                            ].includes(key),
                          ),
                        )}
                        defaults={Object.fromEntries(
                          Object.entries(packageAccount).filter(([key]) =>
                            [
                              "databaseRef",
                              "grants",
                              "databaseAccess",
                            ].includes(key),
                          ),
                        )}
                        excludeKeys={["credentials"]}
                        disabled={disabled || !account.mode}
                        onDirtyChange={(dirty) => mark(name + "options", dirty)}
                        onSave={(metadata) =>
                          save({
                            ...Object.fromEntries(
                              Object.entries(account).filter(
                                ([key]) =>
                                  ![
                                    "databaseRef",
                                    "grants",
                                    "databaseAccess",
                                  ].includes(key),
                              ),
                            ),
                            ...metadata,
                          })
                        }
                      />
                    </details>
                  )}
                </div>
              </details>
              {Object.keys({
                ...base,
                ...credentials,
                ...(objectValue(objectValue(authored.accounts)[name])
                  .credentials as Obj),
              }).length === 0 ? (
                <p>
                  Пакет не объявляет отдельные username/password для этого
                  подключения. TLS и Vault identity задаются через PKI/Vault
                  bindings библиотеки.
                </p>
              ) : (
                <div className="application-credential-scroll">
                  <table className="application-credential-table">
                    <thead>
                      <tr>
                        <th>Поле</th>
                        <th>Переменные приложения</th>
                        <th>Источник и значение / ссылка</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(["username", "password"] as const)
                        .filter(
                          (field) =>
                            Object.hasOwn(base, field) ||
                            Object.hasOwn(credentials, field),
                        )
                        .map((field) => {
                          const source = objectValue(
                            objectValue(credentials[field]).source,
                          );
                          const resolvedSource = objectValue(
                            objectValue(
                              objectValue(
                                objectValue(resolvedAccounts[name]).credentials,
                              )[field],
                            ).source,
                          );
                          return (
                            <tr key={name + field + JSON.stringify(source)}>
                              <th>{field}</th>
                              <td>
                                {renderVariables
                                  ? renderVariables(name, field)
                                  : Object.entries(variableBindings)
                                      .filter(([, value]) => {
                                        const binding = objectValue(
                                          objectValue(value).source,
                                        );
                                        return (
                                          binding.account === name &&
                                          binding.field === field
                                        );
                                      })
                                      .map(([variable]) => (
                                        <code key={variable}>{variable} </code>
                                      ))}
                              </td>
                              <td>
                                <CredentialSourceEditor
                                  resolvedLiteralValue={
                                    field === "username" &&
                                    resolvedSource.kind === "literal" &&
                                    typeof resolvedSource.value === "string"
                                      ? resolvedSource.value
                                      : undefined
                                  }
                                  runtimeInput={
                                    secretSession ? (
                                      <ApplicationRuntimeSecretField
                                        session={secretSession}
                                        label={`${name}: ${field === "password" ? "Пароль" : "Секрет имени пользователя"}`}
                                        sourceRef={String(
                                          objectValue(
                                            objectValue(
                                              objectValue(
                                                objectValue(
                                                  resolvedAccounts[name],
                                                ).credentials,
                                              )[field],
                                            ).source,
                                          ).ref ?? "",
                                        )}
                                        shared={sharedSecretRefs.includes(
                                          String(
                                            objectValue(
                                              objectValue(
                                                objectValue(
                                                  objectValue(
                                                    resolvedAccounts[name],
                                                  ).credentials,
                                                )[field],
                                              ).source,
                                            ).ref ?? "",
                                          ),
                                        )}
                                      />
                                    ) : undefined
                                  }
                                  compact
                                  label={
                                    field === "username"
                                      ? "Имя пользователя"
                                      : "Пароль"
                                  }
                                  source={source}
                                  packageSource={objectValue(
                                    objectValue(base[field]).source,
                                  )}
                                  allowLiteral={field === "username"}
                                  disabled={disabled || !account.mode}
                                  onDirtyChange={(dirty) =>
                                    mark(name + field, dirty)
                                  }
                                  onSave={(source) =>
                                    save({
                                      ...account,
                                      credentials: {
                                        ...credentials,
                                        [field]: { source },
                                      },
                                    })
                                  }
                                  onReset={() => {
                                    const nextCredentials = { ...credentials };
                                    delete nextCredentials[field];
                                    const nextAccount = { ...account };
                                    if (Object.keys(nextCredentials).length)
                                      nextAccount.credentials = nextCredentials;
                                    else delete nextAccount.credentials;
                                    return save(nextAccount);
                                  }}
                                />
                              </td>
                            </tr>
                          );
                        })}
                    </tbody>
                  </table>
                </div>
              )}
              {serviceType === "kafka" && (
                <ApplicationKafkaAccess
                  key={name + JSON.stringify(account.grants)}
                  account={account}
                  inherited={packageAccount}
                  resolved={objectValue(resolvedAccounts[name])}
                  resolvedResources={resolvedResources}
                  disabled={disabled || !account.mode}
                  onDirtyChange={(dirty) => mark(name + "acl", dirty)}
                  onSave={(grants) => {
                    const next = { ...account };
                    if (grants === undefined) delete next.grants;
                    else next.grants = grants;
                    return save(next);
                  }}
                />
              )}
              <ApplicationAccountAccess
                key={
                  name +
                  JSON.stringify([account.databaseAccess, account.grants])
                }
                serviceType={serviceType}
                deployment={deployment}
                resources={resources}
                resolvedResources={resolvedResources}
                bindings={bindings}
                account={account}
                inherited={packageAccount}
                disabled={disabled || !account.mode}
                onDirtyChange={(dirty) => mark(name + "access", dirty)}
                onSave={(metadata) => {
                  const next = { ...account };
                  for (const key of ["databaseRef", "grants", "databaseAccess"])
                    delete next[key];
                  return save({ ...next, ...metadata });
                }}
              />
              {serviceType === "redis" && (
                <ApplicationRedisAccess
                  key={name + JSON.stringify(account.grants)}
                  value={objectValue(account.grants ?? packageAccount.grants)}
                  sentinel={
                    objectValue(bindings[binding]).connectionRef === "sentinel"
                  }
                  disabled={disabled || !account.mode}
                  onDirtyChange={(dirty) => mark(name + "acl", dirty)}
                  onSave={(grants) => save({ ...account, grants })}
                />
              )}
            </section>
          );
        })}
    </>
  );
}
