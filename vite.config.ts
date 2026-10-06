import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import tsconfigPaths from "vite-tsconfig-paths";

// Plain client-side SPA: `vite build` emits static files to dist/.
export default defineConfig({
  plugins: [react(), tailwindcss(), tsconfigPaths()],
  build: { outDir: "dist" },
});
