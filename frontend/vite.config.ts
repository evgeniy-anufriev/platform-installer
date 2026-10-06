import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig(({ command }) => ({
  build: {
    rollupOptions: {
      input: {
        desktop: resolve(import.meta.dirname, "index.html"),
        browser: resolve(import.meta.dirname, "browser.html"),
      },
    },
  },
  plugins: [
    react(),
    ...(command === "serve"
      ? [
          {
            name: "wails-dev-inline-style-csp",
            transformIndexHtml(html: string) {
              return html.replace(
                "style-src 'self';",
                "style-src 'self' 'unsafe-inline';",
              );
            },
          },
        ]
      : []),
  ],
}));
