import { useState, useRef } from "react";
import { objectValue } from "./application-draft";

type Obj = Record<string, unknown>;
export function ApplicationBindings({
  value,
  hints,
  deployments,
  profiles,
  disabled,
  onSave,
  onDirtyChange,
  vaultBinding,
  deploymentTypes = {},
  onSelectVault,
}: {
  vaultBinding?: string;
  deploymentTypes?: Record<string, string>;
  onSelectVault?: (binding: string) => Promise<boolean>;
  value: Obj;
  hints: Record<string, string>;
  deployments: string[];
  profiles: string[];
  disabled: boolean;
  onSave: (value: Obj) => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const dirtyRows = useRef(new Set<string>());
  const [name, setName] = useState("");
  const [added, setAdded] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const names = [
    ...new Set([...Object.keys(hints), ...Object.keys(value), ...added]),
  ];
  const mark = (key: string, dirty: boolean) => {
    if (dirty) dirtyRows.current.add(key);
    else dirtyRows.current.delete(key);
    onDirtyChange(dirtyRows.current.size > 0 || !!name);
  };
  return (
    <section className="application-bindings-table">
      <h3>Подключения библиотеки</h3>
      <p>Выберите сервис или TLS-профиль. Совместимость проверяет Core.</p>
      <div
        className="application-connections-scroll"
        role="region"
        aria-label="Список подключений"
        tabIndex={0}
      >
        <table>
          <thead>
            <tr>
              <th>Подключение</th>
              <th>Тип</th>
              <th>Deployment / профиль</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {names.map((key) => (
              <BindingRow
                key={key + JSON.stringify(value[key])}
                name={key}
                isVault={
                  deploymentTypes[
                    String(objectValue(value[key]).deploymentRef)
                  ] === "vault"
                }
                selectedVault={vaultBinding === key}
                onSelectVault={
                  onSelectVault ? () => onSelectVault(key) : undefined
                }
                value={objectValue(value[key])}
                hint={hints[key]}
                deployments={deployments}
                profiles={profiles}
                disabled={disabled}
                onDirtyChange={(dirty) => mark(key, dirty)}
                onSave={(entry) => onSave({ ...value, [key]: entry })}
                onRemove={() => {
                  const next = { ...value };
                  delete next[key];
                  return onSave(next);
                }}
              />
            ))}
          </tbody>
        </table>
      </div>
      {!adding ? (
        <button
          className="outline"
          disabled={disabled || dirtyRows.current.size > 0}
          onClick={() => setAdding(true)}
        >
          Добавить подключение
        </button>
      ) : (
        <div className="application-add-parameter">
          <label>
            Имя подключения
            <input
              value={name}
              disabled={disabled}
              onChange={(e) => {
                setName(e.target.value);
                onDirtyChange(!!e.target.value || dirtyRows.current.size > 0);
              }}
            />
          </label>
          <button
            className="outline"
            disabled={
              disabled ||
              !name ||
              names.includes(name) ||
              dirtyRows.current.size > 0
            }
            onClick={() => {
              setAdded((rows) => [...rows, name]);
              setName("");
              setAdding(false);
              onDirtyChange(dirtyRows.current.size > 0);
            }}
          >
            Добавить
          </button>
          <button
            className="outline"
            disabled={disabled}
            onClick={() => {
              setName("");
              setAdding(false);
              onDirtyChange(dirtyRows.current.size > 0);
            }}
          >
            Отмена
          </button>
        </div>
      )}
    </section>
  );
}
function BindingRow({
  name,
  isVault,
  selectedVault,
  onSelectVault,
  value,
  hint,
  deployments,
  profiles,
  disabled,
  onSave,
  onRemove,
  onDirtyChange,
}: {
  name: string;
  isVault: boolean;
  selectedVault: boolean;
  onSelectVault?: () => Promise<boolean>;
  value: Obj;
  hint?: string;
  deployments: string[];
  profiles: string[];
  disabled: boolean;
  onSave: (value: Obj) => Promise<boolean>;
  onRemove: () => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [kind, setKind] = useState(
    Object.hasOwn(value, "profileRef") || hint === "pki"
      ? "profileRef"
      : "deploymentRef",
  );
  const [ref, setRef] = useState(
    String(value.profileRef ?? value.deploymentRef ?? ""),
  );
  const [dirty, setDirty] = useState(false);
  const candidates = kind === "profileRef" ? profiles : deployments;
  return (
    <tr>
      <td>
        <strong>{name}</strong>{" "}
        {selectedVault && (
          <small className="application-vault-badge">Хранилище секретов</small>
        )}
      </td>
      <td>
        <select
          aria-label={"Тип подключения " + name}
          disabled={disabled}
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            setRef("");
            setDirty(true);
            onDirtyChange(true);
          }}
        >
          <option value="deploymentRef">Сервис</option>
          <option value="profileRef">TLS-профиль</option>
        </select>
      </td>
      <td>
        <select
          aria-label={"Подключение " + name}
          disabled={disabled}
          value={ref}
          onChange={(e) => {
            setRef(e.target.value);
            setDirty(true);
            onDirtyChange(true);
          }}
        >
          <option value="">Не выбрано</option>
          {ref && !candidates.includes(ref) && (
            <option value={ref}>{ref} · недоступно в текущем проекте</option>
          )}
          {candidates.map((id) => (
            <option key={id}>{id}</option>
          ))}
        </select>
      </td>
      <td>
        <div className="row">
          <button
            disabled={disabled || !dirty || !ref}
            onClick={() => {
              const next = { ...value };
              delete next.deploymentRef;
              delete next.profileRef;
              void onSave({ ...next, [kind]: ref }).then((ok) => {
                if (ok) {
                  setDirty(false);
                  onDirtyChange(false);
                }
              });
            }}
          >
            В черновик
          </button>
          <button
            className="outline"
            disabled={disabled || !Object.keys(value).length}
            onClick={() =>
              void onRemove().then((ok) => {
                if (ok) onDirtyChange(false);
              })
            }
          >
            Сбросить
          </button>
          {isVault && !selectedVault && onSelectVault && (
            <button
              className="outline"
              disabled={disabled || dirty}
              onClick={() => void onSelectVault()}
            >
              Для секретов
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}
