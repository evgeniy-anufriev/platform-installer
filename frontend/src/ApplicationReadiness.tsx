import { useState } from "react";
import type { ObjectValue } from "./application-draft";

export function ApplicationReadiness({
  value,
  defaults,
  disabled,
  onSave,
  onReset,
  onDirtyChange,
}: {
  value: ObjectValue;
  defaults: ObjectValue;
  disabled: boolean;
  onSave: (value: ObjectValue) => Promise<boolean>;
  onReset: () => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const current = (key: string) =>
    draft[key] ?? String(value[key] ?? defaults[key] ?? "");
  const authored = Object.keys(value).length > 0;
  const dirty = Object.keys(draft).length > 0;
  const valid =
    ["container", "healthcheck"].includes(current("mode")) &&
    [
      ["retries", 60],
      ["delay", 30],
    ].every(([key, max]) => {
      const text = current(String(key));
      return (
        text === "" ||
        (Number.isInteger(Number(text)) &&
          Number(text) >= 1 &&
          Number(text) <= Number(max))
      );
    });
  const change = (key: string, text: string) => {
    setDraft((previous) => ({ ...previous, [key]: text }));
    onDirtyChange(true);
  };
  const origin = (key: string) =>
    Object.hasOwn(draft, key)
      ? "Не сохранено"
      : Object.hasOwn(value, key)
        ? "Переопределено"
        : Object.hasOwn(defaults, key)
          ? "Из пакета"
          : "По умолчанию Core";
  return (
    <section className="application-section application-readiness">
      <div className="row">
        <h3>Проверка готовности</h3>
        <button
          type="button"
          className="application-link"
          disabled={disabled}
          onClick={() => setEditing(true)}
        >
          Изменить readiness
        </button>
        {authored && (
          <button
            className="application-link"
            disabled={disabled}
            onClick={async () => {
              if (await onReset()) {
                setDraft({});
                setEditing(false);
                onDirtyChange(false);
              }
            }}
          >
            Сбросить readiness к пакету
          </button>
        )}
      </div>
      <div className="application-readiness-fields">
        <label>
          Режим проверки
          <select
            aria-label="Режим проверки"
            value={current("mode")}
            disabled={disabled || !editing}
            onChange={(e) => change("mode", e.target.value)}
          >
            <option value="">По умолчанию Core</option>
            <option value="container">Контейнер запущен</option>
            <option value="healthcheck">Docker healthcheck</option>
          </select>
          <small>{origin("mode")}</small>
        </label>
        {(
          [
            ["retries", "Число попыток", 60],
            ["delay", "Интервал, сек.", 30],
          ] as const
        ).map(([key, label, max]) => (
          <label key={key}>
            {label}
            <input
              aria-label={label}
              type="number"
              min={1}
              max={max}
              step={1}
              placeholder="По умолчанию Core"
              value={current(key)}
              disabled={disabled || !editing}
              onChange={(e) => change(key, e.target.value)}
            />
            <small>{origin(key)}</small>
          </label>
        ))}
      </div>
      {current("mode") === "healthcheck" && (
        <p className="muted">
          Docker healthcheck должен быть объявлен в пакете. Успешность проверки
          определяется при выполнении плана.
        </p>
      )}
      {dirty && !valid && (
        <p role="alert">
          Выберите режим; попытки — от 1 до 60, интервал — от 1 до 30 секунд.
        </p>
      )}
      {dirty && (
        <div className="row">
          {dirty && (
            <button
              disabled={disabled || !valid}
              onClick={async () => {
                const next: ObjectValue = { ...value, mode: current("mode") };
                for (const key of ["retries", "delay"]) {
                  if (Object.hasOwn(draft, key)) {
                    if (draft[key] === "") delete next[key];
                    else next[key] = Number(draft[key]);
                  }
                }
                if (await onSave(next)) {
                  setDraft({});
                  setEditing(false);
                  onDirtyChange(false);
                }
              }}
            >
              В черновик
            </button>
          )}
        </div>
      )}
    </section>
  );
}
