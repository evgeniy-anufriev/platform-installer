import { useState } from "react";
import { ApplicationSecretInputs } from "./ApplicationSecretInputs";
import { objectValue, type ObjectValue } from "./application-draft";
import type {
  RuntimeSecretDescriptorOperation,
  RuntimeSecretValuesInput,
} from "./backend";

export function ApplicationRegistryCredentials({
  libraryId,
  value,
  registries,
  disabled,
  runtimeDisabled,
  onChange,
  load,
  save,
}: {
  libraryId: string;
  value: unknown;
  registries: string[];
  disabled: boolean;
  runtimeDisabled: boolean;
  onChange: (value: ObjectValue) => void;
  load?: () => Promise<RuntimeSecretDescriptorOperation>;
  save?: (input: RuntimeSecretValuesInput) => Promise<void>;
}) {
  const entries = objectValue(value);
  const [registry, setRegistry] = useState("");
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
      {Object.keys(entries).length > 0 && load && save && (
        <>
          {runtimeDisabled && (
            <p className="muted">
              Сохраните настройки библиотеки перед вводом логина и пароля.
            </p>
          )}
          <ApplicationSecretInputs
            inline
            registryOnly
            libraryId={libraryId}
            disabled={runtimeDisabled}
            title="Логин и пароль registry"
            load={load}
            save={save}
          />
        </>
      )}
    </section>
  );
}
