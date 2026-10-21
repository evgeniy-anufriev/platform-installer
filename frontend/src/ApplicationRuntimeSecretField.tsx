import { useState } from "react";
import type {
  RuntimeSecretDescriptorOperation,
  RuntimeSecretValuesInput,
} from "./backend";

type Session = {
  projectRevision: string;
  contextKey?: string;
  libraryId: string;
  disabled: boolean;
  availability?: RuntimeSecretDescriptorOperation;
  load: () => Promise<RuntimeSecretDescriptorOperation>;
  save: (input: RuntimeSecretValuesInput) => Promise<void>;
};
export type ApplicationSecretSession = Session;

export function ApplicationSecretAvailabilityBadge({
  session,
  sourceRefs,
  resolved,
}: {
  session: Session;
  sourceRefs: string[];
  resolved: boolean;
}) {
  const evidence = session.availability;
  const states = sourceRefs.map((sourceRef) => {
    const matches = evidence?.applicationInputs?.filter(
      (item) =>
        item.purpose === "APPLICATION_SECRET" &&
        item.sourceRef === sourceRef &&
        item.applicationLibraries.includes(session.libraryId),
    );
    return matches?.length === 1
      ? evidence?.applicationSecretAvailability?.[matches[0].requirementRef]
      : undefined;
  });
  const current =
    !session.disabled &&
    resolved &&
    evidence?.status === "READY" &&
    evidence.projectRevision === session.projectRevision;
  const present =
    current && states.length > 0 && states.every((state) => state === true);
  const missing = current && states.some((state) => state === false);
  const unneeded = !session.disabled && resolved && sourceRefs.length === 0;
  return (
    <span
      className={`status-chip status-chip--${present ? "success" : missing ? "warning" : "neutral"}`}
      role="status"
    >
      <span className="status-chip-symbol" aria-hidden="true">
        {present ? "✓" : missing ? "!" : "?"}
      </span>
      {present
        ? "Секрет задан"
        : missing
          ? "Секрет не задан"
          : unneeded
            ? "Сессионный секрет не требуется"
            : "Статус секрета недоступен"}
    </span>
  );
}

export function ApplicationRuntimeSecretField({
  session,
  sourceRef,
  label,
  shared = false,
}: {
  session: Session;
  sourceRef: string;
  label: string;
  shared?: boolean;
}) {
  // A context change must discard unsubmitted values and previous success messages.
  return (
    <RuntimeSecretField
      key={JSON.stringify([
        session.projectRevision,
        session.contextKey,
        session.libraryId,
        session.disabled,
        sourceRef,
        label,
      ])}
      session={session}
      sourceRef={sourceRef}
      label={label}
      shared={shared}
    />
  );
}

function RuntimeSecretField({
  session,
  sourceRef,
  label,
  shared,
}: {
  session: Session;
  sourceRef: string;
  label: string;
  shared: boolean;
}) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const disabled = session.disabled || busy || !sourceRef;
  const submit = async () => {
    if (disabled || !value) return;
    const submitted = value;
    setValue("");
    setMessage("");
    setBusy(true);
    try {
      const operation = await session.load();
      const matches = operation.applicationInputs?.filter(
        (item) =>
          item.purpose === "APPLICATION_SECRET" &&
          item.sourceRef === sourceRef &&
          item.applicationLibraries.includes(session.libraryId),
      );
      if (
        operation.status !== "READY" ||
        operation.projectRevision !== session.projectRevision ||
        !operation.descriptorSetFingerprint ||
        matches?.length !== 1
      )
        throw new Error("RUNTIME_SECRET_DESCRIPTOR_UNAVAILABLE");
      const requirementRef = matches[0].requirementRef;
      await session.save({
        projectRevision: operation.projectRevision,
        descriptorSetFingerprint: operation.descriptorSetFingerprint,
        serviceDeployment: "",
        applicationLibrary: session.libraryId,
        applicationRequirementRef: requirementRef,
        values: { [requirementRef]: submitted },
      });
      setMessage("Секрет отправлен в сессию");
    } catch {
      setMessage(
        "Не удалось сохранить секрет; проверьте актуальность проекта и runtime-сессии",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="application-runtime-secret">
      <div className="application-runtime-secret-entry">
        <label>
          <span className="application-credential-label">{label}</span>
          <input
            type="password"
            aria-label={label}
            autoComplete="new-password"
            placeholder="Введите секрет"
            value={value}
            disabled={disabled}
            onChange={(event) => {
              setValue(event.target.value);
              setMessage("");
            }}
          />
        </label>
        <button
          type="button"
          title="Сохранить в сессии"
          aria-label={`Сохранить в сессии: ${label}`}
          disabled={disabled || !value}
          onClick={() => void submit()}
        >
          ✓
        </button>
        <button
          type="button"
          className="outline"
          title="Очистить ввод"
          aria-label={`Очистить ввод: ${label}`}
          disabled={busy || !value}
          onClick={() => {
            setValue("");
            setMessage("");
          }}
        >
          ×
        </button>
      </div>
      {shared && (
        <small title="Один секрет используется несколькими ресурсами; замена действует на всех потребителей.">
          <span className="application-credential-label">
            Один секрет используется несколькими ресурсами; замена действует на
            всех потребителей.
          </span>
          <span aria-hidden="true">ⓘ</span>
        </small>
      )}
      {message && (
        <small role="status" title={message}>
          <span className="application-credential-label">{message}</span>
          <span aria-hidden="true">ⓘ</span>
        </small>
      )}
    </div>
  );
}
