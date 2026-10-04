import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

export function services(root, args = [], platform = process.platform) {
  const unknown = args.filter(
    (arg) => !["--debug", "--backend-only", "--frontend-only"].includes(arg),
  );
  if (
    unknown.length ||
    (args.includes("--backend-only") && args.includes("--frontend-only"))
  ) {
    throw new Error("Use --debug, --backend-only, or --frontend-only.");
  }
  const result = [];
  if (!args.includes("--frontend-only")) {
    const python = path.join(
      root,
      "backend",
      ".venv",
      platform === "win32" ? "Scripts/python.exe" : "bin/python",
    );
    if (!existsSync(python))
      throw new Error(
        "Create backend/.venv and install backend/requirements.txt first (see README.md).",
      );
    result.push({
      name: "Backend",
      command: python,
      args: [
        "-m",
        "uvicorn",
        "app.main:app",
        "--app-dir",
        "..",
        "--reload",
        "--reload-dir",
        ".",
      ],
      cwd: path.join(root, "backend", "app"),
      env: {
        ...process.env,
        ...(args.includes("--debug") ? { AGENT_DEBUG: "true" } : {}),
      },
    });
  }
  if (!args.includes("--backend-only")) {
    const vite = path.join(
      root,
      "frontend",
      "node_modules",
      "vite",
      "bin",
      "vite.js",
    );
    if (!existsSync(vite))
      throw new Error(
        "Install frontend dependencies first: cd frontend && npm ci",
      );
    result.push({
      name: "Frontend",
      command: process.execPath,
      args: [vite, "--port", "5173", "--strictPort"],
      cwd: path.join(root, "frontend"),
      env: process.env,
    });
  }
  return result;
}

async function stopTree(child) {
  if (!child.pid) return;
  if (process.platform === "win32") {
    await new Promise((resolve) => {
      const killer = spawn(
        "taskkill.exe",
        ["/PID", String(child.pid), "/T", "/F"],
        { stdio: "ignore" },
      );
      killer.once("error", resolve);
      killer.once("exit", resolve);
    });
  } else {
    try {
      process.kill(-child.pid, "SIGTERM");
    } catch (error) {
      if (error.code !== "ESRCH") throw error;
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch (error) {
      if (error.code !== "ESRCH") throw error;
    }
  }
}

// Keep both servers in one terminal and clean up only processes started here.
export async function runServices(
  definitions,
  { signals = process, stdio = "inherit" } = {},
) {
  const children = [];
  let stopping;
  let finish;
  const done = new Promise((resolve) => {
    finish = resolve;
  });
  const stop = (code) => {
    if (stopping) return stopping;
    stopping = Promise.all(children.map(stopTree)).then(() => finish(code));
    return stopping;
  };
  const interrupt = () => {
    void stop(0);
  };
  signals.on("SIGINT", interrupt);
  signals.on("SIGTERM", interrupt);
  try {
    for (const service of definitions) {
      const child = spawn(service.command, service.args, {
        cwd: service.cwd,
        env: service.env,
        stdio,
        detached: process.platform !== "win32",
      });
      children.push(child);
      child.once("error", (error) => {
        console.error(`${service.name} could not start: ${error.message}`);
        void stop(1);
      });
      child.once("exit", (code) => {
        if (!stopping) {
          console.error(`${service.name} stopped; shutting down both servers.`);
          void stop(code || 1);
        }
      });
    }
    return await done;
  } finally {
    signals.off("SIGINT", interrupt);
    signals.off("SIGTERM", interrupt);
  }
}

if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    const definitions = services(
      fileURLToPath(new URL("../", import.meta.url)),
      process.argv.slice(2),
    );
    console.log("Starting development servers. Press Ctrl+C to stop.");
    process.exitCode = await runServices(definitions);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
