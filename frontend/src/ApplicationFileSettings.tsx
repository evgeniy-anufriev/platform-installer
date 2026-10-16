import { useState } from "react";
import { objectValue } from "./application-draft";

export function ApplicationFileSettings({
  authored,
  defaults,
  disabled,
  onSave,
  onReset,
  onDirtyChange,
}: {
  authored: unknown;
  defaults: unknown;
  disabled: boolean;
  onSave: (files: Record<string, unknown>[]) => Promise<boolean>;
  onReset: () => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const initial = Array.isArray(authored)
    ? authored
    : Array.isArray(defaults)
      ? defaults
      : [];
  const [files, setFiles] = useState<Record<string, unknown>[]>(
    initial.map((row) => ({ ...objectValue(row) })),
  );
  const [dirty, setDirty] = useState(false);
  const change = (index: number, key: string, value: string) => {
    setFiles((rows) =>
      rows.map((row, i) => {
        if (i !== index) return row;
        const next = { ...row };
        if (key === "source" || key === "template") {
          delete next.source;
          delete next.template;
        }
        next[key] = value;
        return next;
      }),
    );
    setDirty(true);
    onDirtyChange(true);
  };
  return (
    <section>
      <h3>Файлы конфигурации</h3>
      <p>
        {Array.isArray(authored)
          ? "Явный список экземпляра"
          : "Список из пакета"}
        . Изменение заменяет весь список. Пути source/template относятся к
        пакету; доступность проверяет Core.
      </p>
      {files.map((file, i) => (
        <fieldset key={i}>
          <legend>Файл {i + 1}</legend>
          <label>
            Источник
            <select
              value={Object.hasOwn(file, "template") ? "template" : "source"}
              disabled={disabled}
              onChange={(e) =>
                change(
                  i,
                  e.target.value,
                  String(file.source ?? file.template ?? ""),
                )
              }
            >
              <option value="source">Файл пакета</option>
              <option value="template">Шаблон пакета</option>
            </select>
          </label>
          <label>
            Путь в пакете
            <input
              value={String(file.source ?? file.template ?? "")}
              disabled={disabled}
              onChange={(e) =>
                change(
                  i,
                  Object.hasOwn(file, "template") ? "template" : "source",
                  e.target.value,
                )
              }
            />
          </label>
          <label>
            Назначение
            <input
              value={String(file.destination ?? "")}
              disabled={disabled}
              onChange={(e) => change(i, "destination", e.target.value)}
            />
          </label>
          <label>
            Mode
            <input
              value={String(file.mode ?? "")}
              disabled={disabled}
              onChange={(e) => change(i, "mode", e.target.value)}
            />
          </label>
          <button
            className="outline"
            disabled={disabled}
            onClick={() => {
              setFiles((rows) => rows.filter((_, n) => n !== i));
              setDirty(true);
              onDirtyChange(true);
            }}
          >
            Убрать файл
          </button>
        </fieldset>
      ))}
      <button
        className="outline"
        disabled={disabled}
        onClick={() => {
          setFiles((rows) => [
            ...rows,
            { source: "", destination: "", mode: "0600" },
          ]);
          setDirty(true);
          onDirtyChange(true);
        }}
      >
        Добавить файл
      </button>
      <button
        disabled={disabled || !dirty}
        onClick={() =>
          void onSave(files).then((ok) => {
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
        disabled={disabled || !Array.isArray(authored)}
        onClick={() =>
          void onReset().then((ok) => {
            if (ok) onDirtyChange(false);
          })
        }
      >
        Сбросить список к default
      </button>
    </section>
  );
}
