import { useEffect, useRef, useState } from "react";
import type { HostKeyProbeResult, ServerInformationResult } from "./backend";

export function ServerInformationText({ value }: { value: ServerInformationResult }) {
  const info = value.information;
  if (!info) return <small className="field-error">{value.error?.message}</small>;
  const date = (value: string) => new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Europe/Moscow", day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).format(new Date(value)) + " МСК";
  return <div className="server-information">
    <span>{info.hostname} · {info.os} {info.osVersion} · {info.architecture}</span>
    <span>CPU: {info.cpuCount} · RAM: {(info.memoryBytes / 1024 ** 3).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} ГБ</span>
    <span>Время сервера: {date(info.serverTime)}</span>
    <span>Проверен: {date(info.checkedAt)}</span>
  </div>;
}

export function ServerInformationDialog({ hostId, onProbe, onCheck, onResult, onClose }: {
  hostId: string;
  onProbe: (hostId: string) => Promise<HostKeyProbeResult>;
  onCheck: (probeId: string) => Promise<ServerInformationResult>;
  onResult: (result: ServerInformationResult) => void;
  onClose: () => void;
}) {
  const [probe, setProbe] = useState<HostKeyProbeResult | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const request = useRef<{ hostId: string; probe: typeof onProbe; promise: Promise<HostKeyProbeResult> } | null>(null);
  useEffect(() => {
    let live = true;
    if (!request.current || request.current.hostId !== hostId || request.current.probe !== onProbe) {
      request.current = { hostId, probe: onProbe, promise: onProbe(hostId) };
    }
    void request.current.promise.then((value) => {
      if (!live) return;
      setProbe(value);
      if (value.status !== "APPROVAL_REQUIRED") setError(value.error?.message || "Не удалось получить SSH-отпечаток. Проверьте действующий SSH-сеанс.");
    }).catch(() => live && setError("Не удалось получить SSH-отпечаток.")).finally(() => live && setBusy(false));
    return () => { live = false; };
  }, [hostId, onProbe]);
  const confirm = async () => {
    if (!probe?.probeId) return;
    setBusy(true);
    try {
      const result = await onCheck(probe.probeId);
      onResult(result);
      if (result.status === "CHECKED") onClose();
      else setError(result.error?.message || "Не удалось проверить сервер.");
    } catch { setError("Не удалось проверить сервер."); }
    finally { setBusy(false); }
  };
  return <div className="modal" role="presentation"><section className="card dialog server-dialog" role="dialog" aria-modal="true" aria-labelledby="server-information-title">
    <h1 id="server-information-title">Проверка сервера</h1>
    <p>{probe?.safeLabel || hostId}</p>
    {probe?.status === "APPROVAL_REQUIRED" && <>
      <p>Тип ключа: {probe.keyType}</p><p>Отпечаток: <code>{probe.fingerprint}</code></p>
      <p className="muted">Сверьте отпечаток с независимым доверенным источником. Подтверждённый ключ будет использоваться для проверки сервера и установки.</p>
    </>}
    {error && <p className="field-error" role="alert">{error}</p>}
    {busy && <p role="status">Проверка…</p>}
    <div className="actions"><button className="outline" onClick={onClose} disabled={busy && !!probe}>Отмена</button>
      <button onClick={() => void confirm()} disabled={busy || probe?.status !== "APPROVAL_REQUIRED"}>Подтверждаю совпадение</button>
    </div>
  </section></div>;
}
