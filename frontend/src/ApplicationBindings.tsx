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
}: {
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
  const names = [
    ...new Set([...Object.keys(hints), ...Object.keys(value), ...added]),
  ];
  const mark = (key: string, dirty: boolean) => {
    if (dirty) dirtyRows.current.add(key);
    else dirtyRows.current.delete(key);
    onDirtyChange(dirtyRows.current.size > 0 || !!name);
  };
  return (
    <section>
      <h3>Подключения библиотеки</h3>
      <p>
        Кандидаты — существующие deployment и TLS-профили. Совместимость
        разрешает Core.
      </p>
      {names.map((key) => (
        <BindingRow
          key={key + JSON.stringify(value[key])}
          name={key}
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
      <label>
        Добавить binding
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
        disabled={disabled || !name || names.includes(name)}
        onClick={() => {
          setAdded((rows) => [...rows, name]);
          setName("");
          onDirtyChange(dirtyRows.current.size > 0);
        }}
      >
        Добавить строку
      </button>
    </section>
  );
}
function BindingRow({
  name,
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
    <fieldset>
      <legend>{name}</legend>
      <label>
        Тип подключения
        <select
          disabled={disabled}
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            setRef("");
            setDirty(true);
            onDirtyChange(true);
          }}
        >
          <option value="deploymentRef">Инфраструктурный deployment</option>
          <option value="profileRef">TLS-профиль</option>
        </select>
      </label>
      <label>
        Подключение {name}
        <select
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
      </label>
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
        Убрать binding
      </button>
    </fieldset>
  );
}
