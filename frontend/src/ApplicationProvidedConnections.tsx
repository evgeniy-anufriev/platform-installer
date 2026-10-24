import { objectValue } from "./application-draft";
import { ApplicationValueFields } from "./ApplicationValueFields";
import { CredentialSourceEditor } from "./ApplicationCredentials";
import {
  ApplicationRuntimeSecretField,
  type ApplicationSecretSession,
} from "./ApplicationRuntimeSecretField";

type Obj = Record<string, unknown>;

// The package declares exports; the editor changes only parameters and source descriptors.
export function ApplicationProvidedConnections({
  definitions,
  value,
  resolved,
  disabled,
  onSave,
  onDirtyChange,
  secretSession,
}: {
  definitions: Obj;
  value: Obj;
  resolved: Obj;
  disabled: boolean;
  onSave: (value: Obj) => Promise<boolean>;
  onDirtyChange: (dirty: boolean, key: string) => void;
  secretSession?: ApplicationSecretSession;
}) {
  return (
    <>
      {Object.entries(definitions).map(([name, raw]) => {
        const declaration = objectValue(raw),
          override = objectValue(value[name]);
        const credentials = objectValue(override.credentials);
        const save = (entry: Obj) => onSave({ ...value, [name]: entry });
        return (
          <section
            key={name}
            className="application-provided-connection"
            aria-label={`Предоставляемое подключение ${name}`}
          >
            <h3>Предоставляемое подключение · {name}</h3>
            <p>
              {String(declaration.application)} · {String(declaration.protocol)}{" "}
              ·{" "}
              {String(
                objectValue(resolved[name]).url ?? "Адрес ещё не рассчитан",
              )}
            </p>
            <ApplicationValueFields
              compact
              label="Параметры подключения"
              defaults={objectValue(declaration.parameters)}
              value={objectValue(override.parameters)}
              disabled={disabled}
              onDirtyChange={(dirty) =>
                onDirtyChange(dirty, name + ":parameters")
              }
              onSave={(parameters) => save({ ...override, parameters })}
            />
            <div className="application-credential-scroll">
              <table className="application-provided-credentials">
                <thead>
                  <tr>
                    <th>Поле</th>
                    <th>Источник и значение / ссылка</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(objectValue(declaration.credentials)).map(
                    ([field, source]) => (
                      <tr key={field}>
                        <th scope="row">{field}</th>
                        <td>
                          <CredentialSourceEditor
                            runtimeInput={
                              secretSession ? (
                                <ApplicationRuntimeSecretField
                                  session={secretSession}
                                  label={`${name} · ${field}`}
                                  sourceRef={String(
                                    objectValue(
                                      objectValue(
                                        objectValue(
                                          objectValue(resolved[name])
                                            .credentials,
                                        )[field],
                                      ).source,
                                    ).ref ?? "",
                                  )}
                                />
                              ) : undefined
                            }
                            compact
                            key={field + JSON.stringify(credentials[field])}
                            label={field}
                            literalLabel="Значение"
                            source={objectValue(
                              objectValue(credentials[field]).source,
                            )}
                            packageSource={objectValue(
                              objectValue(source).source,
                            )}
                            allowLiteral={
                              objectValue(source).sensitive === false
                            }
                            disabled={disabled}
                            onDirtyChange={(dirty) =>
                              onDirtyChange(dirty, name + ":" + field)
                            }
                            onSave={(next) =>
                              save({
                                ...override,
                                credentials: {
                                  ...credentials,
                                  [field]: { source: next },
                                },
                              })
                            }
                            onReset={() => {
                              const next = { ...credentials };
                              delete next[field];
                              return save({ ...override, credentials: next });
                            }}
                          />
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
            <p className="muted">
              Значения секретов вводятся здесь и сохраняются только в сессии.
            </p>
            <button
              className="outline"
              disabled={disabled || !Object.hasOwn(value, name)}
              onClick={() => {
                const next = { ...value };
                delete next[name];
                void onSave(next);
              }}
            >
              Сбросить подключение {name}
            </button>
          </section>
        );
      })}
    </>
  );
}
