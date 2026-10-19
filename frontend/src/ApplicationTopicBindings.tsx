import { objectValue, type ObjectValue } from "./application-draft";

export function ApplicationTopicBindings({
  connections,
  resources,
  bindings,
  deployments,
  defaults,
  authored,
  disabled,
  onSave,
  onReset,
  resolvedTopics = {},
}: {
  connections: ObjectValue;
  resources: ObjectValue;
  bindings: ObjectValue;
  deployments: Record<string, { serviceType: string }>;
  defaults: ObjectValue;
  authored: ObjectValue;
  disabled: boolean;
  onSave: (value: ObjectValue) => Promise<boolean>;
  onReset: () => Promise<boolean>;
  resolvedTopics?: ObjectValue;
}) {
  const kafka = Object.entries(connections).filter(
    ([, raw]) =>
      deployments[
        String(
          objectValue(bindings[String(objectValue(raw).library_binding)])
            .deploymentRef,
        )
      ]?.serviceType === "kafka",
  );
  if (
    !kafka.length ||
    (!Object.keys(defaults).length && !Object.keys(authored).length)
  )
    return null;
  return (
    <section className="application-section">
      <h3>Топики Kafka</h3>
      <p>
        Выберите ресурсы библиотеки. Именованные роли используются в шаблонах
        ENV приложения. Выбор не создаёт ACL.
      </p>
      {kafka.map(([alias, raw]) => {
        const provider = objectValue(
          bindings[String(objectValue(raw).library_binding)],
        ).deploymentRef;
        const inherited = defaults[alias];
        const roles = objectValue(inherited);
        const roleOverrides = objectValue(authored[alias]);
        const saveRoles = (next: ObjectValue) => {
          const value = { ...authored };
          if (Object.keys(next).length) value[alias] = next;
          else delete value[alias];
          void (Object.keys(value).length ? onSave(value) : onReset());
        };
        const selected = Array.isArray(authored[alias] ?? inherited)
          ? ((authored[alias] ?? inherited) as string[])
          : [];
        const available = Object.entries(resources).filter(([, value]) => {
          const r = objectValue(value);
          return (
            r.kind === "kafka.topic" &&
            objectValue(bindings[String(r.binding)]).deploymentRef === provider
          );
        });
        return (
          <fieldset key={alias}>
            <legend>
              {alias} · {String(provider)}
            </legend>
            <small>
              {Object.hasOwn(authored, alias)
                ? "Переопределение экземпляра"
                : "Из defaults приложения"}
            </small>
            {Object.keys(roles).length > 0
              ? Object.keys(roles).map((role) => {
                  const value = String(
                    roleOverrides[role] ?? roles[role] ?? "",
                  );
                  return (
                    <div key={role}>
                      <label>
                        {role}
                        <select
                          aria-label={`Топик ${alias}.${role}`}
                          value={value}
                          disabled={disabled}
                          onChange={(e) =>
                            saveRoles({
                              ...roleOverrides,
                              [role]: e.target.value,
                            })
                          }
                        >
                          <option value="">Выберите ресурс</option>
                          {value && !available.some(([id]) => id === value) && (
                            <option value={value}>
                              Недоступный ресурс: {value}
                            </option>
                          )}
                          {available.map(([id]) => (
                            <option key={id} value={id}>
                              {id}
                              {resolvedTopics[id]
                                ? ` · ${String(objectValue(resolvedTopics[id]).name)}`
                                : " · имя ещё не рассчитано Core"}
                            </option>
                          ))}
                        </select>
                      </label>
                      <small>
                        {Object.hasOwn(roleOverrides, role)
                          ? "Переопределение экземпляра"
                          : "Из defaults приложения"}
                      </small>
                      <button
                        type="button"
                        className="outline"
                        disabled={
                          disabled || !Object.hasOwn(roleOverrides, role)
                        }
                        onClick={() => {
                          const next = { ...roleOverrides };
                          delete next[role];
                          saveRoles(next);
                        }}
                      >
                        Сбросить · {role}
                      </button>
                    </div>
                  );
                })
              : available.map(([id, rawResource]) => (
                  <label key={id}>
                    <input
                      type="checkbox"
                      checked={selected.includes(id)}
                      disabled={disabled}
                      onChange={(e) =>
                        void onSave({
                          ...authored,
                          [alias]: e.target.checked
                            ? [...selected, id]
                            : selected.filter((x) => x !== id),
                        })
                      }
                    />
                    {String(
                      objectValue(objectValue(rawResource).parameters).name ??
                        id,
                    )}{" "}
                    · {id}
                  </label>
                ))}
            {selected
              .filter((id) => !available.some(([key]) => key === id))
              .map((id) => (
                <p key={id}>Недоступный ресурс: {id}</p>
              ))}
            {!available.length && (
              <p>Совместимые топики библиотеки не заданы.</p>
            )}
            <button
              type="button"
              className="outline"
              disabled={disabled || !Object.hasOwn(authored, alias)}
              onClick={() => {
                const next = { ...authored };
                delete next[alias];
                void (Object.keys(next).length ? onSave(next) : onReset());
              }}
            >
              Сбросить топики · {alias}
            </button>
          </fieldset>
        );
      })}
    </section>
  );
}
