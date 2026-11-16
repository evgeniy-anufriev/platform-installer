import { useEffect, useState } from "react";
import type {
  OpenResult,
  ProjectBackend,
  RuntimeSecretStatuses,
} from "./backend";

export function useRuntimeSecretStatuses(
  load: ProjectBackend["getRuntimeSecretStatuses"],
  section: "services" | "applications",
  managed: OpenResult["managed"],
  refreshVersion: number,
  contextKey = "",
) {
  const [result, setResult] = useState<{
    managed: OpenResult["managed"];
    contextKey: string;
    statuses: RuntimeSecretStatuses;
  }>();
  useEffect(() => {
    if (!load || !managed) return;
    let active = true;
    let pending = false;
    const refresh = async () => {
      if (!active || pending) return;
      pending = true;
      try {
        const statuses = await load(section);
        if (active)
          setResult(
            statuses.projectRevision === managed.projectRevision
              ? { managed, contextKey, statuses }
              : undefined,
          );
      } catch {
        if (active) setResult(undefined);
      } finally {
        pending = false;
      }
    };
    void refresh();
    const timer = window.setInterval(refresh, 30_000);
    window.addEventListener("focus", refresh);
    return () => {
      active = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, [load, section, managed, refreshVersion, contextKey]);
  return load &&
    result?.managed === managed &&
    result?.contextKey === contextKey
    ? result.statuses
    : undefined;
}

export function RuntimeSecretStatus({
  present,
  compact = false,
}: {
  present?: boolean;
  compact?: boolean;
}) {
  if (typeof present !== "boolean") return null;
  const label = present ? "Секреты заданы" : "Секреты не заданы";
  return (
    <small
      className={`status-chip status-chip--${present ? "success" : "warning"}${compact ? " list-secret-status" : ""}`}
      title={compact ? label : undefined}
    >
      {compact ? (
        <>
          <span aria-hidden="true">{present ? "✓" : "!"}</span>
          <span className="visually-hidden">{label}</span>
        </>
      ) : (
        label
      )}
    </small>
  );
}
