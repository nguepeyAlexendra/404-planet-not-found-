import { defineConfig } from "@playwright/test";

// Prérequis : l'API (port 8000) et le front (port 5173) tournent, la base contient la démonstration (python -m app.cli seed-demo).
// CHROMIUM_PATH permet d'utiliser un Chromium déjà installé.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    launchOptions: process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH, args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"] } : { args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"] },
    viewport: { width: 1280, height: 800 },
  },
});
