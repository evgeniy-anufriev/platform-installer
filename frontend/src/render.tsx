import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import type { ProjectBackend } from "./backend";
import "./styles.css";
import "./production-ui.css";

export function renderApplication(api: ProjectBackend) {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App api={api} />
    </StrictMode>,
  );
}
