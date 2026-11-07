// Launcher lifecycle only: fake foreground PG helpers, no application/SQL/DB.
import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import {
  mkdtemp,
  mkdir,
  writeFile,
  copyFile,
  readFile,
  chmod,
  rm,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const source = resolve(import.meta.dirname, "../..");
const marker = "roadtrips-native-preview-v1\n";
const delay = (ms) => new Promise((done) => setTimeout(done, ms));
async function until(check, message) {
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    const result = await check();
    if (result) return result;
    await delay(25);
  }
  throw Error(message);
}
async function fixture(mode = "starting", longPath = false) {
  const temporary = await mkdtemp(join(tmpdir(), "roadtrips-launcher-test-"));
  const root = longPath
    ? join(temporary, "x".repeat(100), "RoadtripsAreFun")
    : temporary;
  const state = join(root, ".artifacts/native-preview");
  for (const directory of [
    "scripts",
    "backend/.venv/bin",
    "frontend/node_modules/vite/bin",
    ".artifacts/native-preview/db",
    "tools",
  ])
    await mkdir(join(root, directory), { recursive: true, mode: 0o700 });
  await copyFile(
    join(source, "scripts/dev-offline.mjs"),
    join(root, "scripts/dev-offline.mjs"),
  );
  await copyFile(
    join(source, "scripts/dev.mjs"),
    join(root, "scripts/dev.mjs"),
  );
  // Presence only. These are never run: no helper reaches application startup.
  await writeFile(join(root, "backend/.venv/bin/python"), "unused");
  await writeFile(
    join(root, "frontend/node_modules/vite/bin/vite.js"),
    "unused",
  );
  await writeFile(join(state, "preview-owner"), marker, { mode: 0o600 });
  await writeFile(
    join(root, "tools/postgres"),
    `#!/usr/bin/env node
import {writeFileSync} from 'node:fs';
import {join} from 'node:path';
const data=process.argv[process.argv.indexOf('-D')+1];
writeFileSync(join(data,'launch-arguments.json'),JSON.stringify(process.argv.slice(2)),{mode:0o600});
if(${JSON.stringify(mode)}==='starting')writeFileSync(join(data,'postmaster.pid'),[process.pid,data,Math.floor(Date.now()/1000),6544,'','','','starting'].join('\\n')+'\\n',{mode:0o600});
setInterval(()=>{},1000);
`,
    { mode: 0o700 },
  );
  return { root, state, temporary };
}
function launcher(root) {
  const child = spawn(
    process.execPath,
    [join(root, "scripts/dev-offline.mjs")],
    {
      cwd: root,
      env: { PATH: process.env.PATH, PG_BIN: join(root, "tools") },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  let output = "";
  child.stdout.on("data", (chunk) => {
    output += chunk;
  });
  child.stderr.on("data", (chunk) => {
    output += chunk;
  });
  const exited = new Promise((done, reject) => {
    child.once("error", reject);
    child.once("exit", (code) => done(code));
  });
  return { child, exited, output: () => output };
}
async function waitExit(handle) {
  let timer;
  return await Promise.race([
    handle.exited,
    new Promise((_, reject) => {
      timer = setTimeout(
        () => reject(Error("Isolated launcher did not exit")),
        5000,
      );
    }),
  ]).finally(() => clearTimeout(timer));
}
async function stop(handle) {
  if (
    !handle ||
    handle.child.exitCode !== null ||
    handle.child.signalCode !== null
  )
    return;
  handle.child.kill("SIGTERM");
  let timer;
  await Promise.race([
    handle.exited,
    new Promise((_, reject) => {
      timer = setTimeout(
        () => reject(Error("Owned helper did not stop")),
        5000,
      );
    }),
  ]).finally(() => clearTimeout(timer));
}
const alive = (pid) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    if (error.code === "ESRCH") return false;
    throw error;
  }
};

test("second launcher cannot stop a first launcher after port reservations close", async () => {
  const { root, state } = await fixture();
  let first, helperPid;
  try {
    first = launcher(root);
    helperPid = await until(async () => {
      try {
        return Number(
          (await readFile(join(state, "db/postmaster.pid"), "utf8")).split(
            "\n",
          )[0],
        );
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
        return false;
      }
    }, "First launcher did not start its isolated foreground helper: " + first.output());
    const second = launcher(root);
    assert.equal(await waitExit(second), 1);
    assert.match(second.output(), /Preview lock exists/);
    assert.equal(alive(helperPid), true);
    assert.equal(first.child.exitCode, null);
    await stop(first);
    assert.equal(alive(helperPid), false);
    await assert.rejects(readFile(join(state, "launcher.lock")), {
      code: "ENOENT",
    });
  } finally {
    await stop(first);
    if (helperPid && alive(helperPid)) process.kill(-helperPid, "SIGKILL");
    await rm(root, { recursive: true, force: true });
  }
});

test("failed start never stops a different postmaster recorded in the same data path", async () => {
  const { root, state } = await fixture("foreign");
  const foreign = spawn(process.execPath, ["-e", "setInterval(()=>{},1000)"], {
    stdio: "ignore",
  });
  const foreignExit = new Promise((done) => foreign.once("exit", done));
  let run;
  try {
    await writeFile(
      join(state, "db/postmaster.pid"),
      [
        foreign.pid,
        join(state, "db"),
        Math.floor(Date.now() / 1000),
        6544,
        "",
        "",
        "",
        "ready",
      ].join("\n") + "\n",
      { mode: 0o600 },
    );
    run = launcher(root);
    assert.equal(await waitExit(run), 1);
    assert.match(run.output(), /not started by this invocation/);
    assert.equal(alive(foreign.pid), true);
    assert.equal(foreign.exitCode, null);
    await assert.rejects(readFile(join(state, "launcher.lock")), {
      code: "ENOENT",
    });
  } finally {
    await stop(run);
    foreign.kill("SIGTERM");
    await foreignExit;
    await rm(root, { recursive: true, force: true });
  }
});

test("group/other-writable artifact parents are refused before PG startup", async () => {
  const { root } = await fixture();
  try {
    await chmod(join(root, ".artifacts"), 0o777);
    const run = launcher(root);
    assert.equal(await waitExit(run), 1);
    assert.match(run.output(), /nonprivate preview state/);
    await assert.rejects(
      readFile(join(root, ".artifacts/native-preview/db/postmaster.pid")),
      { code: "ENOENT" },
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("long checkout paths disable Unix sockets and keep TCP loopback explicit", async () => {
  const { root, state, temporary } = await fixture("starting", true);
  let run;
  try {
    run = launcher(root);
    const args = await until(async () => {
      try {
        return JSON.parse(
          await readFile(join(state, "db/launch-arguments.json"), "utf8"),
        );
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
        return false;
      }
    }, "Long-path launcher did not start its foreground helper");
    assert.ok(root.length > 104);
    assert.equal(args[args.indexOf("-k") + 1], "");
    assert.equal(args[args.indexOf("-h") + 1], "127.0.0.1");
    assert.equal(args[args.indexOf("-p") + 1], "6544");
    await stop(run);
  } finally {
    await stop(run);
    await rm(temporary, { recursive: true, force: true });
  }
});
