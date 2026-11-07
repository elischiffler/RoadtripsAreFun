// Explicit local fixture only. Never inherits hosted credentials or reads dotenv.
import { execFileSync, spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import {
  constants,
  closeSync,
  existsSync,
  fstatSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  readdirSync,
  realpathSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { createServer } from "node:net";
import { join, resolve } from "node:path";
import { runServices } from "./dev.mjs";

const root = resolve(import.meta.dirname, "..");
const artifacts = join(root, ".artifacts");
const state = join(artifacts, "native-preview");
const data = join(state, "db");
const python = join(root, "backend/.venv/bin/python");
const vite = join(root, "frontend/node_modules/vite/bin/vite.js");
const pgBin = process.env.PG_BIN || "";
const pg = (name) => (pgBin ? join(pgBin, name) : name);
const ownerMarker = "roadtrips-native-preview-v1\n";
const token = randomUUID();
const lockPath = join(state, "launcher.lock");
const env = {
  PATH: process.env.PATH,
  HOME: process.env.HOME,
  TMPDIR: process.env.TMPDIR || "/tmp",
  LANG: "C",
  LC_ALL: "C",
  PGPASSWORD: "disposable-guided-only",
  PYTHON_DOTENV_DISABLED: "1",
};
const reservations = [];
let lock;
let lockIdentity;
let postgres;
let pgLog;
let startedAt;
let unexpectedPostgresExit = false;
let runningServices = false;
let interrupted = false;

function safePath(path, directory = false, privateMode = true) {
  const info = lstatSync(path);
  if (
    info.isSymbolicLink() ||
    !(directory ? info.isDirectory() : info.isFile()) ||
    info.uid !== process.getuid() ||
    info.mode & (privateMode ? 0o077 : 0o022)
  )
    throw Error("Refusing symlinked, unowned or nonprivate preview state.");
  return info;
}
function privateConstant(path, value) {
  if (!existsSync(path))
    writeFileSync(path, value, { flag: "wx", mode: 0o600 });
  const info = safePath(path);
  if (
    info.size !== Buffer.byteLength(value) ||
    readFileSync(path, "utf8") !== value
  )
    throw Error("Refusing unowned preview state.");
}
function invoke(name, args, options = {}) {
  try {
    return execFileSync(pg(name), args, {
      cwd: root,
      env,
      encoding: "utf8",
      timeout: 60000,
      ...options,
    });
  } catch {
    // Never print an inherited command environment or connection credential.
    throw Error(`Local ${name} failed; inspect the isolated preview state.`);
  }
}
const connection = ["-h", "127.0.0.1", "-p", "6544", "-U", "postgres"];
const sql = (query, database = "roadtrips") => {
  if (!ownPostmasterReady(startedAt))
    throw Error("Owned preview database is not ready.");
  // Bind every SQL session to the owned data directory before any DDL. A port
  // race can cause only a read-only refusal, never initialization of another DB.
  return invoke(
    "psql",
    [
      "-X",
      ...connection,
      "-d",
      database,
      "-v",
      "ON_ERROR_STOP=1",
      "-At",
      "-v",
      `preview_data_dir=${realpathSync(data)}`,
    ],
    {
      input:
        "SELECT current_setting('data_directory') = :'preview_data_dir' AS preview_owned \\gset\n\\if :preview_owned\n" +
        query +
        ";\n\\else\nSELECT 1/0;\n\\endif\n",
    },
  );
};
const interruptedCheck = () => {
  if (interrupted) throw Error("Offline preview startup was interrupted.");
};
function interruptStartup() {
  if (!runningServices) interrupted = true;
}
function ownPostmasterReady(startedAt) {
  if (
    !postgres?.pid ||
    postgres.exitCode !== null ||
    postgres.signalCode !== null
  )
    throw Error(
      "Preview PostgreSQL exited before readiness; inspect its local log.",
    );
  const path = join(data, "postmaster.pid");
  if (!existsSync(path)) return false;
  safePath(path);
  const lines = readFileSync(path, "utf8").trim().split("\n");
  if (Number(lines[0]) !== postgres.pid)
    throw Error(
      "Refusing a PostgreSQL process not started by this invocation.",
    );
  return (
    lines[1] === realpathSync(data) &&
    Number(lines[2]) >= startedAt - 2 &&
    Number(lines[3]) === 6544 &&
    lines[7]?.trim() === "ready"
  );
}
async function stopOwnPostgres() {
  if (
    !postgres?.pid ||
    postgres.exitCode !== null ||
    postgres.signalCode !== null
  )
    return;
  // postgres runs in the foreground in a process group spawned here. Never stop
  // a data directory's arbitrary postmaster, and never find a process by port.
  const signal = (kind) => {
    if (postgres.exitCode !== null || postgres.signalCode !== null) return;
    try {
      process.kill(-postgres.pid, kind);
    } catch (error) {
      if (error.code !== "ESRCH") throw error;
    }
  };
  const exited = new Promise((done) => postgres.once("exit", done));
  signal("SIGTERM");
  let timer;
  await Promise.race([
    exited,
    new Promise((done) => {
      timer = setTimeout(done, 10000);
    }),
  ]);
  clearTimeout(timer);
  if (postgres.exitCode === null && postgres.signalCode === null) {
    signal("SIGKILL");
    await exited;
  }
}
process.on("SIGINT", interruptStartup);
process.on("SIGTERM", interruptStartup);
try {
  if (process.platform === "win32")
    throw Error("Use the container journey on Windows.");
  if (process.argv.length > 2)
    throw Error(
      "No launcher arguments are accepted; use PG_BIN for PostgreSQL tools.",
    );
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
      "Use a clean preview checkout without dotenv files; hosted configuration is not accepted.",
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
  if (!existsSync(artifacts)) mkdirSync(artifacts, { mode: 0o700 });
  safePath(artifacts, true, false);
  if (!existsSync(state)) {
    mkdirSync(state, { mode: 0o700 });
    privateConstant(join(state, "preview-owner"), ownerMarker);
  }
  safePath(state, true);
  const owner = join(state, "preview-owner");
  const ownerInfo = safePath(owner);
  if (
    ownerInfo.size !== ownerMarker.length ||
    readFileSync(owner, "utf8") !== ownerMarker
  )
    throw Error("Refusing unowned preview state.");
  try {
    lock = openSync(
      lockPath,
      constants.O_WRONLY |
        constants.O_CREAT |
        constants.O_EXCL |
        constants.O_NOFOLLOW,
      0o600,
    );
  } catch {
    throw Error(
      "Preview lock exists; inspect the isolated state. No existing process was stopped.",
    );
  }
  lockIdentity = fstatSync(lock);
  writeFileSync(lock, token + "\n");
  if (lstatIfPresent(data)) safePath(data, true);
  const key = join(state, "signing-key.pem");
  if (existsSync(key) || lstatIfPresent(key)) safePath(key);
  if (!existsSync(data)) {
    const password = join(state, "synthetic-password");
    privateConstant(password, "disposable-guided-only\n");
    invoke("initdb", [
      "-D",
      data,
      "-U",
      "postgres",
      "--auth=scram-sha-256",
      `--pwfile=${password}`,
      "--encoding=UTF8",
      "--no-locale",
    ]);
  }
  safePath(data, true);
  interruptedCheck();
  for (const server of reservations)
    await new Promise((done) => server.close(done));
  reservations.length = 0;
  interruptedCheck();
  const logPath = join(state, "postgres.log");
  if (existsSync(logPath) || lstatIfPresent(logPath)) safePath(logPath);
  pgLog = openSync(
    logPath,
    constants.O_WRONLY |
      constants.O_CREAT |
      constants.O_APPEND |
      constants.O_NOFOLLOW,
    0o600,
  );
  startedAt = Math.floor(Date.now() / 1000);
  postgres = spawn(
    pg("postgres"),
    ["-D", data, "-h", "127.0.0.1", "-p", "6544", "-k", ""],
    {
      cwd: root,
      env,
      detached: true,
      stdio: ["ignore", pgLog, pgLog],
    },
  );
  let spawnFailure = false;
  postgres.once("error", () => {
    spawnFailure = true;
  });
  postgres.once("exit", () => {
    if (runningServices) {
      unexpectedPostgresExit = true;
      process.emit("SIGTERM");
    }
  });
  const deadline = Date.now() + 30000;
  while (true) {
    interruptedCheck();
    if (spawnFailure)
      throw Error(
        "Local postgres could not start; inspect the isolated state.",
      );
    if (ownPostmasterReady(startedAt)) break;
    if (Date.now() >= deadline)
      throw Error("Owned preview PostgreSQL did not become ready.");
    await new Promise((done) => setTimeout(done, 100));
  }
  if (
    sql("SELECT current_setting('data_directory')", "postgres").trim() !==
    realpathSync(data)
  )
    throw Error(
      "Refusing a database server outside this preview's owned data directory.",
    );
  if (
    !sql(
      "SELECT datname FROM pg_database WHERE datname='roadtrips'",
      "postgres",
    ).trim()
  ) {
    sql("CREATE DATABASE roadtrips", "postgres");
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
  interruptedCheck();
  console.log(
    "OFFLINE FIXTURE: http://127.0.0.1:5173 | test sign-in details: docs/native-offline-preview.md",
  );
  console.log(
    "Synthetic providers and identities only. Local trips persist. Ctrl+C stops this preview.",
  );
  runningServices = true;
  const serviceExit = await runServices([
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
      args: [vite, "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
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
  runningServices = false;
  process.exitCode = unexpectedPostgresExit ? 1 : serviceExit;
} catch (error) {
  console.error(error.message);
  process.exitCode = interrupted ? 130 : 1;
} finally {
  for (const server of reservations) server.close();
  await stopOwnPostgres();
  if (pgLog !== undefined) closeSync(pgLog);
  if (lock !== undefined) {
    const actual = lstatIfPresent(lockPath);
    if (
      actual &&
      actual.ino === lockIdentity.ino &&
      actual.dev === lockIdentity.dev &&
      readFileSync(lockPath, "utf8") === token + "\n"
    )
      unlinkSync(lockPath);
    closeSync(lock);
  }
  process.off("SIGINT", interruptStartup);
  process.off("SIGTERM", interruptStartup);
}
function lstatIfPresent(path) {
  try {
    return lstatSync(path);
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}
