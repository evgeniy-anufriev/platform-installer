import { useState } from "react";

export function ApplicationPackageImport({
  disabled,
  choose,
  review,
  applicationRef,
}: {
  applicationRef?: string;
  disabled: boolean;
  choose?: () => Promise<string>;
  review: (
    source: string,
    kind: string,
    name: string,
    version: string,
    digest: string,
  ) => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState("");
  const [kind, setKind] = useState("application");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  return (
    <>
      <button
        className="outline"
        disabled={disabled || !choose}
        onClick={() => setOpen((v) => !v)}
      >
        {applicationRef ? "Импорт пакета приложения…" : "Импорт пакета…"}
      </button>
      {open && (
        <section aria-label="Импорт пакета">
          <h3>Локальный пакет</h3>
          <button
            disabled={disabled}
            onClick={() =>
              void choose?.()
                .then((path) => {
                  if (path) setSource(path);
                })
                .catch(() =>
                  setError("Не удалось открыть диалог выбора папки."),
                )
            }
          >
            Выбрать папку пакета
          </button>
          <p>{source || "Папка не выбрана"}</p>
          {applicationRef ? (
            <p>Приложение: {applicationRef}</p>
          ) : (
            <>
              <label>
                Тип
                <select value={kind} onChange={(e) => setKind(e.target.value)}>
                  <option value="application">
                    Приложения — вся папка application-packages
                  </option>
                  <option value="library">Библиотека</option>
                </select>
              </label>
              {kind === "library" && (
                <label>
                  Имя
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
              )}
            </>
          )}
          {error && <p role="alert">{error}</p>}
          <button
            disabled={
              disabled ||
              !source ||
              (!applicationRef && kind === "library" && !name)
            }
            onClick={() =>
              void review(
                source,
                applicationRef ? "application" : kind,
                applicationRef
                  ? applicationRef.split("@")[0]
                  : kind === "application"
                    ? ""
                    : name,
                applicationRef ? (applicationRef.split("@")[1] ?? "") : "",
                "",
              ).then((ok) => {
                if (ok) setOpen(false);
              })
            }
          >
            Проверить импорт
          </button>
          <button className="outline" onClick={() => setOpen(false)}>
            Отмена
          </button>
        </section>
      )}
    </>
  );
}
