import { useState } from "react";

export function ApplicationPackageImport({
  disabled,
  choose,
  review,
}: {
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
  const [version, setVersion] = useState("");
  const [digest, setDigest] = useState("");
  const [error, setError] = useState("");
  return (
    <>
      <button
        className="outline"
        disabled={disabled || !choose}
        onClick={() => setOpen((v) => !v)}
      >
        Импорт пакета…
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
          <label>
            Тип
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="application">Приложение</option>
              <option value="library">Библиотека</option>
            </select>
          </label>
          <label>
            Имя
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label>
            Версия
            <input
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="1.0.0"
            />
          </label>
          <label>
            Ожидаемый digest пакета
            <input
              value={digest}
              onChange={(e) => setDigest(e.target.value)}
              placeholder="sha256:…"
            />
          </label>
          <p>
            Только локальный data-only пакет. Публикация после проверки и общего
            Review/Save.
          </p>
          {error && <p role="alert">{error}</p>}
          <button
            disabled={disabled || !source || !name || !version || !digest}
            onClick={() =>
              void review(source, kind, name, version, digest).then((ok) => {
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
