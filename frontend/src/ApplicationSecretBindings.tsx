import { useRef, useState } from "react";
import { objectValue } from "./application-draft";

type Obj = Record<string, unknown>;
const sourceKey = (binding: unknown) => {
  const source = objectValue(objectValue(binding).source);
  return source.account &&
    ["username", "password"].includes(String(source.field))
    ? `${source.account}:${source.field}`
    : "";
};

// Edits ordinary authored secret_bindings; Core still resolves inheritance and validates sources.
export function ApplicationSecretBindings({
  value,
  defaults,
  accounts,
  disabled,
  onSave,
  onDirtyChange,
}: {
  value: Obj;
  defaults: Obj;
  accounts: Obj[];
  disabled: boolean;
  onSave: (value: Obj) => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const authored = objectValue(value.secret_bindings),
    base = objectValue(defaults.secret_bindings);
  const sources = [
    ...new Set(accounts.flatMap((list) => Object.keys(list))),
  ].flatMap((account) =>
    ["username", "password"]
      .filter((field) =>
        accounts.some((list) =>
          Object.hasOwn(
            objectValue(objectValue(list[account]).credentials),
            field,
          ),
        ),
      )
      .map((field) => ({ key: account + ":" + field, account, field })),
  );
  const dirty = useRef(new Set<string>());
  const mark = (key: string, active: boolean) => {
    if (active) dirty.current.add(key);
    else dirty.current.delete(key);
    onDirtyChange(dirty.current.size > 0);
  };
  const [name, setName] = useState(""),
    [source, setSource] = useState("");
  const save = (next: Obj) => {
    const provisioner = { ...value };
    if (Object.keys(next).length) {
      provisioner.secret_bindings = next;
      for (const key of ["type", "mode"])
        if (!Object.hasOwn(provisioner, key) && Object.hasOwn(defaults, key))
          provisioner[key] = defaults[key];
    } else delete provisioner.secret_bindings;
    return onSave(provisioner);
  };
  const setBinding = (variable: string, key: string) => {
    const item = sources.find((item) => item.key === key);
    return item
      ? save({
          ...authored,
          [variable]: { source: { account: item.account, field: item.field } },
        })
      : Promise.resolve(false);
  };
  const reset = (variable: string) => {
    const next = { ...authored };
    delete next[variable];
    return save(next);
  };
  const names = Object.keys({ ...base, ...authored });
  return (
    <section className="application-section application-secret-bindings">
      <h3>Переменные приложения из credentials</h3>
      <p>
        Поле username/password в Vault не меняется. Vault Agent передаёт его
        значение процессу приложения под выбранным именем переменной.
      </p>
      <p>
        Привязки пакета сохраняются. Новое имя добавляет переменную, а сброс
        убирает только переопределение экземпляра.
      </p>
      {names
        .filter((variable) => sourceKey(authored[variable] ?? base[variable]))
        .map((variable) => (
          <BindingRow
            key={
              variable + JSON.stringify([authored[variable], base[variable]])
            }
            variable={variable}
            current={sourceKey(authored[variable] ?? base[variable])}
            packageSource={sourceKey(base[variable])}
            explicit={Object.hasOwn(authored, variable)}
            disabled={disabled}
            sources={sources}
            onSave={(key) => setBinding(variable, key)}
            onReset={() => reset(variable)}
            onDirtyChange={(v) => mark(variable, v)}
          />
        ))}
      {names.some(
        (variable) => !sourceKey(authored[variable] ?? base[variable]),
      ) && (
        <p>
          Привязки общих секретов сохранены отдельно; эта форма меняет только
          username/password аккаунтов.
        </p>
      )}
      <fieldset>
        <legend>Добавить переменную</legend>
        <label>
          Имя переменной приложения
          <input
            value={name}
            disabled={disabled}
            onChange={(e) => {
              setName(e.target.value);
              mark("__new", true);
            }}
          />
        </label>
        <label>
          Поле credentials
          <select
            aria-label="Поле credentials"
            value={source}
            disabled={disabled}
            onChange={(e) => {
              setSource(e.target.value);
              mark("__new", true);
            }}
          >
            <option value="">Выберите аккаунт и поле</option>
            {sources.map((item) => (
              <option key={item.key} value={item.key}>
                {item.account} · {item.field}
              </option>
            ))}
          </select>
        </label>
        <button
          disabled={
            disabled ||
            !/^[A-Za-z_][A-Za-z0-9_]*$/.test(name) ||
            names.includes(name) ||
            !source
          }
          onClick={() =>
            void setBinding(name, source).then((ok) => {
              if (ok) {
                setName("");
                setSource("");
                mark("__new", false);
              }
            })
          }
        >
          В черновик
        </button>
        {name && names.includes(name) && (
          <p role="status">
            Переменная уже объявлена; измените её привязку выше.
          </p>
        )}
      </fieldset>
    </section>
  );
}
function BindingRow({
  variable,
  current,
  packageSource,
  explicit,
  disabled,
  sources,
  onSave,
  onReset,
  onDirtyChange,
}: {
  variable: string;
  current: string;
  packageSource: string;
  explicit: boolean;
  disabled: boolean;
  sources: { key: string; account: string; field: string }[];
  onSave: (key: string) => Promise<boolean>;
  onReset: () => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [editing, setEditing] = useState(explicit),
    [source, setSource] = useState(current),
    [dirty, setDirty] = useState(false);
  const finish = (ok: boolean) => {
    if (ok) {
      setDirty(false);
      onDirtyChange(false);
    }
  };
  return (
    <fieldset>
      <legend>{variable}</legend>
      <p>
        Пакет: {packageSource.replace(":", " · ") || "Не объявлена"} ·{" "}
        {explicit ? "Переопределено" : "Из пакета"}
      </p>
      <label>
        Источник {variable}
        <select
          aria-label={`Источник ${variable}`}
          value={source}
          disabled={disabled || !editing}
          onChange={(e) => {
            setSource(e.target.value);
            setDirty(true);
            onDirtyChange(true);
          }}
        >
          {!sources.some((item) => item.key === source) && (
            <option value={source}>{source.replace(":", " · ")}</option>
          )}
          {sources.map((item) => (
            <option key={item.key} value={item.key}>
              {item.account} · {item.field}
            </option>
          ))}
        </select>
      </label>
      <div className="row">
        <button
          className="outline"
          disabled={disabled || editing}
          onClick={() => setEditing(true)}
        >
          Переопределить {variable}
        </button>
        <button
          disabled={
            disabled || !dirty || !sources.some((item) => item.key === source)
          }
          onClick={() => void onSave(source).then(finish)}
        >
          В черновик
        </button>
        <button
          className="outline"
          disabled={disabled || !explicit}
          onClick={() => void onReset().then(finish)}
        >
          Сбросить {variable} к default
        </button>
      </div>
    </fieldset>
  );
}
