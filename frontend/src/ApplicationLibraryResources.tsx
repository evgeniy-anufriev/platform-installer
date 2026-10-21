import { Fragment, useState, type ReactNode } from "react";
import { objectValue, type ObjectValue } from "./application-draft";

export function ApplicationLibraryResources({
  resources,
  bindings,
  deployments,
  disabled,
  onSave,
  onDirtyChange,
  resolvedTopics = {},
  topicDefaults = {},
  databaseDefaults = {},
  clickhouseDefaults = {},
  redisDefaults = {},
  resolvedResources = {},
  showAddActions = true,
}: {
  resources: ObjectValue;
  bindings: ObjectValue;
  deployments: Record<string, { serviceType: string }>;
  disabled: boolean;
  onSave: (value: ObjectValue) => Promise<boolean>;
  onDirtyChange: (value: boolean) => void;
  resolvedTopics?: ObjectValue;
  topicDefaults?: ObjectValue;
  databaseDefaults?: ObjectValue;
  clickhouseDefaults?: ObjectValue;
  redisDefaults?: ObjectValue;
  resolvedResources?: ObjectValue;
  showAddActions?: boolean;
}) {
  const [edit, setEdit] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("postgresql.database");
  const [binding, setBinding] = useState("");
  const [mode, setMode] = useState("managed");
  const [error, setError] = useState("");
  const [partitions, setPartitions] = useState("");
  const [replicationFactor, setReplicationFactor] = useState("");
  const [minISR, setMinISR] = useState("");
  const [topicConfig, setTopicConfig] = useState("");
  const compatibleBindings = (type: string) =>
    Object.keys(bindings).filter(
      (key) =>
        deployments[String(objectValue(bindings[key]).deploymentRef)]
          ?.serviceType === type.split(".")[0],
    );
  const availableBindings = compatibleBindings(kind);
  const defaultsByKind: Record<string, ObjectValue> = {
    "kafka.topic": topicDefaults,
    "postgresql.database": databaseDefaults,
    "clickhouse.database": clickhouseDefaults,
    "redis.key": redisDefaults,
  };
  const hasDefault = Object.hasOwn(defaultsByKind[kind] ?? {}, edit ?? "");
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
  const open = (key: string, newKind = "postgresql.database") => {
    if (
      edit !== null &&
      !window.confirm("Отбросить несохранённую настройку ресурса?")
    )
      return;
    onDirtyChange(false);
    const row = objectValue(resources[key]);
    setEdit(key);
    setName(String(objectValue(row.parameters).name ?? ""));
    setKind(String(row.kind ?? newKind));
    const parameters = objectValue(row.parameters);
    const config = objectValue(parameters.config);
    setPartitions(String(parameters.partitions ?? ""));
    setReplicationFactor(String(parameters.replication_factor ?? ""));
    setMinISR(String(config["min.insync.replicas"] ?? ""));
    setTopicConfig(
      Object.entries(config)
        .filter(([k]) => k !== "min.insync.replicas")
        .map(([k, v]) => `${k}=${String(v)}`)
        .join("\n"),
    );
    const candidates = compatibleBindings(String(row.kind ?? newKind));
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
        {showAddActions && (
          <>
            <button disabled={disabled} onClick={() => open("")}>
              Добавить БД
            </button>
            {compatibleBindings("kafka.topic").length > 0 && (
              <button
                disabled={disabled}
                onClick={() => open("", "kafka.topic")}
              >
                Добавить топик
              </button>
            )}
          </>
        )}
      </div>
      {showAddActions && (
        <>
          {compatibleBindings("redis.key").length > 0 && (
            <button disabled={disabled} onClick={() => open("", "redis.key")}>
              Добавить ключ Redis
            </button>
          )}
        </>
      )}
      {showAddActions &&
        Object.entries(defaultsByKind).flatMap(([resourceKind, defaults]) =>
          Object.keys(defaults)
            .filter((id) => !Object.hasOwn(resources, id))
            .map((id) => (
              <button
                key={resourceKind + id}
                disabled={disabled}
                onClick={() => open(id, resourceKind)}
              >
                Добавить из defaults · {id}
              </button>
            )),
        )}
      <p className="muted">
        Общие для приложений библиотеки. Удаление записи и изменение имени не
        удаляют и не переименовывают установленный ресурс. Ссылки проверяет Core
        при проверке проекта.
      </p>
      <div
        className="application-resources-scroll"
        role="region"
        aria-label="Ресурсы библиотеки"
        tabIndex={0}
      >
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
                              "kafka.topic": "Kafka · Топик",
                              "redis.key": "Redis · Ключ",
                            } as Record<string, string>
                          )[String(row.kind)] ?? String(row.kind)}
                        </td>
                        <td>
                          {String(
                            objectValue(resolvedTopics[key]).name ??
                              objectValue(
                                objectValue(resolvedResources[key]).parameters,
                              ).name ??
                              objectValue(row.parameters).name ??
                              "—",
                          )}
                          {row.kind === "kafka.topic" && (
                            <small>
                              {resolvedTopics[key]
                                ? `Core: partitions=${String(objectValue(resolvedTopics[key]).partitions)}, RF=${String(objectValue(resolvedTopics[key]).replicationFactor)}, minISR=${String(objectValue(objectValue(resolvedTopics[key]).config)["min.insync.replicas"])}`
                                : "Параметры Core ещё не рассчитаны"}
                              {objectValue(resolvedTopics[key])
                                .minISRWarning === true && " · minISR выше RF"}
                            </small>
                          )}
                        </td>
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
                                  `Удалить ресурс ${key} из проекта? Установленный ресурс сохранится. Связанные ссылки необходимо изменить отдельно.`,
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
      </div>
      {!Object.keys(resources).length && <p>Ресурсы библиотеки не заданы.</p>}
      {edit !== null && (
        <form
          className="application-resource-form"
          onSubmit={async (e) => {
            e.preventDefault();
            const id =
              edit ||
              (kind === "kafka.topic" || kind === "redis.key"
                ? (kind === "redis.key" ? "key_" : "topic_") +
                  name.replace(/[^A-Za-z0-9_-]/g, "_").slice(0, 122)
                : name);
            if (
              !/^[a-z][A-Za-z0-9_-]{0,127}$/.test(id) ||
              (!edit && Object.hasOwn(resources, id))
            ) {
              setError(
                "Укажите уникальное имя ресурса: латинская буква, цифры, _ или -.",
              );
              return;
            }
            if (!availableBindings.includes(binding)) {
              setError("Выберите сервис, соответствующий типу ресурса.");
              return;
            }
            const previous = objectValue(resources[edit]);
            let parameters: ObjectValue = {
              ...(previous.kind === kind
                ? objectValue(previous.parameters)
                : {}),
              name,
            };
            if (!name && hasDefault) delete parameters.name;
            if (kind === "kafka.topic") {
              const config: ObjectValue = {};
              for (const line of topicConfig
                .split("\n")
                .filter((v) => v.trim())) {
                const at = line.indexOf("=");
                if (
                  at < 1 ||
                  line.slice(0, at).trim() === "min.insync.replicas"
                ) {
                  setError(
                    "Используйте ключ=значение; min.insync.replicas задаётся полем minISR.",
                  );
                  return;
                }
                config[line.slice(0, at).trim()] = line.slice(at + 1);
              }
              if (minISR) config["min.insync.replicas"] = Number(minISR);
              parameters = {
                ...(name ? { name } : {}),
                config,
                ...(partitions ? { partitions: Number(partitions) } : {}),
                ...(replicationFactor
                  ? { replication_factor: Number(replicationFactor) }
                  : {}),
              };
            }
            const resource: ObjectValue = {
              ...previous,
              kind,
              binding,
              parameters,
            };
            if (kind === "redis.key") {
              delete resource.mode;
              delete resource.databaseRef;
            } else resource.mode = mode;
            if (await onSave({ ...resources, [id]: resource })) close();
          }}
          onChange={() => onDirtyChange(true)}
        >
          <h4>{edit ? `Настройка ресурса ${edit}` : "Новый ресурс"}</h4>
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
              <option value="redis.key">Redis · Ключ</option>
              {compatibleBindings("kafka.topic").length > 0 && (
                <option value="kafka.topic">Kafka · Топик</option>
              )}
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
            {kind === "kafka.topic"
              ? "Имя топика"
              : kind === "redis.key"
                ? "Имя ключа Redis"
                : "Имя БД / схемы"}
            <input
              required={!hasDefault}
              value={name}
              placeholder={hasDefault ? "Из defaults библиотеки" : ""}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          {!edit && (
            <small>ID ресурса в библиотеке формируется из имени.</small>
          )}
          {kind === "kafka.topic" && (
            <>
              <label>
                Партиции
                <input
                  type="number"
                  min="1"
                  placeholder="По умолчанию: 1"
                  value={partitions}
                  onChange={(e) => setPartitions(e.target.value)}
                />
              </label>
              <label>
                Replication factor
                <input
                  type="number"
                  min="1"
                  placeholder="Авто · из Kafka deployment"
                  value={replicationFactor}
                  onChange={(e) => setReplicationFactor(e.target.value)}
                />
              </label>
              <label>
                minISR
                <input
                  type="number"
                  min="1"
                  placeholder="Авто · из effective RF"
                  value={minISR}
                  onChange={(e) => setMinISR(e.target.value)}
                />
              </label>
              <label>
                Другие параметры топика · ключ=значение
                <textarea
                  value={topicConfig}
                  onChange={(e) => setTopicConfig(e.target.value)}
                />
              </label>
              <p>
                Очистите поле для значения по умолчанию. Созданные топики
                автоматически не изменяются; несовпадения покажет Core.
              </p>
            </>
          )}
          {kind !== "redis.key" && (
            <label>
              Управление
              <select value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="managed">Создавать и проверять</option>
                <option value="existing">Использовать существующую</option>
              </select>
            </label>
          )}
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
