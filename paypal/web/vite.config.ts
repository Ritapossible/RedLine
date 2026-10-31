import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The demo vendor's terms pages are RedLine's own examples (../../examples),
// bundled as text, so the preview and the server read the same pages.
export default defineConfig({
  plugins: [react()],
  server: { fs: { allow: ["..", "../.."] } },
  build: { sourcemap: true },
});
