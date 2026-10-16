import { useRef, useState } from "react";
import { objectValue } from "./application-draft";

type Obj = Record<string, unknown>;
// Small authored key/value control for concrete parameter/environment sections.
// It edits JSON-shaped data; it never evaluates schema rules or Ansible values.
export function ApplicationValueFields({
  label,
  value,
  defaults,
  disabled,
  onSave,
  onDirtyChange,
  excludeKeys = [],
}: {
  label: string;
  value: Obj;
  defaults: Obj;
  disabled: boolean;
  onSave: (value: Obj) => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
  excludeKeys?: string[];
}) {
  const dirtyFields = useRef(new Set<string>());
  const mark = (key: string, dirty: boolean) => {
    if (dirty) dirtyFields.current.add(key);
    else dirtyFields.current.delete(key);
    onDirtyChange(dirtyFields.current.size > 0);
  };
  const [name, setName] = useState("");
  const [adding, setAdding] = useState(false);
  const keys = Object.keys({ ...defaults, ...value });
  return (
    <section>
      <h3>{label}</h3>
      {keys.map((key) => {
        const inherited = defaults[key],
          authored = value[key];
        const current = authored ?? inherited;
        const reset = () => {
          const next = { ...value };
          delete next[key];
          return onSave(next);
        };
        if (current && typeof current === "object" && !Array.isArray(current))
          return (
            <fieldset key={key}>
              <legend>{key}</legend>
              <ApplicationValueFields
                label={key}
                value={objectValue(authored)}
                defaults={objectValue(inherited)}
                disabled={disabled}
                onSave={(next) => onSave({ ...value, [key]: next })}
                onDirtyChange={(dirty) => mark(key, dirty)}
              />
              <button
                className="outline"
                disabled={disabled || !Object.hasOwn(value, key)}
                onClick={() => void reset()}
              >
                Сбросить {key}
              </button>
            </fieldset>
          );
        if (Array.isArray(current))
          return (
            <div key={key}>
              <strong>{key}</strong>
              <ApplicationArrayFields
                label={key}
                value={current}
                disabled={disabled}
                onDirtyChange={(dirty) => mark(key, dirty)}
                onSave={(rows) => onSave({ ...value, [key]: rows })}
              />
              <button
                className="outline"
                disabled={disabled || !Object.hasOwn(value, key)}
                onClick={() => void reset()}
              >
                Сбросить {key}
              </button>
            </div>
          );
        return (
          <ScalarValue
            key={key + JSON.stringify(current)}
            label={key}
            value={current}
            inferType={inherited === undefined && current === ""}
            explicit={Object.hasOwn(value, key)}
            disabled={disabled}
            onDirtyChange={(dirty) => mark(key, dirty)}
            onSave={(next) => onSave({ ...value, [key]: next })}
            onReset={reset}
          />
        );
      })}
      {!adding ? (
        <button
          className="outline"
          disabled={disabled}
          onClick={() => setAdding(true)}
        >
          Добавить параметр · {label}
        </button>
      ) : (
        <form
          className="application-add-parameter"
          onSubmit={(e) => {
            e.preventDefault();
            if (!name || keys.includes(name) || excludeKeys.includes(name))
              return;
            void onSave({ ...value, [name]: "" }).then((ok) => {
              if (ok) {
                setName("");
                setAdding(false);
                mark("__add", false);
              }
            });
          }}
        >
          <label>
            Имя параметра
            <input
              value={name}
              disabled={disabled}
              autoFocus
              onChange={(e) => {
                setName(e.target.value);
                mark("__add", true);
              }}
            />
          </label>
          <button
            disabled={
              disabled ||
              !name ||
              keys.includes(name) ||
              excludeKeys.includes(name)
            }
          >
            Добавить
          </button>
          <button
            type="button"
            className="outline"
            disabled={disabled}
            onClick={() => {
              setName("");
              setAdding(false);
              mark("__add", false);
            }}
          >
            Отмена
          </button>
          <small>Значение задаётся в строке параметра после добавления.</small>
        </form>
      )}
    </section>
  );
}

export function ApplicationArrayFields({
  label,
  value,
  disabled,
  onSave,
  onDirtyChange,
}: {
  label: string;
  value: unknown[];
  disabled: boolean;
  onSave: (value: unknown[]) => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const dirtyRows = useRef(new Set<number>());
  const mark = (index: number, dirty: boolean) => {
    if (dirty) dirtyRows.current.add(index);
    else dirtyRows.current.delete(index);
    onDirtyChange(dirtyRows.current.size > 0);
  };
  return (
    <section>
      <p>Изменение заменяет список {label} целиком.</p>
      {value.map((row, index) => (
        <fieldset key={index}>
          <legend>
            {label} · {index + 1}
          </legend>
          {row && typeof row === "object" && !Array.isArray(row) ? (
            <ApplicationValueFields
              label={label}
              value={objectValue(row)}
              defaults={{}}
              disabled={disabled}
              onDirtyChange={(dirty) => mark(index, dirty)}
              onSave={(next) =>
                onSave(value.map((v, i) => (i === index ? next : v)))
              }
            />
          ) : Array.isArray(row) ? (
            <ApplicationArrayFields
              label={label}
              value={row}
              disabled={disabled}
              onDirtyChange={(dirty) => mark(index, dirty)}
              onSave={(next) =>
                onSave(value.map((v, i) => (i === index ? next : v)))
              }
            />
          ) : (
            <ScalarValue
              label={label}
              value={row}
              explicit={true}
              disabled={disabled}
              onDirtyChange={(dirty) => mark(index, dirty)}
              onSave={(next) =>
                onSave(value.map((v, i) => (i === index ? next : v)))
              }
              onReset={() => onSave(value.filter((_, i) => i !== index))}
            />
          )}
          <button
            className="outline"
            disabled={disabled}
            onClick={() => void onSave(value.filter((_, i) => i !== index))}
          >
            Убрать элемент
          </button>
        </fieldset>
      ))}
      <button
        className="outline"
        disabled={disabled}
        onClick={() => void onSave([...value, ""])}
      >
        Добавить строку
      </button>
      <button
        className="outline"
        disabled={disabled}
        onClick={() => void onSave([...value, {}])}
      >
        Добавить объект
      </button>
    </section>
  );
}
function ScalarValue({
  label,
  value,
  explicit,
  disabled,
  onSave,
  onReset,
  onDirtyChange,
  inferType = false,
}: {
  label: string;
  value: unknown;
  explicit: boolean;
  disabled: boolean;
  onSave: (value: unknown) => Promise<boolean>;
  onReset: () => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
  inferType?: boolean;
}) {
  const [text, setText] = useState(String(value ?? ""));
  const [dirty, setDirty] = useState(false);
  const [manualType, setManualType] = useState("auto");
  const inferred = inferParameterValue(text);
  const originalType = typeof value;
  const type =
    manualType !== "auto"
      ? manualType
      : inferType
        ? typeof inferred
        : originalType;
  const parsed =
    type === "number"
      ? Number(text)
      : type === "boolean"
        ? text === "true"
        : text;
  const valid =
    type === "number"
      ? text.trim() !== "" && Number.isFinite(Number(text))
      : type === "boolean"
        ? ["true", "false"].includes(text)
        : true;
  const typeLabel =
    type === "number" ? "Число" : type === "boolean" ? "Логическое" : "Строка";
  return (
    <div className="application-field">
      <label>
        {label}
        <input
          value={text}
          disabled={disabled}
          onChange={(e) => {
            setText(e.target.value);
            setDirty(true);
            onDirtyChange(true);
          }}
        />
      </label>
      <small>
        Тип: {typeLabel}
        {manualType === "auto" ? " · автоматически" : " · задан вручную"}
      </small>
      <details className="application-parameter-type">
        <summary>Дополнительно</summary>
        <label>
          Тип · {label}
          <select
            value={manualType}
            disabled={disabled}
            onChange={(e) => {
              setManualType(e.target.value);
              setDirty(true);
              onDirtyChange(true);
            }}
          >
            <option value="auto">Автоматически</option>
            <option value="string">Строка</option>
            <option value="number">Число</option>
            <option value="boolean">Логическое</option>
          </select>
        </label>
        <div className="row">
          {[
            { title: "Создать объект", value: {} },
            { title: "Создать список", value: [] },
          ].map((choice) => (
            <button
              key={choice.title}
              className="outline"
              disabled={disabled}
              onClick={() => {
                if (
                  text &&
                  !window.confirm("Заменить текущее значение структурой?")
                )
                  return;
                void onSave(choice.value).then((ok) => {
                  if (ok) onDirtyChange(false);
                });
              }}
            >
              {choice.title}
            </button>
          ))}
        </div>
      </details>
      {!valid && (
        <small role="alert">Значение не соответствует типу {typeLabel}.</small>
      )}
      <small>
        {explicit ? "Явное значение" : "Из пакета · без вычисления Ansible"}
      </small>
      <div className="row">
        <button
          disabled={disabled || !dirty || !valid}
          onClick={() =>
            void onSave(parsed).then((ok) => {
              if (ok) {
                setDirty(false);
                onDirtyChange(false);
              }
            })
          }
        >
          В черновик
        </button>
        <button
          className="outline"
          disabled={disabled || !explicit}
          onClick={() =>
            void onReset().then((ok) => {
              if (ok) onDirtyChange(false);
            })
          }
        >
          Сбросить к default
        </button>
      </div>
    </div>
  );
}

// UI input conversion only; package validation and Ansible resolution stay in Core.
export function inferParameterValue(text: string): string | number | boolean {
  if (text === "true" || text === "false") return text === "true";
  if (
    /^-?(?:0|[1-9]\d*)(?:\.\d+)?$/.test(text) &&
    Number.isFinite(Number(text)) &&
    Math.abs(Number(text)) <= Number.MAX_SAFE_INTEGER
  )
    return Number(text);
  return text;
}
