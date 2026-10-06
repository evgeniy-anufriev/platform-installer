import { renderApplication } from "./render";
import { backend } from "./backend";
import { qaE4Backend } from "./qa-e4";

const qaE4 =
  import.meta.env.DEV &&
  new URLSearchParams(window.location.search).get("qa") === "e4";
renderApplication(qaE4 ? qaE4Backend : backend);
