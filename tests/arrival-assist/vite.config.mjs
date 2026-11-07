import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
const require = createRequire(
  new URL("../../frontend/package.json", import.meta.url),
);
const { defineConfig } = await import(require.resolve("vite"));
const { default: react } = await import(
  require.resolve("@vitejs/plugin-react")
);
export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  envDir: false,
  plugins: [react()],
  resolve: {
    alias: {
      react: fileURLToPath(
        new URL("../../frontend/node_modules/react", import.meta.url),
      ),
      "react-dom": fileURLToPath(
        new URL("../../frontend/node_modules/react-dom", import.meta.url),
      ),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5199,
    strictPort: true,
    fs: { allow: [fileURLToPath(new URL("../..", import.meta.url))] },
  },
});
