import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const directory = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = join(directory, "../..");
const composeFile = join(directory, "compose.yaml");
const runId = process.env.DB_TEST_RUN_ID || randomBytes(5).toString("hex");
if (!/^[a-z0-9]{1,20}$/.test(runId)) {
  throw new Error("DB_TEST_RUN_ID must be 1-20 lowercase letters or digits");
}
const project = `roadtrips-crud-${runId}`;
const git = (args) =>
  execFileSync("git", args, { cwd: repositoryRoot, encoding: "utf8" }).trim();
const cleanCheckout = git(["status", "--porcelain"]) === "";
const revision = cleanCheckout ? git(["rev-parse", "HEAD"]) : "local-crud-test";
const environment = { ...process.env, DB_TEST_RUN_ID: runId, ROADTRIPS_REVISION: revision };
const compose = ["compose", "-f", composeFile, "-p", project];
const restoreUrl =
  "postgresql://postgres:disposable-local-only@restore/roadtrips";
const objectsQuery =
  "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace " +
  "WHERE n.nspname NOT IN ('pg_catalog','information_schema') " +
  "AND n.nspname NOT LIKE 'pg_toast%' AND c.relkind IN ('r','p','v','m','S','f');";

function assertSchemaMatchesSources() {
  const readme = readFileSync(join(repositoryRoot, "README.md"), "utf8");
  const memory = readFileSync(join(repositoryRoot, "backend/app/crud/memory_crud.py"), "utf8");
  const schema = readFileSync(join(directory, "schema.sql"), "utf8");
  const readmeDdl = /## Database Schema[\s\S]*?```sql\s*([\s\S]*?)```/.exec(readme)?.[1];
  const memoryDdl = /_CREATE_TABLE_SQL = """([\s\S]*?)"""/.exec(memory)?.[1];
  if (!readmeDdl || !memoryDdl) throw new Error("Authoritative schema source missing");
  const canonical = (value) =>
    value.replace(/--[^\n]*/g, "").replace(/[\s;]/g, "").toLowerCase();
  if (canonical(schema) !== canonical(`${readmeDdl}\n${memoryDdl}`)) {
    throw new Error("Disposable schema drifted from README or memory_crud DDL");
  }
  console.log("Schema matches checked-in README and memory CRUD DDL");
}

function docker(args, options = {}) {
  return execFileSync("docker", [...compose, ...args], {
    env: environment,
    encoding: options.encoding === "buffer" ? null : (options.encoding ?? "utf8"),
    input: options.input,
    maxBuffer: 64 * 1024 * 1024,
    timeout: options.timeout ?? 120_000,
    stdio: options.stdio ?? ["pipe", "pipe", "inherit"],
  });
}

function probe(phase, service = "postgres") {
  console.log(`Real CRUD ${phase} against ${service}`);
  docker(
    [
      "run",
      "--rm",
      "--no-deps",
      "-e",
      `DB_TEST_RUN_ID=${runId}`,
      "-e",
      `DATABASE_URL=${service === "restore" ? restoreUrl : "postgresql://postgres:disposable-local-only@postgres/roadtrips"}`,
      "test",
      "python",
      "tests/db_integration_probe.py",
      phase,
    ],
    { stdio: "inherit", timeout: 120_000 },
  );
}

function assertApiReady() {
  const result = docker([
    "exec",
    "-T",
    "api",
    "python",
    "-c",
    "import json,urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=10)); assert data == {'status':'ready'}, data",
  ]);
  console.log(`API /ready: ${result.trim() || "200 ready"}`);
}

function assertApiDependencyFailure() {
  docker([
    "exec",
    "-T",
    "api",
    "python",
    "-c",
    "import urllib.error,urllib.request\ntry:\n urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=10)\n raise AssertionError('database loss did not fail readiness')\nexcept urllib.error.HTTPError as error:\n assert error.code == 503, error.code",
  ]);
  console.log("API /ready: expected 503 during database loss");
}

function objectCount(service) {
  return Number(
    docker([
      "exec",
      "-T",
      service,
      "psql",
      "-U",
      "postgres",
      "-d",
      "roadtrips",
      "-Atc",
      objectsQuery,
    ]).trim(),
  );
}

function restoreOnlyIfEmpty(archive) {
  // Same object inventory/refusal check and pg_restore safety flags as the
  // hosting-ops postgres/restore.sh runbook, scoped to this disposable stack.
  const count = objectCount("restore");
  if (!Number.isInteger(count) || count !== 0) {
    throw new Error(`Restore refused: target has ${count} application objects`);
  }
  docker(
    [
      "exec",
      "-T",
      "restore",
      "pg_restore",
      "-U",
      "postgres",
      "-d",
      "roadtrips",
      "--no-owner",
      "--no-privileges",
      "--single-transaction",
      "--exit-on-error",
    ],
    { input: archive, timeout: 120_000 },
  );
}

assertSchemaMatchesSources();
if (process.argv.includes("--check-schema")) process.exit(0);

let sourceStarted = false;
let restoreStarted = false;
let apiStarted = false;
try {
  console.log(`Project ${project}: build isolated Python test and API images (${revision})`);
  docker(["build", "test", "api"], { stdio: "inherit", timeout: 600_000 });
  docker(["up", "-d", "--wait", "--wait-timeout", "60", "postgres"]);
  sourceStarted = true;
  probe("seed");

  docker(["--profile", "api", "up", "-d", "--wait", "--wait-timeout", "60", "api"]);
  apiStarted = true;
  assertApiReady();
  docker(["--profile", "api", "up", "-d", "--wait", "--wait-timeout", "60", "--force-recreate", "--no-deps", "api"]);
  assertApiReady();

  docker(["stop", "postgres"]);
  assertApiDependencyFailure();
  docker([
    "up",
    "-d",
    "--wait",
    "--wait-timeout",
    "60",
    "--force-recreate",
    "postgres",
  ]);
  probe("verify");
  assertApiReady();
  console.log("Source volume survived container recreation");

  // Match hosting-ops backup.sh: custom-format dump, private output, no overwrite.
  const archive = docker(
    ["exec", "-T", "postgres", "pg_dump", "-U", "postgres", "-d", "roadtrips", "-Fc"],
    { encoding: "buffer" },
  );
  if (archive.length === 0) throw new Error("Empty PostgreSQL backup");
  const backupDirectory = join(directory, ".artifacts");
  mkdirSync(backupDirectory, { recursive: true, mode: 0o700 });
  const backupPath = join(backupDirectory, `${project}.dump`);
  writeFileSync(backupPath, archive, { flag: "wx", mode: 0o600 });
  console.log(`Private backup: ${backupPath} (${archive.length} bytes)`);

  docker(["--profile", "api", "stop", "api", "postgres"]);
  docker(["--profile", "restore", "up", "-d", "--wait", "--wait-timeout", "60", "restore"]);
  restoreStarted = true;
  restoreOnlyIfEmpty(archive);
  probe("verify", "restore");
  let refused = false;
  try {
    restoreOnlyIfEmpty(archive);
  } catch (error) {
    if (!String(error.message).startsWith("Restore refused:")) throw error;
    refused = true;
    console.log(error.message);
  }
  if (!refused) throw new Error("Populated-target restore was not refused");
  probe("verify", "restore");

  console.log(`PASS: source and restore volumes preserved (${project}_source-data, ${project}_restore-data)`);
} finally {
  if (sourceStarted || restoreStarted || apiStarted) {
    try {
      docker(["--profile", "restore", "--profile", "api", "stop", "api", "postgres", "restore"], { timeout: 60_000 });
    } catch (error) {
      console.error(`Could not stop disposable database containers: ${error.message}`);
    }
  }
}
