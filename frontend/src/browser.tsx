import { renderApplication } from "./render";
import {
  browserBackend,
  startBrowserActivityKeepAlive,
} from "./browser_backend";

void window.__PI_BROWSER_READY__
  ?.then(() => {
    startBrowserActivityKeepAlive();
    renderApplication(browserBackend);
  })
  .catch(() => undefined);
