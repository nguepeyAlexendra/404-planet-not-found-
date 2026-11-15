/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: { rollupOptions: { output: { manualChunks: { maplibre: ["maplibre-gl"], charts: ["recharts"], vendor: ["react", "react-dom", "react-router-dom"] } } }, chunkSizeWarningLimit: 1100 },
  server: { port: 5173, proxy: { "/api": process.env.VITE_API_PROXY ?? "http://localhost:8000" } },
  test: { environment: "jsdom", setupFiles: ["./tests/setup.ts"], globals: true, css: false, exclude: ["e2e/**", "node_modules/**"] },
});
