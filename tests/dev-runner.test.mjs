import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import {
  mkdtempSync,
  mkdirSync,
  writeFileSync,
  readFileSync,
  existsSync,
  rmSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import test from "node:test";
import { services, runServices } from "../scripts/dev.mjs";

function fixture(t) {
  const root = mkdtempSync(path.join(os.tmpdir(), "roadtrips runner "));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return root;
}

test("Windows paths, debug environment and individual services", (t) => {
  const root = fixture(t);
  for (const name of [
    "backend/.venv/Scripts/python.exe",
    "frontend/node_modules/vite/bin/vite.js",
  ]) {
    const filename = path.join(root, name);
    mkdirSync(path.dirname(filename), { recursive: true });
    writeFileSync(filename, "");
  }
  const definitions = services(root, ["--debug"], "win32");
  assert.equal(definitions.length, 2);
  assert.equal(
    definitions[0].command,
    path.join(root, "backend/.venv/Scripts/python.exe"),
  );
  assert.equal(definitions[0].env.AGENT_DEBUG, "true");
  assert.ok(definitions[1].args.includes("--strictPort"));
  assert.equal(services(root, ["--frontend-only"], "win32").length, 1);
  assert.equal(services(root, ["--backend-only"], "win32").length, 1);
  assert.throws(() => services(root, ["--invalid"]), /Use --debug/);
});

test("missing prerequisites fail before starting either server", (t) => {
  assert.throws(() => services(fixture(t), [], "win32"), /Create backend/);
  assert.throws(() => services(fixture(t), ["--frontend-only"]), /npm ci/);
});

for (const reason of ["SIGINT", "exit", "spawn failure"]) {
  test(`${reason} stops the sibling process`, { timeout: 15000 }, async (t) => {
    const root = fixture(t);
    const pidFile = path.join(root, "child.pid");
    const childFile = path.join(root, "child.mjs");
    writeFileSync(
      childFile,
      `import {writeFileSync} from 'node:fs'; writeFileSync(process.argv[2], String(process.pid)); setInterval(()=>{},1000);`,
    );
    const signals = new EventEmitter();
    const definitions = [
      {
        name: "Sibling",
        command: process.execPath,
        args: [childFile, pidFile],
      },
    ];
    if (reason === "exit")
      definitions.push({
        name: "Failing server",
        command: process.execPath,
        args: ["-e", "setTimeout(()=>process.exit(7),1000)"],
      });
    if (reason === "spawn failure")
      definitions.push({
        name: "Missing server",
        command: path.join(root, "missing-executable"),
        args: [],
      });
    const running = runServices(definitions, { signals, stdio: "ignore" });
    if (reason === "SIGINT") {
      for (let attempt = 0; !existsSync(pidFile) && attempt < 100; attempt++)
        await delay(30);
      assert.ok(existsSync(pidFile), "sibling started");
      signals.emit("SIGINT");
    }
    assert.equal(
      await running,
      reason === "SIGINT" ? 0 : reason === "exit" ? 7 : 1,
    );
    if (existsSync(pidFile)) {
      const pid = Number(readFileSync(pidFile, "utf8"));
      assert.throws(() => process.kill(pid, 0), { code: "ESRCH" });
    }
    assert.equal(signals.listenerCount("SIGINT"), 0);
    assert.equal(signals.listenerCount("SIGTERM"), 0);
  });
}
