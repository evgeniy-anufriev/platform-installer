import { useState } from "react";
import { objectValue, type ObjectValue } from "./application-draft";
import type { RuntimeSecretValuesInput } from "./backend";

export function ApplicationRegistryCredentials({
  libraryId,
  value,
  registries,
  disabled,
  runtimeDisabled,
  onChange,
  save,
  projectRevision = "",
}: {
  libraryId: string;
  value: unknown;
  registries: string[];
  disabled: boolean;
  runtimeDisabled: boolean;
  onChange: (value: ObjectValue) => void;
  save?: (input: RuntimeSecretValuesInput) => Promise<void>;
  projectRevision?: string;
}) {
  const entries = objectValue(value);
  const [registry, setRegistry] = useState("");
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const fields = Object.entries(entries).flatMap(([name, raw]) =>
    ["username", "password"].flatMap((field) => {
      const source = objectValue(objectValue(objectValue(raw)[field]).source);
      return source.kind === "runtime_secret_ref" &&
        typeof source.ref === "string"
        ? [
            {
              source: source.ref,
              label: `${field === "username" ? "Логин" : "Пароль"}: ${name}`,
              password: field === "password",
            },
          ]
        : [];
    }),
  );
  const options = [...new Set([...registries, ...Object.keys(entries)])];
  return (
    <section className="application-registry-credentials">
      <h3>Доступ к registry</h3>
      <p className="muted">
        Логин и пароль задаются только в runtime-сессии и применяются на целевых
        серверах.
      </p>
      <label>
        Registry
        <input
          aria-label="Registry"
          list={`registry-options-${libraryId}`}
          value={registry}
          disabled={disabled}
          onChange={(event) => setRegistry(event.target.value)}
          placeholder="registry.example:5000"
        />
        <datalist id={`registry-options-${libraryId}`}>
          {options.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
      </label>
      <button
        type="button"
        disabled={
          disabled ||
          !registry.trim() ||
          Object.hasOwn(entries, registry.trim())
        }
        onClick={() => {
          const reference = `registry-${crypto.randomUUID()}`;
          onChange({
            ...entries,
            [registry.trim()]: {
              username: {
                source: {
                  kind: "runtime_secret_ref",
                  ref: `${reference}-username`,
                },
              },
              password: {
                source: {
                  kind: "runtime_secret_ref",
                  ref: `${reference}-password`,
                },
              },
            },
          });
          setRegistry("");
        }}
      >
        Настроить runtime-доступ
      </button>
      {Object.keys(entries).map((name) => (
        <div className="row" key={name}>
          <span>{name}</span>
          <button
            type="button"
            className="outline"
            disabled={disabled}
            onClick={() => {
              const next = { ...entries };
              delete next[name];
              onChange(next);
            }}
          >
            Убрать назначение
          </button>
        </div>
      ))}
      {fields.length > 0 && save && (
        <>
          {runtimeDisabled && (
            <p className="muted">
              Сохраните настройки библиотеки перед вводом логина и пароля.
            </p>
          )}
          <button
            type="button"
            disabled={runtimeDisabled || saving}
            onClick={() => {
              setOpen(true);
              setValues({});
              setMessage("");
            }}
          >
            Логин и пароль registry
          </button>
          {message && <p role="status">{message}</p>}
          {open && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (runtimeDisabled || saving || !projectRevision) return;
                const submitted = values;
                setValues({});
                setSaving(true);
                void save({
                  projectRevision,
                  descriptorSetFingerprint: "",
                  serviceDeployment: "",
                  applicationLibrary: libraryId,
                  applicationSourceValues: submitted,
                  values: {},
                })
                  .then(() => {
                    setOpen(false);
                    setMessage("Логин и пароль сохранены только в сессии");
                  })
                  .catch(() =>
                    setMessage(
                      "Не удалось сохранить логин и пароль. Проверьте, что настройки registry сохранены в проекте.",
                    ),
                  )
                  .finally(() => setSaving(false));
              }}
            >
              {fields.map((field) => (
                <label key={field.source}>
                  {field.label}
                  <input
                    type={field.password ? "password" : "text"}
                    autoComplete={field.password ? "new-password" : "username"}
                    required
                    disabled={runtimeDisabled || saving}
                    value={values[field.source] || ""}
                    onChange={(event) =>
                      setValues((current) => ({
                        ...current,
                        [field.source]: event.target.value,
                      }))
                    }
                  />
                </label>
              ))}
              <button
                type="button"
                disabled={saving}
                onClick={() => {
                  setOpen(false);
                  setValues({});
                }}
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={runtimeDisabled || saving || !projectRevision}
              >
                Сохранить в сессии
              </button>
            </form>
          )}
        </>
      )}
    </section>
  );
}
