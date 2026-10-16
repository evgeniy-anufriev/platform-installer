import { useState } from "react";
import { objectValue, type ObjectValue } from "./application-draft";

export type PortSource = { label: string; ports: ObjectValue };
export function ApplicationPorts({
  sources,
  value,
  disabled,
  onSave,
  onDirtyChange,
}: {
  sources: PortSource[];
  value: ObjectValue;
  disabled: boolean;
  onSave: (name: string, port: ObjectValue) => Promise<boolean>;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [host, setHost] = useState("");
  const [container, setContainer] = useState("");
  const [error, setError] = useState("");
  const validPort = (text: string) =>
    text.trim() !== "" &&
    Number.isInteger(Number(text)) &&
    Number(text) >= 1 &&
    Number(text) <= 65535;
  const rows = sources.flatMap((source) =>
    Object.entries(source.ports).map(([id, raw]) => ({
      source: source.label,
      id,
      port: objectValue(raw),
    })),
  );
  const close = () => {
    setAdding(false);
    setName("");
    setHost("");
    setContainer("");
    setError("");
    onDirtyChange(false);
  };
  const open = (id = "", port: ObjectValue = {}) => {
    if (adding && !window.confirm("Отбросить несохранённый ввод порта?"))
      return;
    setAdding(true);
    setName(id);
    setHost(String(port.published ?? ""));
    setContainer(String(port.container ?? ""));
    setError("");
    onDirtyChange(!!id);
  };
  return (
    <section className="application-section application-ports">
      <div className="row">
        <h3>Порты и источники настроек</h3>
        <button disabled={disabled} onClick={() => open()}>
          Добавить порт
        </button>
      </div>
      <p className="muted">
        Значения каждого источника показаны отдельно. Итог для сервера
        рассчитывает Core; последний расчёт может отличаться от черновика.
      </p>
      {rows.length ? (
        <div className="application-port-sources-scroll">
          <table>
            <thead>
              <tr>
                <th>Порт</th>
                <th>Host → Container</th>
                <th>Источник</th>
                <th>Действие</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index}>
                  <td>{row.id}</td>
                  <td>
                    {String(row.port.published ?? "—")} →{" "}
                    {String(row.port.container ?? "—")}
                  </td>
                  <td>{row.source}</td>
                  <td>
                    {!Object.hasOwn(value, row.id) && (
                      <button
                        className="outline"
                        disabled={disabled}
                        onClick={() => open(row.id, row.port)}
                      >
                        Переопределить
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>
          Порты не заданы в доступных настройках. Добавьте порт Host → Container
          или выполните проверку проекта для расчёта Core.
        </p>
      )}
      {adding && (
        <form
          className="application-port-form"
          onChange={() => onDirtyChange(true)}
          onSubmit={async (e) => {
            e.preventDefault();
            if (
              !/^[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)*$/.test(name) ||
              name.length > 128 ||
              Object.hasOwn(value, name)
            ) {
              setError(
                "Укажите уникальное имя порта: латинские строчные буквы, цифры, -, _ или точка.",
              );
              return;
            }
            if (!validPort(host) || !validPort(container)) {
              setError(
                "Host и Container должны быть целыми числами от 1 до 65535.",
              );
              return;
            }
            if (
              await onSave(name, {
                published: Number(host),
                container: Number(container),
              })
            )
              close();
          }}
        >
          <label>
            Имя порта
            <input
              value={name}
              required
              disabled={disabled}
              onChange={(e) => setName(e.target.value)}
              placeholder="http"
            />
          </label>
          <label>
            Host
            <input
              type="number"
              required
              min={1}
              max={65535}
              step={1}
              value={host}
              disabled={disabled}
              onChange={(e) => setHost(e.target.value)}
            />
          </label>
          <span className="application-port-arrow">→</span>
          <label>
            Container
            <input
              type="number"
              required
              min={1}
              max={65535}
              step={1}
              value={container}
              disabled={disabled}
              onChange={(e) => setContainer(e.target.value)}
            />
          </label>
          {error && <p role="alert">{error}</p>}
          <div className="row">
            <button
              disabled={
                disabled || !name || !validPort(host) || !validPort(container)
              }
            >
              В черновик
            </button>
            <button
              type="button"
              className="outline"
              disabled={disabled}
              onClick={close}
            >
              Отмена
            </button>
          </div>
          <small>
            Добавляется явное переопределение экземпляра. Размещение сервера и
            совместимость проверяет Core.
          </small>
        </form>
      )}
    </section>
  );
}
