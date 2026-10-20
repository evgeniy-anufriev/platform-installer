import { useRef, useState } from "react";
import type {
  RuntimeSecretDescriptorOperation,
  RuntimeSecretValuesInput,
} from "./backend";

export function ApplicationSecretInputs({
  disabled,
  inline = false,
  load,
  save,
  libraryId,
  title = "Секреты библиотек",
  registryOnly = false,
}: {
  disabled: boolean;
  inline?: boolean;
  libraryId?: string;
  title?: string;
  registryOnly?: boolean;
  load: () => Promise<RuntimeSecretDescriptorOperation>;
  save: (input: RuntimeSecretValuesInput) => Promise<void>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [operation, setOperation] =
    useState<RuntimeSecretDescriptorOperation>();
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const close = () => {
    setValues({});
    setOperation(undefined);
    dialog.current?.close();
  };
  const open = async () => {
    setBusy(true);
    setMessage("");
    try {
      const result = await load();
      if (result.status !== "READY") {
        setMessage(result.error?.message || "Требования к секретам недоступны");
        return;
      }
      const inputs = result.applicationInputs?.filter(
        (item) =>
          (!libraryId || item.applicationLibraries.includes(libraryId)) &&
          item.purpose.startsWith("APPLICATION_REGISTRY_") === registryOnly,
      );
      if (!inputs?.length) {
        setMessage("Секреты библиотек не требуются");
        return;
      }
      setValues({});
      setOperation({ ...result, applicationInputs: inputs });
      if (!inline) dialog.current?.showModal();
    } catch {
      setMessage("Не удалось получить требования к секретам");
    } finally {
      setBusy(false);
    }
  };
  const form = (
    <form
      method="dialog"
      onSubmit={(event) => {
        event.preventDefault();
        if (!operation?.projectRevision || !operation.descriptorSetFingerprint)
          return;
        setBusy(true);
        void save({
          projectRevision: operation.projectRevision,
          descriptorSetFingerprint: operation.descriptorSetFingerprint,
          serviceDeployment: "",
          ...(libraryId ? { applicationLibrary: libraryId } : {}),
          values,
        })
          .then(() => {
            close();
            setMessage("Секреты сохранены только в сессии");
          })
          .catch(() => {
            setValues({});
            setMessage(
              "Не удалось сохранить секреты; проверьте актуальность проекта и сессии",
            );
          })
          .finally(() => setBusy(false));
      }}
    >
      <h2>{title}</h2>
      <p className="muted">
        {registryOnly
          ? "Логин и пароль остаются только в runtime-сессии и применяются на целевых серверах."
          : "Значения остаются только в памяти и передаются через runtime lease для одобренного плана."}
      </p>
      {operation?.applicationInputs?.map((item) => (
        <label key={item.requirementRef}>
          <span>{item.displayLabel}</span>
          {inline && (
            <small>
              Источник: {item.sourceRef} ·{" "}
              {registryOnly
                ? "Registry"
                : (item.providerDeployment ?? "Приложение")}
            </small>
          )}
          <input
            aria-label={item.displayLabel}
            type={
              item.purpose === "APPLICATION_REGISTRY_USERNAME"
                ? "text"
                : "password"
            }
            autoComplete="new-password"
            required
            disabled={disabled || busy}
            value={values[item.requirementRef] || ""}
            onChange={(event) =>
              setValues((current) => ({
                ...current,
                [item.requirementRef]: event.target.value,
              }))
            }
          />
        </label>
      ))}
      <button type="button" disabled={busy} onClick={close}>
        Отмена
      </button>
      <button type="submit" disabled={disabled || busy}>
        Сохранить в сессии
      </button>
    </form>
  );
  return (
    <section className="card">
      <button
        type="button"
        disabled={disabled || busy}
        onClick={() => void open()}
      >
        {title}
      </button>
      {message && <p role="status">{message}</p>}
      {inline ? (
        operation && <div className="application-inline-secrets">{form}</div>
      ) : (
        <dialog
          ref={dialog}
          className="runtime-secret-dialog"
          aria-label={title}
          onCancel={(event) => {
            event.preventDefault();
            close();
          }}
        >
          {form}{" "}
        </dialog>
      )}
    </section>
  );
}
