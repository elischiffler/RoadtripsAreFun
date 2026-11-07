import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dirname, "../..");
const project = "roadtrips-guided-" + randomBytes(5).toString("hex");
const artifacts = join(import.meta.dirname, ".artifacts");
mkdirSync(artifacts, { recursive: true });
const revision = process.env.ROADTRIPS_REVISION;
if (!/^[a-f0-9]{40}$/.test(revision || ""))
  throw Error("Set ROADTRIPS_REVISION to the exact tested commit");
const actualRevision = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: root,
  encoding: "utf8",
}).trim();
const dirty = execFileSync("git", ["status", "--porcelain"], {
  cwd: root,
  encoding: "utf8",
}).trim();
if (revision !== actualRevision || dirty)
  throw Error(
    "The release gate requires a clean checkout of its exact revision",
  );
const dockerEnv = { ...process.env };
for (const selector of [
  "DOCKER_HOST",
  "DOCKER_CONTEXT",
  "DOCKER_TLS",
  "DOCKER_TLS_VERIFY",
  "DOCKER_CERT_PATH",
])
  delete dockerEnv[selector];
const invoke = (args, options = {}) =>
  execFileSync("docker", ["--host=unix:///var/run/docker.sock", ...args], {
    cwd: root,
    env: dockerEnv,
    timeout: 240000,
    ...options,
  });
const docker = (args) => invoke(args, { stdio: "inherit" });
const compose = [
  "compose",
  "--env-file",
  "/dev/null",
  "-f",
  "tests/guidedjourney/compose.yaml",
  "-p",
  project,
];
const preview = [
  "compose",
  "--env-file",
  "/dev/null",
  "-f",
  "compose.yaml",
  "-p",
  "roadtrips-local",
];
const inspect = (image) =>
  JSON.parse(invoke(["image", "inspect", image], { encoding: "utf8" }))[0];
const testImage = inspect("roadtrips-tests-local");
for (const image of [
  "roadtrips-tests-local",
  `roadtrips-web-local:${revision}`,
]) {
  if (
    inspect(image).Config.Labels?.["org.opencontainers.image.revision"] !==
    revision
  )
    throw Error(`Journey image revision mismatch: ${image}`);
}
for (const service of ["web", "api"]) {
  const id = invoke([...preview, "ps", "--all", "-q", service], {
    encoding: "utf8",
  }).trim();
  if (!id || id.includes("\n"))
    throw Error(`Expected one diagnostic ${service} container`);
  const container = JSON.parse(
    invoke(["container", "inspect", id], { encoding: "utf8" }),
  )[0];
  const labels = container.Config.Labels || {};
  if (
    labels["com.docker.compose.project"] !== "roadtrips-local" ||
    labels["com.docker.compose.service"] !== service ||
    container.Image !==
      inspect(
        `roadtrips-${service === "web" ? "web" : "api"}-local:${revision}`,
      ).Id ||
    (service === "web" && !container.State.Running) ||
    (service === "api" && !container.Config.Env.includes("LOCAL_PREVIEW=true"))
  )
    throw Error(
      `Refusing to alter an unverified diagnostic ${service} container`,
    );
}
const chromium =
  process.env.CHROMIUM_PATH ||
  ["/usr/bin/google-chrome", "/usr/bin/chromium"].find(existsSync);
if (!chromium)
  throw Error("Chromium is required for the trip-creation release gate");
// Cheap observer integrity preflight, before starting any journey fixture.
// Use the already revision-verified Python image with no network or app startup.
invoke(
  [
    "run",
    "--rm",
    "--network",
    "none",
    "--read-only",
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges:true",
    "--memory",
    "256m",
    "--pids-limit",
    "64",
    "--tmpfs",
    "/tmp:size=8m",
    "--mount",
    `type=bind,src=${join(root, "tests/guidedjourney")},dst=/journey,readonly`,
    testImage.Id,
    "python",
    "-m",
    "unittest",
    "discover",
    "-s",
    "/journey",
    "-p",
    "test_preparation_observer.py",
    "-q",
  ],
  { stdio: "inherit", timeout: 30000 },
);
try {
  // The diagnostic API intentionally blocks business routes. Replace only that
  // local preview process; leave the already-built real frontend running.
  docker([...preview, "stop", "api"]);
  docker([
    ...compose,
    "up",
    "--detach",
    "--wait",
    "--wait-timeout",
    "90",
    "postgres",
  ]);
  const inventory = invoke(
    [
      ...compose,
      "exec",
      "-T",
      "postgres",
      "psql",
      "-U",
      "postgres",
      "-d",
      "roadtrips",
      "-Atc",
      "SELECT count(*) FROM pg_tables WHERE schemaname='public'",
    ],
    { encoding: "utf8" },
  ).trim();
  if (inventory !== "0")
    throw Error(
      "Refusing schema initialization in a populated fixture database",
    );
  invoke(
    [
      ...compose,
      "exec",
      "-T",
      "postgres",
      "psql",
      "-U",
      "postgres",
      "-d",
      "roadtrips",
      "-v",
      "ON_ERROR_STOP=1",
    ],
    {
      input:
        readFileSync(join(root, "tests/postgres/schema.sql"), "utf8") +
        "\n" +
        readFileSync(join(root, "tests/postgres/catalog-fixture.sql"), "utf8") +
        "\nCREATE TABLE guided_journey_fixture_marker(marker text PRIMARY KEY);\nINSERT INTO guided_journey_fixture_marker VALUES ('disposable-local-only');\n",
      stdio: ["pipe", "inherit", "inherit"],
    },
  );
  docker([
    ...compose,
    "up",
    "--detach",
    "--wait",
    "--wait-timeout",
    "90",
    "api",
  ]);
  const apiId = invoke([...compose, "ps", "-q", "api"], {
    encoding: "utf8",
  }).trim();
  const runningApi = JSON.parse(
    invoke(["container", "inspect", apiId], { encoding: "utf8" }),
  )[0];
  if (
    runningApi.Image !== testImage.Id ||
    runningApi.Config.Labels?.["org.opencontainers.image.revision"] !== revision
  )
    throw Error(
      "Started journey API does not match the checked test image revision",
    );
  execFileSync(process.execPath, ["tests/guidedjourney/browser.mjs"], {
    cwd: root,
    stdio: "inherit",
    timeout: 180000,
    env: {
      PATH: process.env.PATH,
      CHROMIUM_PATH: chromium,
      GUIDED_JOURNEY_ARTIFACTS: artifacts,
      // Browser credentials are fixture constants; app/provider credentials are
      // never inherited by this process or supplied to the fixture stack.
    },
  });
} catch (error) {
  docker([...compose, "logs", "--no-color"]);
  throw error;
} finally {
  // tmpfs storage has no retained data, and the random project cannot match an
  // existing application. No production target or general prune is accepted.
  docker([...compose, "down", "--volumes"]);
}
