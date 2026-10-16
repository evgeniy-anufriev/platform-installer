import { useRef, useState } from "react";
import { objectValue } from "./application-draft";
import { ApplicationValueFields } from "./ApplicationValueFields";

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
}: {
  label: string;
  source: Obj;
  packageSource: Obj;
  allowLiteral: boolean;
  disabled: boolean;
  onSave: (source: Obj) => Promise<boolean>;
  onReset: () => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const initial = Object.keys(source).length ? source : packageSource;
  const [kind, setKind] = useState(
    String(initial.kind ?? "runtime_secret_ref"),
  );
  const [values, setValues] = useState<Obj>({ ...initial });
  const [dirty, setDirty] = useState(false);
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
    <fieldset>
      <legend>{label}</legend>
      <p>
        Пакет: {String(packageSource.kind ?? "Не объявлен")} ·{" "}
        {Object.keys(source).length ? "Явное переопределение" : "Наследуется"}
      </p>
      <label>
        Источник
        <select
          disabled={disabled}
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            setValues({});
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
      {keys.map((key) => (
        <label key={key}>
          {labels[key]}
          <input
            disabled={disabled}
            value={String(values[key] ?? "")}
            autoComplete="off"
            onChange={(e) => {
              setValues((v) => ({ ...v, [key]: e.target.value }));
              change();
            }}
          />
        </label>
      ))}
      <button
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
        В черновик
      </button>
      <button
        className="outline"
        disabled={disabled || !Object.keys(source).length}
        onClick={() => void onReset().then(finish)}
      >
        Сбросить к default
      </button>
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
  onProviderSecrets,
}: {
  defaults: Obj;
  authored: Obj;
  connections: Obj;
  disabled: boolean;
  onSave: (accounts: Obj) => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
  bindings: Obj;
  onProviderSecrets?: (deploymentId: string) => void;
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
      {names.map((name) => {
        const account = objectValue(accounts[name]);
        const packageAccount = objectValue(
          objectValue(defaults.accounts)[name],
        );
        const credentials = objectValue(account.credentials);
        const base = objectValue(packageAccount.credentials);
        const save = (value: Obj) => {
          const next = { ...accounts };
          if (Object.keys(value).length) next[name] = value;
          else delete next[name];
          return onSave(next);
        };
        return (
          <section key={name}>
            <h3>{name}</h3>
            <p>
              Подключение:{" "}
              {String(objectValue(connections[name]).library_binding ?? name)}
            </p>
            {Object.keys(packageAccount).length > 0 && (
              <label>
                Режим аккаунта · явное переопределение
                <select
                  disabled={disabled}
                  value={String(account.mode ?? "")}
                  onChange={(event) =>
                    void save(
                      event.target.value
                        ? { ...account, mode: event.target.value, credentials }
                        : {},
                    )
                  }
                >
                  <option value="">Пакет · сброс аккаунта к defaults</option>
                  <option value="managed">managed</option>
                  <option value="existing">existing</option>
                </select>
              </label>
            )}
            {typeof objectValue(
              bindings[
                String(objectValue(connections[name]).library_binding ?? name)
              ],
            ).deploymentRef === "string" &&
              onProviderSecrets && (
                <button
                  className="outline"
                  disabled={disabled}
                  onClick={() =>
                    onProviderSecrets(
                      String(
                        objectValue(
                          bindings[
                            String(
                              objectValue(connections[name]).library_binding ??
                                name,
                            )
                          ],
                        ).deploymentRef,
                      ),
                    )
                  }
                >
                  Административные секреты сервиса
                </button>
              )}
            {Object.keys(packageAccount).length > 0 && (
              <ApplicationValueFields
                label="Режим и grants"
                value={Object.fromEntries(
                  Object.entries(account).filter(([key]) =>
                    ["databaseRef", "grants"].includes(key),
                  ),
                )}
                defaults={Object.fromEntries(
                  Object.entries(packageAccount).filter(([key]) =>
                    ["databaseRef", "grants"].includes(key),
                  ),
                )}
                excludeKeys={["credentials"]}
                disabled={disabled || !account.mode}
                onDirtyChange={(dirty) => mark(name + "options", dirty)}
                onSave={(metadata) =>
                  save({
                    ...Object.fromEntries(
                      Object.entries(account).filter(
                        ([key]) => !["databaseRef", "grants"].includes(key),
                      ),
                    ),
                    ...metadata,
                  })
                }
              />
            )}
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
              (["username", "password"] as const)
                .filter(
                  (field) =>
                    Object.hasOwn(base, field) ||
                    Object.hasOwn(credentials, field),
                )
                .map((field) => {
                  const source = objectValue(
                    objectValue(credentials[field]).source,
                  );
                  return (
                    <CredentialSourceEditor
                      key={name + field + JSON.stringify(source)}
                      label={
                        field === "username" ? "Имя пользователя" : "Пароль"
                      }
                      source={source}
                      packageSource={objectValue(
                        objectValue(base[field]).source,
                      )}
                      allowLiteral={field === "username"}
                      disabled={disabled || !account.mode}
                      onDirtyChange={(dirty) => mark(name + field, dirty)}
                      onSave={(source) =>
                        save({
                          ...account,
                          credentials: { ...credentials, [field]: { source } },
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
                  );
                })
            )}
          </section>
        );
      })}
    </>
  );
}
