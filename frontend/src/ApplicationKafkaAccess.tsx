import { useState } from "react";
import { objectValue, type ObjectValue } from "./application-draft";

// Core resolves identities and validates ACLs. This editor only stages the existing grants list.
export function ApplicationKafkaAccess({
  account,
  inherited,
  resolved,
  resolvedResources,
  disabled,
  onSave,
  onDirtyChange,
}: {
  account: ObjectValue;
  inherited: ObjectValue;
  resolved: ObjectValue;
  resolvedResources: ObjectValue;
  disabled: boolean;
  onSave: (grants: ObjectValue[] | undefined) => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [editing, setEditing] = useState<ObjectValue[] | null>(null);
  const [error, setError] = useState("");
  const current = Array.isArray(resolved.grants) ? resolved.grants : undefined;
  const source = Object.hasOwn(account, "grants")
    ? account.grants
    : inherited.grants;
  const rows =
    editing ??
    (current ?? (Array.isArray(source) ? source : [])).map(objectValue);
  const finish = async (grants: ObjectValue[] | undefined) => {
    if (await onSave(grants)) {
      setEditing(null);
      setError("");
      onDirtyChange(false);
    } else setError("Не удалось добавить ACL в черновик.");
  };
  const change = (index: number, value: ObjectValue) =>
    setEditing(rows.map((row, i) => (i === index ? value : row)));
  return (
    <fieldset className="application-kafka-access">
      <legend>ACL Kafka</legend>
      <p className="muted">
        {editing
          ? "Переопределение списка ACL"
          : current
            ? "Текущая проекция Core"
            : "Нет актуальной проекции Core — показаны исходные декларации. Сохраните проект и выполните проверку."}
        {Object.hasOwn(account, "grants")
          ? " · Переопределено"
          : " · Наследуется"}
      </p>
      <div className="application-table-scroll">
        <table>
          <thead>
            <tr>
              <th>Ресурс</th>
              <th>Имя / ссылка</th>
              <th>Сопоставление</th>
              <th>Операции</th>
              {editing && <th>Действия</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => {
              const topicRef = Object.hasOwn(row, "topicRef");
              const name = topicRef
                ? (objectValue(
                    objectValue(resolvedResources[String(row.topicRef)])
                      .parameters,
                  ).name ?? row.topicRef)
                : row.name;
              return (
                <tr key={index}>
                  <td>
                    {editing ? (
                      <select
                        aria-label={`Ресурс ACL ${index + 1}`}
                        disabled={disabled}
                        value={
                          topicRef
                            ? "topicRef"
                            : String(row.resourceType ?? "group")
                        }
                        onChange={(e) => {
                          const next = { ...row };
                          delete next.topicRef;
                          delete next.resourceType;
                          delete next.name;
                          delete next.patternType;
                          change(
                            index,
                            e.target.value === "topicRef"
                              ? { ...next, topicRef: "" }
                              : {
                                  ...next,
                                  resourceType: e.target.value,
                                  name: "",
                                  patternType: "literal",
                                },
                          );
                        }}
                      >
                        <option value="topicRef">Топик · ссылка</option>
                        <option value="topic">Топики · префикс</option>
                        <option value="group">Consumer group</option>
                        <option value="transactional-id">
                          Transactional ID
                        </option>
                        <option value="cluster">Cluster</option>
                      </select>
                    ) : topicRef || row.resourceType === "topic" ? (
                      "Топик"
                    ) : row.resourceType === "group" ? (
                      "Consumer group"
                    ) : (
                      String(row.resourceType ?? "—")
                    )}
                  </td>
                  <td>
                    {editing ? (
                      <input
                        aria-label={`Имя или ссылка ACL ${index + 1}`}
                        disabled={disabled}
                        value={String(
                          (topicRef ? row.topicRef : row.name) ?? "",
                        )}
                        onChange={(e) =>
                          change(index, {
                            ...row,
                            [topicRef ? "topicRef" : "name"]: e.target.value,
                          })
                        }
                      />
                    ) : (
                      String(name ?? "—")
                    )}
                  </td>
                  <td>
                    {editing && !topicRef ? (
                      <select
                        aria-label={`Сопоставление ACL ${index + 1}`}
                        disabled={disabled}
                        value={String(row.patternType ?? "literal")}
                        onChange={(e) =>
                          change(index, { ...row, patternType: e.target.value })
                        }
                      >
                        <option value="literal">literal</option>
                        <option value="prefixed">prefixed</option>
                      </select>
                    ) : (
                      String(row.patternType ?? "literal")
                    )}
                  </td>
                  <td>
                    {editing ? (
                      <input
                        aria-label={`Операции ACL ${index + 1}`}
                        disabled={disabled}
                        value={
                          Array.isArray(row.operations)
                            ? row.operations.join(", ")
                            : ""
                        }
                        onChange={(e) =>
                          change(index, {
                            ...row,
                            operations: e.target.value
                              .split(",")
                              .map((s) => s.trim()),
                          })
                        }
                      />
                    ) : Array.isArray(row.operations) ? (
                      row.operations.join(", ")
                    ) : (
                      "—"
                    )}
                  </td>
                  {editing && (
                    <td>
                      <button
                        className="outline"
                        disabled={disabled}
                        aria-label={`Удалить ACL ${index + 1}`}
                        onClick={() =>
                          setEditing(rows.filter((_, i) => i !== index))
                        }
                      >
                        Удалить
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!rows.length && <p>ACL не объявлены.</p>}
      <p className="muted">
        Снятие декларации не отзывает уже выданные ACL. Допустимость ресурсов и
        операций проверяет Core.
      </p>
      {editing ? (
        <>
          <p className="muted">
            Операции — через запятую. Имя или ссылка сохраняются как введены,
            без вычисления шаблонов. Переопределение заменяет весь список;
            значения из проекции Core становятся явными.
          </p>
          <button
            className="outline"
            disabled={disabled}
            onClick={() =>
              setEditing([...rows, { topicRef: "", operations: [] }])
            }
          >
            Добавить ACL
          </button>
          <button disabled={disabled} onClick={() => void finish(rows)}>
            В черновик
          </button>
          <button
            className="outline"
            disabled={disabled}
            onClick={() => {
              setEditing(null);
              setError("");
              onDirtyChange(false);
            }}
          >
            Отмена
          </button>
        </>
      ) : (
        <>
          <button
            className="outline"
            disabled={disabled || (!current && !Array.isArray(account.grants))}
            onClick={() => {
              // Keep authored expressions when already overridden; otherwise explicitly copy the Core projection.
              setEditing(
                (Array.isArray(account.grants)
                  ? account.grants
                  : (current ?? [])
                ).map((row) => ({ ...objectValue(row) })),
              );
              onDirtyChange(true);
            }}
          >
            Переопределить ACL
          </button>
          <button
            className="outline"
            disabled={disabled || !Object.hasOwn(account, "grants")}
            onClick={() => void finish(undefined)}
          >
            Сбросить ACL к наследованию
          </button>
        </>
      )}
      {error && <p role="alert">{error}</p>}
    </fieldset>
  );
}
