import { Fragment, useState, type ReactNode } from "react";
import { objectValue, type ObjectValue } from "./application-draft";

export function ApplicationLibraryResources({
  resources,
  bindings,
  deployments,
  disabled,
  onSave,
  onDirtyChange,
}: {
  resources: ObjectValue;
  bindings: ObjectValue;
  deployments: Record<string, { serviceType: string }>;
  disabled: boolean;
  onSave: (value: ObjectValue) => Promise<boolean>;
  onDirtyChange: (value: boolean) => void;
}) {
  const [edit, setEdit] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("postgresql.database");
  const [binding, setBinding] = useState("");
  const [mode, setMode] = useState("managed");
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const compatibleBindings = (type: string) =>
    Object.keys(bindings).filter(
      (key) =>
        deployments[String(objectValue(bindings[key]).deploymentRef)]
          ?.serviceType === type.split(".")[0],
    );
  const availableBindings = compatibleBindings(kind);
  const allIds = Object.keys(resources);
  const currentPage = Math.min(
    page,
    Math.max(0, Math.ceil(allIds.length / 2) - 1),
  );
  const visible = new Set(allIds.slice(currentPage * 2, currentPage * 2 + 2));
  const groups = new Map<string, string[]>();
  for (const key of Object.keys(bindings)) {
    const deployment = String(objectValue(bindings[key]).deploymentRef ?? key);
    if (!groups.has(deployment)) groups.set(deployment, []);
  }
  for (const [key, value] of Object.entries(resources)) {
    const ref = String(objectValue(value).binding ?? "");
    const deployment = String(objectValue(bindings[ref]).deploymentRef ?? ref);
    groups.set(deployment, [...(groups.get(deployment) ?? []), key]);
  }
  const open = (key: string) => {
    if (
      edit !== null &&
      !window.confirm("Отбросить несохранённую настройку ресурса?")
    )
      return;
    onDirtyChange(false);
    const row = objectValue(resources[key]);
    setEdit(key);
    setName(String(objectValue(row.parameters).name ?? ""));
    setKind(String(row.kind ?? "postgresql.database"));
    const candidates = compatibleBindings(
      String(row.kind ?? "postgresql.database"),
    );
    setBinding(
      String(row.binding ?? (candidates.length === 1 ? candidates[0] : "")),
    );
    setMode(String(row.mode ?? "managed"));
    setError("");
  };
  const close = () => {
    setEdit(null);
    onDirtyChange(false);
  };
  return (
    <section className="application-library-resources">
      <div className="row">
        <h3>Общие ресурсы</h3>
        <button disabled={disabled} onClick={() => open("")}>
          Добавить БД
        </button>
      </div>
      <p className="muted">
        Общие для приложений библиотеки. Удаление записи и изменение имени не
        удаляют и не переименовывают установленную БД. Ссылки проверяет Core при
        проверке проекта.
      </p>
      <table>
        <thead>
          <tr>
            <th>Ресурс</th>
            <th>Тип</th>
            <th>Имя</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {[...groups]
            .map(([deployment, keys]): [string, string[]] => [
              deployment,
              keys.filter((key) => visible.has(key)),
            ])
            .filter(([, keys]) => keys.length)
            .map(([deployment, keys]) => (
              <Group key={deployment} title={deployment}>
                {keys.map((key) => {
                  const row = objectValue(resources[key]);
                  return (
                    <tr key={key}>
                      <td>{key}</td>
                      <td>
                        {(
                          {
                            "postgresql.database": "PostgreSQL · БД",
                            "postgresql.schema": "PostgreSQL · Схема",
                            "clickhouse.database": "ClickHouse · БД",
                          } as Record<string, string>
                        )[String(row.kind)] ?? String(row.kind)}
                      </td>
                      <td>{String(objectValue(row.parameters).name ?? "—")}</td>
                      <td>
                        <button
                          className="outline"
                          disabled={disabled}
                          onClick={() => open(key)}
                        >
                          Настроить
                        </button>{" "}
                        <button
                          className="outline"
                          disabled={disabled}
                          onClick={async () => {
                            if (
                              !window.confirm(
                                `Удалить ресурс ${key} из проекта? Установленная БД сохранится. Связанные ссылки необходимо изменить отдельно.`,
                              )
                            )
                              return;
                            const next = { ...resources };
                            delete next[key];
                            if (await onSave(next)) {
                              if (edit === key) close();
                            }
                          }}
                        >
                          Удалить
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </Group>
            ))}
        </tbody>
      </table>
      {allIds.length > 2 && (
        <div className="row" aria-label="Страницы ресурсов">
          <button
            className="outline"
            disabled={currentPage === 0}
            onClick={() => setPage(currentPage - 1)}
          >
            Назад
          </button>
          <span>
            {currentPage + 1} / {Math.ceil(allIds.length / 2)}
          </span>
          <button
            className="outline"
            disabled={(currentPage + 1) * 2 >= allIds.length}
            onClick={() => setPage(currentPage + 1)}
          >
            Далее
          </button>
        </div>
      )}
      {!Object.keys(resources).length && (
        <p>Ресурсы не заданы. Добавьте БД и выберите подключение библиотеки.</p>
      )}
      {edit !== null && (
        <form
          className="application-resource-form"
          onSubmit={async (e) => {
            e.preventDefault();
            const id = edit || name;
            if (
              !/^[a-z][A-Za-z0-9_-]{0,127}$/.test(id) ||
              (!edit && Object.hasOwn(resources, id))
            ) {
              setError(
                "Укажите уникальное имя БД: латинская буква, цифры, _ или -.",
              );
              return;
            }
            if (!availableBindings.includes(binding)) {
              setError("Выберите сервис, соответствующий типу БД.");
              return;
            }
            const previous = objectValue(resources[edit]);
            if (
              await onSave({
                ...resources,
                [id]: {
                  ...previous,
                  kind,
                  binding,
                  mode,
                  parameters: { ...objectValue(previous.parameters), name },
                },
              })
            )
              close();
          }}
          onChange={() => onDirtyChange(true)}
        >
          <h4>{edit ? `Настройка ресурса ${edit}` : "Новая БД"}</h4>
          <label>
            Тип
            <select
              value={kind}
              onChange={(e) => {
                const next = e.target.value;
                setKind(next);
                const candidates = compatibleBindings(next);
                if (!candidates.includes(binding))
                  setBinding(candidates.length === 1 ? candidates[0] : "");
                setError("");
              }}
            >
              <option value="postgresql.database">PostgreSQL · БД</option>
              <option value="clickhouse.database">ClickHouse · БД</option>
              {kind === "postgresql.schema" && (
                <option value="postgresql.schema">PostgreSQL · Схема</option>
              )}
            </select>
          </label>
          <label>
            Подключение
            <select
              aria-label="Подключение библиотеки"
              value={binding}
              required
              onChange={(e) => setBinding(e.target.value)}
            >
              <option value="">Выберите подключение</option>
              {binding && !availableBindings.includes(binding) && (
                <option value={binding} disabled>
                  Недоступное подключение · {binding}
                </option>
              )}
              {availableBindings.map((key) => (
                <option key={key} value={key}>
                  {String(objectValue(bindings[key]).deploymentRef ?? key)} ·{" "}
                  {key}
                </option>
              ))}
            </select>
          </label>
          <label>
            Имя БД / схемы
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          {!edit && (
            <small>Имя также используется как ключ ресурса в библиотеке.</small>
          )}
          <label>
            Управление
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="managed">Создавать и проверять</option>
              <option value="existing">Использовать существующую</option>
            </select>
          </label>
          {error && <p role="alert">{error}</p>}
          <div className="row">
            <button disabled={disabled}>В черновик</button>
            <button type="button" className="outline" onClick={close}>
              Отмена
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Fragment>
      <tr className="application-resource-group">
        <th colSpan={4}>{title}</th>
      </tr>
      {children}
    </Fragment>
  );
}
