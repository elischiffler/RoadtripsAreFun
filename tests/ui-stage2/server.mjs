// Dedicated loopback presentation fixture. Do not use production .env files.
import { fileURLToPath, pathToFileURL } from "node:url";
import { join } from "node:path";
const root = fileURLToPath(new URL("../../frontend/", import.meta.url));
const { createServer } = await import(
  pathToFileURL(join(root, "node_modules/vite/dist/node/index.js"))
);
const { default: react } = await import(
  pathToFileURL(join(root, "node_modules/@vitejs/plugin-react/dist/index.mjs"))
);
const fixture = {
  VITE_BACKEND_SERVER: "http://127.0.0.1:18999/",
  VITE_MAPBOX_TOKEN: "",
  VITE_COGNITO_ENDPOINT: "http://127.0.0.1:18999/identity",
  VITE_USERPOOL_ID: "us-west-1_fixture",
  VITE_CLIENT_ID: "fixture",
};
const server = await createServer({
  configFile: false,
  root,
  envDir: false,
  envPrefix: "__ROADTRIPS_UI_FIXTURE_ONLY__",
  plugins: [react()],
  define: Object.fromEntries(
    Object.entries(fixture).map(([key, value]) => [
      "import.meta.env." + key,
      JSON.stringify(value),
    ]),
  ),
  server: { host: "127.0.0.1", port: 5187, strictPort: true },
});
await server.listen();
console.log(
  "Presentation fixture ready at http://127.0.0.1:5187 (intercepted API required)",
);
for (const signal of ["SIGINT", "SIGTERM"])
  process.once(signal, async () => {
    await server.close();
    process.exit(0);
  });
