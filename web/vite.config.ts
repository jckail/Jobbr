import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served at https://jckail.com/jobbr/
export default defineConfig({
  base: "/jobbr/",
  plugins: [react()],
  server: { proxy: { "/jobbr/api": "http://localhost:8000" } },
});
