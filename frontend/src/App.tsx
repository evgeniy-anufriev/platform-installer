import { useState } from "react";
import type { OpenResult, ProjectBackend } from "./backend";
import { backend } from "./backend";

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
  const destination = parent ? `${parent}${separator}${name.trim()}` : root;
  const open = async () => { setLoading(true); try { setResult(await api.chooseProject()); } finally { setLoading(false); } };
  const chooseParent = async () => { const selected = await api.chooseProjectParent(); if (selected) { setParent(selected); setSeparator("\\"); } };
  const updateDestination = (value: string) => { setParent(""); setRoot(value); };
  const adoptDestinationParent = () => { const index = Math.max(root.lastIndexOf("\\"), root.lastIndexOf("/")); if (index >= 0) { setParent(root.slice(0, index)); setSeparator(root[index]); } };
  const create = async (event: React.FormEvent) => { event.preventDefault(); if (!name.trim()) { setNameRequired(true); return; } setCreating(true); try { const next = await api.createProject({ projectRoot: destination, displayName: name, compatibilitySourceId: "default" }); setResult(next); setDialog(false); if (next.status === "OPEN") { setName(""); setRoot(""); setParent(""); setSeparator("\\"); setNameRequired(false); } } finally { setCreating(false); } };
  const close = async () => setResult(await api.closeProject());
  const snapshot = result.snapshot;
  const local = result.project;
  const project = snapshot?.project as Record<string, unknown> | undefined;
  const empty = result.status === "OPEN" && result.classification === "EMPTY_MANAGED_PROJECT" && local && !snapshot;
  const title = empty ? local.name : project?.name ? String(project.name) : "Проект не открыт";
  return <div className="shell">
    <aside><div className="brand">Platform<br /><span>Installer</span></div><nav>{navigation.map((item, index) => <button key={item} className={index === 0 ? "active" : "future"} disabled={index !== 0}>{item}</button>)}</nav></aside>
    <main><header><div><strong>{title}</strong><span>{result.root || "Выберите существующий проект или создайте новый"}</span></div>{result.status === "OPEN" && <div className="readonly">{empty ? "Не настроен" : "Только чтение"}</div>}<button className="outline" onClick={() => setDialog(true)} disabled={loading || creating}>Создать проект</button><button className="outline" onClick={open} disabled={loading || creating}>Открыть проект</button></header>
      <section className="banner">UI‑01C: создание публикует только metadata-only project.yml. Inventory, переменные, Core и Execution Node не используются.</section>
      {(loading || creating) && <section className="card">{creating ? "Безопасное создание проекта…" : "Открытие проекта…"}</section>}
      {!loading && !creating && result.status === "NO_PROJECT" && <section className="empty card"><h1>Создайте или откройте проект</h1><p>Новый проект содержит только metadata и compatibility locks из verified local bundle.</p><button onClick={() => setDialog(true)}>Создать проект</button><button className="outline" onClick={open}>Открыть папку проекта</button></section>}
      {!loading && !creating && result.status === "ERROR" && <section className="error card"><h1>Проект не открыт</h1><p>{result.error?.message}</p><code>{result.error?.code}</code><button onClick={() => setDialog(true)}>Создать проект</button><button className="outline" onClick={open}>Открыть другой проект</button></section>}
      {!loading && !creating && empty && <><section className="title"><div><h1>Проект ещё не настроен</h1><p>Это корректный metadata-only проект, а не результат проверки Core.</p></div><button className="outline" onClick={close}>Закрыть проект</button></section><section className="grid"><Stat label="Серверы" value={result.counts?.servers ?? 0} /><Stat label="Deployments / Сервисы" value={result.counts?.deployments ?? 0} /><Stat label="Выполнения" value={result.counts?.runs ?? 0} /><Stat label="Inventory" value="Не создан" /></section><section className="card"><h2>Сведения проекта</h2><dl><dt>Название</dt><dd>{local.name}</dd><dt>Путь</dt><dd>{result.root}</dd><dt>Project ID</dt><dd>{local.id}</dd><dt>Compatibility source</dt><dd>{local.source?.bundleDigest}</dd></dl></section><section className="card"><h2>Следующие шаги</h2><p>Добавьте серверы или спроектируйте топологию в следующих milestones. Сохранение, план и выполнение сейчас недоступны.</p></section></>}
      {!loading && !creating && result.status === "OPEN" && snapshot && <><section className="title"><div><h1>{title}</h1><p>Авторитетный снимок Core; локальные файлы не изменялись.</p></div><button className="outline" onClick={close}>Закрыть проект</button></section><section className="grid"><Stat label="Хосты" value={count(snapshot.hosts)} /><Stat label="Развёртывания" value={count(snapshot.serviceDeployments)} /><Stat label="PKI профили" value={count(snapshot.pki)} /><Stat label="Findings" value={snapshot.findings?.length ?? 0} /></section><section className="card"><h2>Состояние проекта</h2><dl><dt>Статус</dt><dd>{snapshot.status}</dd><dt>Revision</dt><dd>{snapshot.projectRevision}</dd><dt>Snapshot fingerprint</dt><dd>{snapshot.snapshotFingerprint}</dd><dt>Документы</dt><dd>{snapshot.documents?.length ?? 0}</dd></dl></section></>}
      {dialog && <div className="modal"><form className="card dialog" onSubmit={create}><h1>Создать проект</h1><label>Название проекта<input maxLength={256} value={name} onChange={event => { setName(event.target.value); setNameRequired(false); }} autoFocus aria-invalid={nameRequired} /></label>{nameRequired && <p className="field-error" role="alert">Заполните «Название проекта»: оно задаёт новую папку проекта.</p>}<label>Новая папка проекта<input required value={destination} onChange={event => updateDestination(event.target.value)} onBlur={adoptDestinationParent} placeholder="C:\\Projects\\production" /></label><div className="actions"><button type="button" className="outline" onClick={chooseParent}>Выбрать parent</button><button type="button" className="outline" onClick={() => setDialog(false)}>Отмена</button><button type="submit" disabled={creating || !destination.trim()}>Создать проект</button></div><p>Название проекта всегда задаёт последнюю папку в пути. Будет создан только <code>project.yml</code>.</p></form></div>}
    </main>
  </div>;
}

function Stat({ label, value }: { label: string; value: number | string }) { return <article className="stat"><span>{label}</span><strong>{value}</strong>{value === 0 && <small>Нет данных</small>}</article>; }
