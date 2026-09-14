import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { qaE4Backend } from "./qa-e4";
import "./styles.css";

const qaE4 = import.meta.env.DEV && new URLSearchParams(window.location.search).get("qa") === "e4";
createRoot(document.getElementById("root")!).render(<StrictMode><App api={qaE4 ? qaE4Backend : undefined} /></StrictMode>);
