// Native offline preview. All identities/providers are synthetic; never uses .env.
import { execFileSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  writeFileSync,
} from "node:fs";
import { createServer } from "node:net";
import { join, resolve } from "node:path";
import { runServices } from "./dev.mjs";

const root = resolve(import.meta.dirname, "..");
const state = join(root, ".artifacts/native-preview");
const data = join(state, "db");
const python = join(root, "backend/.venv/bin/python");
const vite = join(root, "frontend/node_modules/vite/bin/vite.js");
const pgBin = process.env.PG_BIN || "";
const pg = (name) => (pgBin ? join(pgBin, name) : name);
// Explicit allowlist: do not inherit hosted credentials, dotenv, PG* selectors,
// provider keys or options that execute arbitrary Node/Python startup modules.
const env = {
  PATH: process.env.PATH,
  HOME: process.env.HOME,
  TMPDIR: process.env.TMPDIR || "/tmp",
  LANG: "en_US.UTF-8",
  PGPASSWORD: "disposable-guided-only",
  PYTHON_DOTENV_DISABLED: "1",
};
const invoke = (name, args, options = {}) =>
  execFileSync(pg(name), args, {
    cwd: root,
    env,
    encoding: "utf8",
    timeout: 60000,
    ...options,
  });
const sql = (query) =>
  invoke(
    "psql",
    [
      "-X",
      "-h",
      "127.0.0.1",
      "-p",
      "6544",
      "-U",
      "postgres",
      "-d",
      "roadtrips",
      "-v",
      "ON_ERROR_STOP=1",
      "-At",
    ],
    { input: query },
  );
const reservations = [];
let attemptedStart = false;
let runningServices = false;
function stopPostgres() {
  if (!attemptedStart) return;
  try {
    invoke("pg_ctl", ["-D", data, "status"], { stdio: "ignore" });
  } catch {
    return;
  }
  invoke("pg_ctl", ["-D", data, "-m", "fast", "-w", "stop"]);
}
function interruptStartup() {
  if (runningServices) return;
  stopPostgres();
  process.exit(130);
}
process.on("SIGINT", interruptStartup);
process.on("SIGTERM", interruptStartup);
try {
  if (process.platform === "win32")
    throw Error("Use the container journey on Windows.");
  if (!existsSync(python) || !existsSync(vite))
    throw Error(
      "Install backend/.venv and frontend dependencies first (README.md).",
    );
  if (
    readdirSync(root).some(
      (name) =>
        name === ".env" ||
        (name.startsWith(".env.") && name !== ".env.example"),
    )
  )
    throw Error(
      "Use a clean preview checkout without .env; hosted configuration is not accepted.",
    );
  for (const port of [5173, 6544, 8003, 8998, 9010]) {
    const server = createServer();
    await new Promise((accept, reject) => {
      server.once("error", () =>
        reject(
          Error(`Port ${port} is in use; no existing process was stopped.`),
        ),
      );
      server.listen(port, "127.0.0.1", accept);
    });
    reservations.push(server);
  }
  mkdirSync(state, { recursive: true, mode: 0o700 });
  const owner = join(state, "preview-owner");
  if (!existsSync(data)) {
    if (!existsSync(owner))
      writeFileSync(owner, "roadtrips-native-preview-v1\n", {
        flag: "wx",
        mode: 0o600,
      });
    if (readFileSync(owner, "utf8") !== "roadtrips-native-preview-v1\n")
      throw Error("Refusing unowned preview state.");
    const passwordFile = join(state, "synthetic-password");
    if (!existsSync(passwordFile))
      writeFileSync(passwordFile, "disposable-guided-only\n", {
        flag: "wx",
        mode: 0o600,
      });
    invoke("initdb", [
      "-D",
      data,
      "-U",
      "postgres",
      "--auth=scram-sha-256",
      `--pwfile=${passwordFile}`,
      "--encoding=UTF8",
      "--no-locale",
    ]);
  }
  if (
    !existsSync(owner) ||
    readFileSync(owner, "utf8") !== "roadtrips-native-preview-v1\n"
  )
    throw Error("Refusing an unowned PostgreSQL directory.");
  for (const server of reservations)
    await new Promise((done) => server.close(done));
  reservations.length = 0;
  let existingDatabase = false;
  try {
    invoke("pg_ctl", ["-D", data, "status"], { stdio: "ignore" });
    existingDatabase = true;
  } catch (error) {
    if (error.status !== 3) throw error;
  }
  if (existingDatabase)
    throw Error("Preview database is already running; it was not stopped.");
  attemptedStart = true;
  invoke("pg_ctl", [
    "-D",
    data,
    "-l",
    join(state, "postgres.log"),
    "-o",
    "-h 127.0.0.1 -p 6544 -k /tmp",
    "-w",
    "start",
  ]);
  const databases = invoke("psql", [
    "-X",
    "-h",
    "127.0.0.1",
    "-p",
    "6544",
    "-U",
    "postgres",
    "-d",
    "postgres",
    "-Atc",
    "SELECT datname FROM pg_database WHERE datname = 'roadtrips'",
  ]);
  if (!databases.trim()) {
    invoke("createdb", [
      "-h",
      "127.0.0.1",
      "-p",
      "6544",
      "-U",
      "postgres",
      "roadtrips",
    ]);
    sql(
      readFileSync(join(root, "tests/postgres/schema.sql"), "utf8") +
        "\n" +
        readFileSync(join(root, "tests/postgres/catalog-fixture.sql"), "utf8") +
        "\nCREATE TABLE guided_journey_fixture_marker(marker text PRIMARY KEY); INSERT INTO guided_journey_fixture_marker VALUES ('disposable-local-only');",
    );
  }
  if (
    sql("SELECT marker FROM guided_journey_fixture_marker").trim() !==
    "disposable-local-only"
  )
    throw Error("Refusing an unmarked database.");
  console.log(
    "OFFLINE FIXTURE: http://localhost:5173 | traveler@example.test / fixture-only",
  );
  console.log(
    "Synthetic locations, roads, hotels, AI and login; local saved trips persist. Ctrl+C stops only this preview.",
  );
  runningServices = true;
  process.exitCode = await runServices([
    {
      name: "Offline API",
      command: python,
      args: [join(root, "tests/guidedjourney/fixture.py")],
      cwd: root,
      env: {
        ...env,
        GUIDED_JOURNEY_NATIVE_PREVIEW: "true",
        GUIDED_JOURNEY_FIXTURE: "disposable-local-only",
        DATABASE_URL:
          "postgresql://postgres:disposable-guided-only@127.0.0.1:6544/roadtrips",
        DATABASE_SSLMODE: "disable",
      },
    },
    {
      name: "Offline frontend",
      command: process.execPath,
      args: [vite, "--host", "localhost", "--port", "5173", "--strictPort"],
      cwd: join(root, "frontend"),
      env: {
        ...env,
        VITE_BACKEND_SERVER: "http://127.0.0.1:8003/",
        VITE_CLIENT_ID: "localfixture",
        VITE_USERPOOL_ID: "us-west-1_fixture",
        VITE_COGNITO_ENDPOINT: "http://127.0.0.1:8998",
        VITE_MAPBOX_TOKEN: "",
      },
    },
  ]);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
} finally {
  for (const server of reservations) server.close();
  stopPostgres();
  process.off("SIGINT", interruptStartup);
  process.off("SIGTERM", interruptStartup);
}
