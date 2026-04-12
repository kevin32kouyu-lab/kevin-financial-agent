import { defineConfig } from "vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: path.resolve(__dirname, "web"),
  server: {
    host: "127.0.0.1",
    port: 5173
  },
  build: {
    outDir: path.resolve(__dirname, "web", "dist"),
    emptyOutDir: true
  }
});
