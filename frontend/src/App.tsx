import { useState } from "react";
import type { OpenResult, ProjectBackend } from "./backend";
import { backend } from "./backend";

const navigation = ["Проект", "Серверы", "Топология", "Сертификаты", "Сервисы", "Установка", "Логи", "Справка", "О программе", "Настройки"];

function count(value: unknown): number { return value && typeof value === "object" ? Object.keys(value).length : 0; }

export function App({ api = backend }: { api?: ProjectBackend }) {
  const [result, setResult] = useState<OpenResult>({ status: "NO_PROJECT" } as OpenResult);
  const [loading, setLoading] = useState(false);
  const open = async () => { setLoading(true); try { setResult(await api.chooseProject()); } finally { setLoading(false); } };
  const close = async () => setResult(await api.closeProject());
  const snapshot = result.snapshot;
  const project = snapshot?.project as Record<string, unknown> | undefined;
  return <div className="shell">
    <aside><div className="brand">Platform<br /><span>Installer</span></div><nav>{navigation.map((item, index) => <button key={item} className={index === 0 ? "active" : "future"} disabled={index !== 0}>{item}</button>)}</nav></aside>
    <main><header><div><strong>{project?.name ? String(project.name) : "Проект не открыт"}</strong><span>{result.root || "Выберите существующий проект"}</span></div><div className="readonly">Только чтение</div><button className="outline" onClick={open} disabled={loading}>Открыть проект</button></header>
      <section className="banner">Режим UI‑01B: доступно только read-only открытие через READY Execution Node. Редактирование и сохранение появятся в UI‑01D.</section>
      {loading && <section className="card">Получение авторитетного ProjectSnapshot…</section>}
      {!loading && result.status === "NO_PROJECT" && <section className="empty card"><h1>Откройте существующий проект</h1><p>Приложение не создаёт файлы и не запускает локальный Ansible.</p><button onClick={open}>Открыть папку проекта</button></section>}
      {!loading && result.status === "ERROR" && <section className="error card"><h1>Проект не открыт</h1><p>{result.error?.message}</p><code>{result.error?.code}</code><button onClick={open}>Повторить</button></section>}
      {!loading && result.status === "OPEN" && snapshot && <>
        <section className="title"><div><h1>{project?.name ? String(project.name) : "Проект"}</h1><p>Авторитетный снимок Core; локальные файлы не изменялись.</p></div><button className="outline" onClick={close}>Закрыть проект</button></section>
        <section className="grid"><Stat label="Хосты" value={count(snapshot.hosts)} /><Stat label="Развёртывания" value={count(snapshot.serviceDeployments)} /><Stat label="PKI профили" value={count(snapshot.pki)} /><Stat label="Findings" value={snapshot.findings?.length ?? 0} /></section>
        <section className="card"><h2>Состояние проекта</h2><dl><dt>Статус</dt><dd>{snapshot.status}</dd><dt>Revision</dt><dd>{snapshot.projectRevision}</dd><dt>Snapshot fingerprint</dt><dd>{snapshot.snapshotFingerprint}</dd><dt>Документы</dt><dd>{snapshot.documents?.length ?? 0}</dd></dl></section>
        <section className="card"><h2>Следующие разделы</h2><p>Серверы, Топология, Сертификаты и Сервисы пока показываются только в навигации: редактирование, план и выполнение не выполняются.</p></section>
      </>}
    </main>
  </div>;
}

function Stat({ label, value }: { label: string; value: number }) { return <article className="stat"><span>{label}</span><strong>{value}</strong>{value === 0 && <small>Нет данных</small>}</article>; }
