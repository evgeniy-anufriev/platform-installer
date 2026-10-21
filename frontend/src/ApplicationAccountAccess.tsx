import { useState } from "react";
import { objectValue, type ObjectValue } from "./application-draft";

type Access = {
  databaseRef: string;
  privileges: string[];
  additionalCreatorRoles?: string[];
};
export function ApplicationAccountAccess({
  serviceType,
  deployment,
  resources,
  bindings,
  account,
  inherited,
  disabled,
  onSave,
  onDirtyChange,
}: {
  serviceType: string;
  deployment: string;
  resources: ObjectValue;
  bindings: ObjectValue;
  account: ObjectValue;
  inherited: ObjectValue;
  disabled: boolean;
  onSave: (metadata: ObjectValue) => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [edit, setEdit] = useState<number | null>(null),
    [database, setDatabase] = useState("");
  const [rights, setRights] = useState<string[]>([]),
    [creators, setCreators] = useState("");
  const [error, setError] = useState("");
  const pg = serviceType === "postgresql",
    ch = serviceType === "clickhouse";
  const source = Object.hasOwn(account, pg ? "databaseAccess" : "grants")
    ? account
    : inherited;
  const raw = source[pg ? "databaseAccess" : "grants"];
  const rows: Access[] = Array.isArray(raw)
    ? raw.map((value) => objectValue(value) as unknown as Access)
    : [];
  const candidates = Object.entries(resources).filter(([, value]) => {
    const resource = objectValue(value);
    return (
      resource.kind === `${serviceType}.database` &&
      String(objectValue(bindings[String(resource.binding)]).deploymentRef) ===
        deployment
    );
  });
  const legacy =
    pg &&
    !Object.hasOwn(account, "databaseAccess") &&
    ["grants", "databaseRef"].some(
      (key) => Object.hasOwn(account, key) || Object.hasOwn(inherited, key),
    );
  const preciseCH =
    ch &&
    rows.some((row) => JSON.stringify(objectValue(row).tables) !== '["*"]');
  const save = async (next: Access[]) => {
    const value: ObjectValue = pg
      ? { databaseAccess: next }
      : {
          databaseRef:
            account.databaseRef ??
            inherited.databaseRef ??
            next[0]?.databaseRef,
          grants: next.map((row) => ({
            databaseRef: row.databaseRef,
            tables: ["*"],
            privileges: row.privileges,
          })),
        };
    if (await onSave(value)) {
      setEdit(null);
      setError("");
      onDirtyChange(false);
    }
  };
  const open = (index: number) => {
    const row = rows[index];
    setEdit(index);
    setDatabase(row?.databaseRef ?? "");
    setRights(row?.privileges ?? []);
    setCreators((row?.additionalCreatorRoles ?? []).join(", "));
    setError("");
    onDirtyChange(true);
  };
  if (!pg && !ch) return null;
  if (legacy || preciseCH)
    return (
      <section>
        <p className="muted">
          Используются точные права пакета. Переход на все объекты БД расширяет
          доступ; текущие правила сохранены в расширенных настройках.
        </p>
        {legacy && (
          <button
            disabled={disabled}
            onClick={() => {
              if (
                window.confirm(
                  "Перейти на права для всех схем и объектов выбранных БД? Точные правила будут заменены после Review и Apply.",
                )
              )
                void onSave({ databaseAccess: [] });
            }}
          >
            Настроить доступ ко всем объектам БД
          </button>
        )}
      </section>
    );
  return (
    <section className="application-account-access">
      <header>
        <h4>Доступ к базам данных</h4>
        <button
          disabled={disabled || edit !== null}
          onClick={() => open(rows.length)}
        >
          ＋ Добавить доступ
        </button>
      </header>
      <table>
        <thead>
          <tr>
            <th>База данных</th>
            <th>Права</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.databaseRef}>
              <td>
                {String(
                  objectValue(
                    objectValue(resources[row.databaseRef]).parameters,
                  ).name ?? row.databaseRef,
                )}
              </td>
              <td>
                {row.privileges.join(" · ")}
                {row.additionalCreatorRoles?.length ? (
                  <small>
                    Создатели: {row.additionalCreatorRoles.join(", ")}
                  </small>
                ) : null}
              </td>
              <td>
                <button
                  disabled={disabled || edit !== null}
                  onClick={() => open(i)}
                >
                  Изменить
                </button>
                <button
                  disabled={disabled || edit !== null}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Удалить доступ? Права будут сняты только при Apply. БД и учётная запись сохранятся.",
                      )
                    )
                      void save(rows.filter((_, index) => index !== i));
                  }}
                >
                  Удалить
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p>Доступ к БД не задан.</p>}
      {edit !== null && (
        <fieldset>
          <legend>Доступ к БД</legend>
          <label>
            База данных
            <select
              aria-label="База данных доступа"
              value={database}
              disabled={disabled}
              onChange={(event) => setDatabase(event.target.value)}
            >
              <option value="">Выберите БД библиотеки</option>
              {candidates
                .filter(
                  ([id]) =>
                    !rows.some(
                      (row, i) => row.databaseRef === id && i !== edit,
                    ),
                )
                .map(([id, resource]) => (
                  <option key={id} value={id}>
                    {String(
                      objectValue(objectValue(resource).parameters).name ?? id,
                    )}
                  </option>
                ))}
            </select>
          </label>
          <div className="application-rights">
            {(pg
              ? ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE"]
              : ["SELECT", "INSERT"]
            ).map((right) => (
              <label key={right}>
                <input
                  type="checkbox"
                  checked={rights.includes(right)}
                  disabled={disabled}
                  onChange={(event) =>
                    setRights((current) =>
                      event.target.checked
                        ? [...current, right]
                        : current.filter((p) => p !== right),
                    )
                  }
                />
                {right}
              </label>
            ))}
          </div>
          {pg && (
            <details>
              <summary>Создатели будущих объектов</summary>
              <p>
                Владелец библиотеки включён автоматически. Дополнительные роли
                должны принадлежать этой библиотеке; Core проверит их при
                выполнении.
              </p>
              <label>
                Роли миграций через запятую
                <input
                  aria-label="Роли миграций"
                  value={creators}
                  disabled={disabled}
                  onChange={(event) => setCreators(event.target.value)}
                />
              </label>
            </details>
          )}
          {error && <p role="alert">{error}</p>}
          <button
            disabled={disabled}
            onClick={() => {
              setEdit(null);
              onDirtyChange(false);
            }}
          >
            Отмена
          </button>
          <button
            disabled={
              disabled ||
              !rights.length ||
              !candidates.some(([id]) => id === database)
            }
            onClick={() => {
              const roles = creators
                .split(",")
                .map((v) => v.trim())
                .filter(Boolean);
              if (
                roles.some((role) => !/^[a-z_][a-z0-9_-]{0,62}$/.test(role)) ||
                new Set(roles).size !== roles.length
              ) {
                setError("Укажите уникальные имена ролей миграций.");
                return;
              }
              const next = [...rows];
              next[edit] = {
                databaseRef: database,
                privileges: [...rights].sort(),
                ...(pg && roles.length
                  ? { additionalCreatorRoles: roles }
                  : {}),
              };
              void save(next);
            }}
          >
            В черновик
          </button>
        </fieldset>
      )}
    </section>
  );
}

export function ApplicationRedisAccess({
  value,
  disabled,
  onSave,
  onDirtyChange,
  sentinel = false,
}: {
  value: ObjectValue;
  disabled: boolean;
  sentinel?: boolean;
  onSave: (value: ObjectValue) => Promise<boolean>;
  onDirtyChange: (value: boolean) => void;
}) {
  const [fields, setFields] = useState(() =>
    Object.fromEntries(
      ["commands", "keys", "channels"].map((key) => [
        key,
        Array.isArray(value[key]) ? (value[key] as string[]).join(", ") : "",
      ]),
    ),
  );
  const [dirty, setDirty] = useState(false);
  return (
    <fieldset className="application-redis-access">
      <legend>ACL {sentinel ? "Sentinel" : "Redis"}</legend>
      {["commands", "keys", "channels"].map((key) => (
        <label key={key}>
          {
            {
              commands: "Команды",
              keys: "Шаблоны ключей",
              channels: "Шаблоны каналов",
            }[key]
          }
          <input
            aria-label={`ACL ${key}`}
            disabled={disabled}
            value={fields[key]}
            placeholder="Значения через запятую"
            onChange={(event) => {
              setFields({ ...fields, [key]: event.target.value });
              setDirty(true);
              onDirtyChange(true);
            }}
          />
        </label>
      ))}
      <p className="muted">
        Права задаются списком команд и шаблонов. Core проверит формат данных.
      </p>
      <button
        disabled={disabled || !dirty || !fields.commands.trim()}
        onClick={() => {
          const next = Object.fromEntries(
            ["commands", "keys", "channels"].map((key) => [
              key,
              fields[key]
                .split(",")
                .map((v) => v.trim())
                .filter(Boolean),
            ]),
          );
          void onSave(next).then((ok) => {
            if (ok) {
              setDirty(false);
              onDirtyChange(false);
            }
          });
        }}
      >
        В черновик
      </button>
    </fieldset>
  );
}
