import { useState } from "react";
import type { EditResult, OpenResult, ProjectBackend } from "./backend";
import { backend } from "./backend";
import "./edit.css";

const navigation = ["Проект", "Серверы", "Топология", "Сертификаты", "Сервисы", "Установка", "Логи", "Справка", "О программе", "Настройки"];
function count(value: unknown): number { return value && typeof value === "object" ? Object.keys(value).length : 0; }

export function App({ api = backend }: { api?: ProjectBackend }) {
  const [result, setResult] = useState<OpenResult>({ status: "NO_PROJECT" } as OpenResult);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [dialog, setDialog] = useState(false);
  const [name, setName] = useState("");
  const [root, setRoot] = useState("");
  const [parent, setParent] = useState("");
  const [separator, setSeparator] = useState("\\");
  const [nameRequired, setNameRequired] = useState(false);
  const [edit, setEdit] = useState<EditResult | null>(null);
  const [editError, setEditError] = useState<EditResult["error"] | null>(null);
  const [editBusy, setEditBusy] = useState(false);
  const [hostId, setHostId] = useState("node1");
  const [address, setAddress] = useState("");
  const [sshPort, setSSHPort] = useState("22");
  const [sessionId, setSessionId] = useState("");
  const destination = parent ? `${parent}${separator}${name.trim()}` : root;

  const open = async () => { setLoading(true); try { setResult(await api.chooseProject()); } finally { setLoading(false); } };
  const chooseParent = async () => { const selected = await api.chooseProjectParent(); if (selected) { setParent(selected); setSeparator("\\"); } };
  const updateDestination = (value: string) => { setParent(""); setRoot(value); };
  const adoptDestinationParent = () => { const index = Math.max(root.lastIndexOf("\\"), root.lastIndexOf("/")); if (index >= 0) { setParent(root.slice(0, index)); setSeparator(root[index]); } };
  const create = async (event: React.FormEvent) => { event.preventDefault(); if (!name.trim()) { setNameRequired(true); return; } setCreating(true); try { const next = await api.createProject({ projectRoot: destination, displayName: name, compatibilitySourceId: "default" }); setResult(next); setDialog(false); if (next.status === "OPEN") { setName(""); setRoot(""); setParent(""); setSeparator("\\"); setNameRequired(false); } } finally { setCreating(false); } };
  const close = async () => setResult(await api.closeProject());
  const startEdit = async () => { setEditBusy(true); try { const next = await api.startEditSession(); setEdit(next); setEditError(next.error || null); setSessionId(next.session?.sessionId || ""); } finally { setEditBusy(false); } };
  const addFirstServer = async (event: React.FormEvent) => { event.preventDefault(); if (!sessionId) return; setEditBusy(true); try { const next = await api.appendEditCommand(sessionId, { operation: "CreateServer", hostId, address, sshPort: Number(sshPort) }); setEdit(next); setEditError(next.error || null); } finally { setEditBusy(false); } };
  const review = async () => { if (!sessionId) return; setEditBusy(true); try { const next = await api.reviewEditSession(sessionId); const finding = next.plan?.validation?.findings?.[0]; if (next.error) setEditError(next.error); else if (next.plan?.status === "BLOCKED") setEditError({ code: finding?.code || "CORE_VALIDATION_BLOCKED", message: finding?.safeMessage || "Проверка изменений заблокирована." }); else { setEdit(next); setEditError(null); } } finally { setEditBusy(false); } };
  const save = async () => { const planId = edit?.plan?.planId; if (!sessionId || !planId) return; setEditBusy(true); try { const next = await api.commitEditPlan(sessionId, planId); const finding = next.commit?.finding; if (next.error) { setEditError(next.error); return; } if (next.commit && next.commit.status !== "COMMITTED" && next.commit.status !== "COMMITTED_REFRESH_FAILED") { setEditError({ code: finding?.code || "WRITE_FAILED", message: finding?.safeMessage || "Сохранение изменений заблокировано." }); return; } setEdit(next); setEditError(null); if (next.commit?.snapshot) setResult(current => ({ ...current, classification: "MANAGED_PROJECT", snapshot: next.commit?.snapshot as OpenResult["snapshot"] } as OpenResult)); if (next.status.startsWith("COMMITTED")) setSessionId(""); } finally { setEditBusy(false); } };
  const discard = async () => { if (!sessionId) return; setEditBusy(true); try { await api.discardEditSession(sessionId); setEdit(null); setEditError(null); setSessionId(""); } finally { setEditBusy(false); } };

  const snapshot = result.snapshot;
  const local = result.project;
  const project = snapshot?.project as Record<string, unknown> | undefined;
  const empty = result.status === "OPEN" && result.classification === "EMPTY_MANAGED_PROJECT" && local && !snapshot;
  const title = empty ? local.name : project?.name ? String(project.name) : "Проект не открыт";
  return <div className="shell">
    <aside><div className="brand">Platform<br /><span>Installer</span></div><nav>{navigation.map((item, index) => <button key={item} className={index === 0 ? "active" : "future"} disabled={index !== 0}>{item}</button>)}</nav></aside>
    <main><header><div><strong>{title}</strong><span>{result.root || "Выберите существующий проект или создайте новый"}</span></div>{sessionId && <div className="unsaved">Есть несохранённые изменения</div>}{result.status === "OPEN" && !sessionId && <div className="readonly">{empty ? "Не настроен" : "Проверено Core"}</div>}<button className="outline" onClick={() => setDialog(true)} disabled={loading || creating || !!sessionId}>Создать проект</button><button className="outline" onClick={open} disabled={loading || creating || !!sessionId}>Открыть проект</button></header>
      <section className="banner">UI‑01D: изменения остаются в transient session до проверки полного candidate на READY Execution Node и явного сохранения.</section>
      {sessionId && <section className="banner"><code>ACTIVE_EXECUTION_STATE_UNKNOWN</code> Состояние выполнения UNKNOWN: если выполнение существует, оно использует immutable предыдущую revision.</section>}
      {(loading || creating) && <section className="card">{creating ? "Безопасное создание проекта…" : "Открытие проекта…"}</section>}
      {!loading && !creating && result.status === "NO_PROJECT" && <section className="empty card"><h1>Создайте или откройте проект</h1><p>Новый проект содержит только metadata и compatibility locks из verified local bundle.</p><button onClick={() => setDialog(true)}>Создать проект</button><button className="outline" onClick={open}>Открыть папку проекта</button></section>}
      {!loading && !creating && result.status === "ERROR" && <section className="error card"><h1>Проект не открыт</h1><p>{result.error?.message}</p><code>{result.error?.code}</code><button onClick={() => setDialog(true)}>Создать проект</button><button className="outline" onClick={open}>Открыть другой проект</button></section>}
      {!loading && !creating && empty && <><section className="title"><div><h1>Проект ещё не настроен</h1><p>Это корректный metadata-only проект. Первое сохранение создаст полный минимальный Ansible project.</p></div><button className="outline" onClick={close} disabled={!!sessionId}>Закрыть проект</button></section><section className="grid"><Stat label="Серверы" value={result.counts?.servers ?? 0} /><Stat label="Deployments / Сервисы" value={result.counts?.deployments ?? 0} /><Stat label="Выполнения" value={result.counts?.runs ?? 0} /><Stat label="Inventory" value="Не создан" /></section><section className="card"><h2>Сведения проекта</h2><dl><dt>Название</dt><dd>{local.name}</dd><dt>Путь</dt><dd>{result.root}</dd><dt>Project ID</dt><dd>{local.id}</dd><dt>Compatibility source</dt><dd>{local.source?.bundleDigest}</dd></dl></section><FirstSave edit={edit} error={editError} busy={editBusy} sessionId={sessionId} hostId={hostId} address={address} sshPort={sshPort} onStart={startEdit} onSubmit={addFirstServer} onHost={setHostId} onAddress={setAddress} onPort={setSSHPort} onReview={review} onSave={save} onDiscard={discard} /></>}
      {!loading && !creating && result.status === "OPEN" && snapshot && <><section className="title"><div><h1>{title}</h1><p>Авторитетный снимок Core.</p></div><button className="outline" onClick={close}>Закрыть проект</button></section><section className="grid"><Stat label="Хосты" value={count(snapshot.hosts)} /><Stat label="Развёртывания" value={count(snapshot.serviceDeployments)} /><Stat label="PKI профили" value={count(snapshot.pki)} /><Stat label="Findings" value={snapshot.findings?.length ?? 0} /></section><section className="card"><h2>Состояние проекта</h2><dl><dt>Статус</dt><dd>{snapshot.status}</dd><dt>Revision</dt><dd>{snapshot.projectRevision}</dd><dt>Snapshot fingerprint</dt><dd>{snapshot.snapshotFingerprint}</dd><dt>Документы</dt><dd>{snapshot.documents?.length ?? 0}</dd></dl></section></>}
      {dialog && <div className="modal"><form className="card dialog" onSubmit={create}><h1>Создать проект</h1><label>Название проекта<input maxLength={256} value={name} onChange={event => { setName(event.target.value); setNameRequired(false); }} autoFocus aria-invalid={nameRequired} /></label>{nameRequired && <p className="field-error" role="alert">Заполните «Название проекта»: оно задаёт новую папку проекта.</p>}<label>Новая папка проекта<input required value={destination} onChange={event => updateDestination(event.target.value)} onBlur={adoptDestinationParent} placeholder="C:\\Projects\\production" /></label><div className="actions"><button type="button" className="outline" onClick={chooseParent}>Выбрать parent</button><button type="button" className="outline" onClick={() => setDialog(false)}>Отмена</button><button type="submit" disabled={creating || !destination.trim()}>Создать проект</button></div><p>Название проекта всегда задаёт последнюю папку в пути. Будет создан только <code>project.yml</code>.</p></form></div>}
    </main>
  </div>;
}

interface FirstSaveProps {
  edit: EditResult | null;
  error: EditResult["error"] | null;
  busy: boolean;
  sessionId: string;
  hostId: string;
  address: string;
  sshPort: string;
  onStart: () => void;
  onSubmit: (event: React.FormEvent) => void;
  onHost: (value: string) => void;
  onAddress: (value: string) => void;
  onPort: (value: string) => void;
  onReview: () => void;
  onSave: () => void;
  onDiscard: () => void;
}

function FirstSave({ edit, error, busy, sessionId, hostId, address, sshPort, onStart, onSubmit, onHost, onAddress, onPort, onReview, onSave, onDiscard }: FirstSaveProps) {
  const commandCount = edit?.session?.commandCount ?? 0;
  if (edit?.commit && (edit.commit.status === "COMMITTED" || edit.commit.status === "COMMITTED_REFRESH_FAILED")) return <section className="card"><h2>Изменения сохранены</h2><p>Статус: {edit.commit.status}. Canonical project revision обновлён.</p></section>;
  if (!sessionId) return <section className="card"><h2>Первое сохранение</h2><p>До проверки и кнопки «Сохранить» файлы проекта не изменятся.</p><button onClick={onStart} disabled={busy}>Начать редактирование</button></section>;
  if (error) return <section className="error card"><h2>Изменения заблокированы</h2><p>{error.message}</p><code>{error.code}</code><div className="actions"><button className="outline" onClick={onDiscard}>Отменить изменения</button><button onClick={onReview} disabled={busy}>Повторить проверку</button>{edit?.plan?.planId && <button onClick={onSave} disabled={busy}>Повторить сохранение</button>}</div></section>;
  if (edit?.plan) return <section className="card review"><h2>План изменений</h2><p>Core: {edit.plan.validation?.status}. Документов: {edit.plan.affectedDocuments?.length ?? 0}.</p><ul>{edit.plan.semanticChanges?.map((change, index) => <li key={index}>{change.safeSummary}</li>)}</ul><ul>{edit.plan.affectedDocuments?.map((change) => <li key={change.logicalPath}>{change.logicalPath}: {change.before?.state} → {change.after?.state}</li>)}</ul><div className="actions"><button className="outline" onClick={onDiscard}>Отменить изменения</button><button onClick={onSave} disabled={busy || !edit.plan.commitAllowed}>Сохранить</button></div></section>;
  if (commandCount > 0) return <section className="card review"><h2>Черновик готов к проверке</h2><p>Команд: {commandCount}. Core проверит полный candidate на выбранном Execution Node.</p><div className="actions"><button className="outline" onClick={onDiscard}>Отменить изменения</button><button onClick={onReview} disabled={busy}>Проверить изменения</button></div></section>;
  return <form className="card first-server" onSubmit={onSubmit}><h2>Первый сервер</h2><p>Узкий bootstrap-сценарий UI‑01D; полный редактор серверов относится к UI‑01E.</p><label>ID сервера<input value={hostId} onChange={(event) => onHost(event.target.value)} required /></label><label>Адрес<input value={address} onChange={(event) => onAddress(event.target.value)} placeholder="192.0.2.10" required /></label><label>SSH port<input type="number" min="1" max="65535" value={sshPort} onChange={(event) => onPort(event.target.value)} required /></label><div className="actions"><button type="button" className="outline" onClick={onDiscard}>Отменить изменения</button><button type="submit" disabled={busy}>Добавить в черновик</button></div></form>;
}

function Stat({ label, value }: { label: string; value: number | string }) { return <article className="stat"><span>{label}</span><strong>{value}</strong>{value === 0 && <small>Нет данных</small>}</article>; }
