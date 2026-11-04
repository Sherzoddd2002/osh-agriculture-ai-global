#!/usr/bin/env node
import fs from "node:fs";
import fsp from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { pipeline } from "node:stream/promises";
import { Readable } from "node:stream";
import extractZip from "extract-zip";

const repo = "Sherzoddd2002/osh-agriculture-ai-global";
const sourceRef = process.env.OSH_AGRI_SOURCE_REF || "main";
const port = 8080;
const home = path.resolve(process.env.OSH_AGRI_HOME || (
  process.platform === "win32"
    ? path.join(process.env.LOCALAPPDATA || os.homedir(), "OSH", "AgricultureAI")
    : process.platform === "darwin"
      ? path.join(os.homedir(), "Library", "Application Support", "OSH", "AgricultureAI")
      : path.join(os.homedir(), ".local", "share", "osh-agriculture-ai-global")
));
const p = {
  source: path.join(home, "source"),
  runtime: path.join(home, "runtime"),
  app: path.join(home, "runtime", "app"),
  frontend: path.join(home, "runtime", "frontend"),
  env: path.join(home, "runtime", ".env"),
  venv: path.join(home, ".venv"),
  data: path.join(home, "data"),
  logs: path.join(home, "logs"),
  pid: path.join(home, "worker.pid"),
  serverPid: path.join(home, "web.pid")
};
const py = process.platform === "win32" ? path.join(p.venv, "Scripts", "python.exe") : path.join(p.venv, "bin", "python");
const args = process.argv.slice(2);
const command = args[0] || "help";
const noOpen = args.includes("--no-open");
function run(cmd, argv, cwd, inherit = true) {
  const r = spawnSync(cmd, argv, { cwd, stdio: inherit ? "inherit" : "pipe", windowsHide: true });
  if (r.error) throw r.error;
  if (r.status !== 0) throw new Error(`Command failed: ${cmd} ${argv.join(" ")} (exit ${r.status})`);
  return r;
}
async function pythonCommand() {
  const candidates = process.platform === "win32" ? [["py", ["-3"]], ["python", []]] : [["python3", []], ["python", []]];
  for (const [cmd, prefix] of candidates) {
    const r = spawnSync(cmd, [...prefix, "--version"], { encoding: "utf8", windowsHide: true });
    const m = (r.stdout + r.stderr).match(/Python (\d+)\.(\d+)/);
    if (m && (Number(m[1]) > 3 || (Number(m[1]) === 3 && Number(m[2]) >= 11))) return [cmd, prefix];
  }
  throw new Error("Python 3.11+ topilmadi. O‘rnating: https://www.python.org/downloads/");
}
async function downloadSource() {
  const tmp = await fsp.mkdtemp(path.join(os.tmpdir(), "osh-agri-"));
  try {
    const response = await fetch(`https://codeload.github.com/${repo}/zip/refs/heads/${sourceRef}`);
    if (!response.ok || !response.body) throw new Error(`GitHub download HTTP ${response.status}`);
    const zip = path.join(tmp, "repo.zip");
    await pipeline(Readable.fromWeb(response.body), fs.createWriteStream(zip));
    const unpack = path.join(tmp, "unpack");
    await fsp.mkdir(unpack);
    await extractZip(zip, { dir: unpack });
    const [folder] = await fsp.readdir(unpack);
    const root = path.join(unpack, folder);
    for (const file of ["requirements.txt", "backend/app/main.py", "frontend/index.html"]) {
      await fsp.access(path.join(root, file));
    }
    // Stage the extracted source on the same volume as the destination.
    // os.tmpdir() may be on C: while OSH_AGRI_HOME is on E:, and Windows
    // cannot rename directories across volumes (EXDEV).
    const sourceParent = path.dirname(p.source);
    await fsp.mkdir(sourceParent, { recursive: true });
    const stagedSource = path.join(
      sourceParent,
      `.osh-agri-source-${process.pid}-${crypto.randomBytes(6).toString("hex")}`
    );
    try {
      await fsp.cp(root, stagedSource, { recursive: true });
      await fsp.rm(p.source, { recursive: true, force: true });
      await fsp.rename(stagedSource, p.source);
    } finally {
      await fsp.rm(stagedSource, { recursive: true, force: true });
    }
  } finally {
    await fsp.rm(tmp, { recursive: true, force: true });
  }
}
async function syncRuntime() {
  await fsp.mkdir(p.runtime, { recursive: true });
  await fsp.rm(p.app, { recursive: true, force: true });
  await fsp.rm(p.frontend, { recursive: true, force: true });
  await fsp.cp(path.join(p.source, "backend", "app"), p.app, { recursive: true });
  await fsp.cp(path.join(p.source, "frontend"), p.frontend, { recursive: true });
}
async function configure() {
  await fsp.mkdir(p.data, { recursive: true });
  await fsp.mkdir(p.logs, { recursive: true });
  let envExists = true;
  try { await fsp.access(p.env); } catch { envExists = false; }
  if (!envExists) {
    const dbPath = path.join(p.data, "agriculture.sqlite3").replaceAll("\\", "/");
    const dbUrl = `sqlite:///${dbPath}`;
    const lines = [
      "APP_ENV=development",
      "APP_NAME=OSH Agriculture AI Global",
      `DATABASE_URL=${dbUrl}`,
      "ENABLE_POSTGIS=false",
      `JWT_SECRET=${crypto.randomBytes(48).toString("base64url")}`,
      "JWT_EXPIRE_MINUTES=10080",
      "CORS_ORIGINS=http://127.0.0.1:8080,http://localhost:8080",
      "MAX_UPLOAD_MB=25",
      "WORKER_POLL_SECONDS=3"
    ];
    await fsp.writeFile(p.env, lines.join("\n") + "\n", { flag: "wx" });
  }
  // Restrict the generated JWT secret on Unix-like systems.
  if (process.platform !== "win32") await fsp.chmod(p.env, 0o600);
}
async function preparePython(upgrade = false) {
  const [cmd, prefix] = await pythonCommand();
  if (!fs.existsSync(py)) run(cmd, [...prefix, "-m", "venv", p.venv], home);
  if (upgrade) run(py, ["-m", "pip", "install", "--upgrade", "pip"], p.source);
  run(py, ["-m", "pip", "install", "-r", path.join(p.source, "requirements.txt")], p.source);
}
async function initDb() {
  run(py, ["-m", "app.init_db"], p.runtime);
}
async function healthy() {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/api/v1/health`, { signal: AbortSignal.timeout(2000) });
    if (!r.ok) return false;
    const body = await r.json();
    return body.ok === true && body.service === "OSH Agriculture AI Global";
  } catch { return false; }
}
async function workerPid() {
  try { return Number(JSON.parse(await fsp.readFile(p.pid, "utf8")).pid); } catch { return null; }
}
async function pidAlive(pid) {
  if (!pid || !Number.isInteger(pid)) return false;
  try { process.kill(pid, 0); return true; } catch (e) { return e.code === "EPERM"; }
}
async function startWorker() {
  const old = await workerPid();
  if (old && await pidAlive(old)) {
    let cmdline = "";
    if (process.platform === "win32") {
      const r = spawnSync("powershell.exe", ["-NoProfile", "-Command", `(Get-CimInstance Win32_Process -Filter 'ProcessId = ${old}').CommandLine`], { encoding: "utf8" });
      cmdline = r.stdout || "";
    } else {
      const r = spawnSync("ps", ["-p", String(old), "-o", "args="], { encoding: "utf8" });
      cmdline = r.stdout || "";
    }
    if (cmdline.toLowerCase().includes("app.worker")) return;
    throw new Error("Worker PID boshqa jarayonga tegishli bo‘lishi mumkin; xavfsizlik uchun to‘xtatilmadi.");
  }
  const log = fs.openSync(path.join(p.logs, "worker.log"), "a");
  const child = spawn(py, ["-m", "app.worker"], { cwd: p.runtime, detached: true, stdio: ["ignore", log, log], windowsHide: true });
  fs.closeSync(log);
  child.unref();
  if (!child.pid) throw new Error("Worker ishga tushmadi.");
  await fsp.writeFile(p.pid, JSON.stringify({ pid: child.pid, command: "app.worker" }));
  console.log(`Worker ishga tushdi. PID: ${child.pid}`);
}
async function stopWorker() {
  const pid = await workerPid();
  if (!pid || !(await pidAlive(pid))) { await fsp.rm(p.pid, { force: true }); console.log("Worker ishlamayapti."); return; }
  let cmdline = "";
  if (process.platform === "win32") {
    const r = spawnSync("powershell.exe", ["-NoProfile", "-Command", `(Get-CimInstance Win32_Process -Filter 'ProcessId = ${pid}').CommandLine`], { encoding: "utf8" });
    cmdline = r.stdout || "";
  } else {
    const r = spawnSync("ps", ["-p", String(pid), "-o", "args="], { encoding: "utf8" });
    cmdline = r.stdout || "";
  }
  if (!cmdline.toLowerCase().includes("app.worker")) throw new Error("PID OSH worker ekanligi tasdiqlanmadi; jarayon to‘xtatilmadi.");
  if (process.platform === "win32") run("taskkill.exe", ["/PID", String(pid), "/T", "/F"], home);
  else process.kill(pid, "SIGTERM");
  await fsp.rm(p.pid, { force: true });
}
function openBrowser() {
  const url = `http://127.0.0.1:${port}`;
  if (noOpen) return;
  if (process.platform === "win32") spawn("cmd.exe", ["/c", "start", "", url], { detached: true, stdio: "ignore", windowsHide: true }).unref();
  else spawn(process.platform === "darwin" ? "open" : "xdg-open", [url], { detached: true, stdio: "ignore" }).unref();
}
async function processCommandLine(pid) {
  if (process.platform === "win32") {
    const r = spawnSync("powershell.exe", ["-NoProfile", "-Command", `(Get-CimInstance Win32_Process -Filter 'ProcessId = ${pid}').CommandLine`], { encoding: "utf8" });
    return r.stdout || "";
  }
  const r = spawnSync("ps", ["-p", String(pid), "-o", "args="], { encoding: "utf8" });
  return r.stdout || "";
}
async function stopServer() {
  let pid = null;
  try { pid = Number(JSON.parse(await fsp.readFile(p.serverPid, "utf8")).pid); } catch {}
  if (!pid || !(await pidAlive(pid))) {
    await fsp.rm(p.serverPid, { force: true });
    console.log("Web-server ishlamayapti.");
    return;
  }
  const cmdline = await processCommandLine(pid);
  if (!cmdline.toLowerCase().includes("uvicorn") || !cmdline.includes("app.main:app")) {
    throw new Error("Server PID OSH Agriculture web-server ekanligi tasdiqlanmadi; jarayon to‘xtatilmadi.");
  }
  if (process.platform === "win32") run("taskkill.exe", ["/PID", String(pid), "/T", "/F"], home);
  else process.kill(pid, "SIGTERM");

  const until = Date.now() + 10000;
  while (Date.now() < until && await pidAlive(pid)) await new Promise(r => setTimeout(r, 250));
  if (await pidAlive(pid)) throw new Error("Web-server to‘xtamadi; PID fayli saqlab qolindi.");
  await fsp.rm(p.serverPid, { force: true });
  console.log("Web-server to‘xtatildi.");
}
async function serve() {
  if (await healthy()) { console.log("Sayt allaqachon ishlayapti: http://127.0.0.1:8080"); openBrowser(); return; }
  const child = spawn(py, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)], { cwd: p.runtime, stdio: "inherit", windowsHide: false });
  if (!child.pid) throw new Error("Web-server process yaratilmadi.");
  await fsp.writeFile(p.serverPid, JSON.stringify({ pid: child.pid, command: "uvicorn app.main:app" }));

  let exited = false;
  let code = 0;
  const ended = new Promise(resolve => child.once("exit", async c => {
    exited = true;
    code = c ?? 1;
    await fsp.rm(p.serverPid, { force: true });
    resolve();
  }));
  const onSignal = () => {
    if (!child.killed) child.kill();
    stopWorker().catch(e => console.error("Worker stop:", e.message));
  };
  process.once("SIGINT", onSignal);
  process.once("SIGTERM", onSignal);

  const until = Date.now() + 90000;
  while (Date.now() < until && !exited && !(await healthy())) await new Promise(r => setTimeout(r, 1000));
  if (exited) {
    process.removeListener("SIGINT", onSignal);
    process.removeListener("SIGTERM", onSignal);
    throw new Error(`Web-server ishga tushmadi (exit ${code}).`);
  }
  if (!(await healthy())) {
    child.kill();
    process.removeListener("SIGINT", onSignal);
    process.removeListener("SIGTERM", onSignal);
    throw new Error("Health-check 90 soniyada javob bermadi.");
  }
  console.log("OSH Agriculture AI Global: http://127.0.0.1:8080");
  openBrowser();
  await ended;
  process.removeListener("SIGINT", onSignal);
  process.removeListener("SIGTERM", onSignal);
}
async function install() {
  if (fs.existsSync(p.source)) throw new Error("Loyiha allaqachon o‘rnatilgan. Yangilash uchun update buyrug‘idan foydalaning.");
  await fsp.mkdir(home, { recursive: true });
  await downloadSource(); await syncRuntime(); await configure();
  await preparePython(true); await initDb(); await startWorker(); await serve();
}
async function update() {
  if (!fs.existsSync(p.source)) throw new Error("Avval install buyrug‘ini bajaring.");
  await stopServer(); await stopWorker(); await downloadSource(); await syncRuntime(); await configure();
  await preparePython(false); await initDb(); await startWorker(); await serve();
}
async function status() {
  const web = await healthy();
  const pid = await workerPid();
  const worker = pid && await pidAlive(pid);
  console.log(`Web: ${web ? "RUNNING" : "STOPPED"}\nWorker: ${worker ? "RUNNING (PID " + pid + ")" : "STOPPED"}\nInstall: ${home}`);
}
async function runCentralScript(action) {
  if (process.platform !== "win32") {
    throw new Error("Central PostgreSQL host installer currently supports Windows PowerShell only.");
  }
  let script = path.join(p.source, "ops", `${action}-central.ps1`);
  if (!fs.existsSync(script)) {
    await downloadSource();
    script = path.join(p.source, "ops", `${action}-central.ps1`);
  }
  await fsp.access(script);
  const centralHome = path.join(home, "central-server");
  await fsp.mkdir(centralHome, { recursive: true });
  const result = spawnSync(
    "powershell.exe",
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
    {
      cwd: p.source,
      stdio: "inherit",
      windowsHide: false,
      env: { ...process.env, OSH_AGRI_CENTRAL_HOME: centralHome }
    }
  );
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`Central server command failed (exit ${result.status}).`);
}

async function main() {
  if (Number(process.versions.node.split(".")[0]) < 20) throw new Error("Node.js 20+ kerak.");
  if (args.includes("--help") || command === "help") {
    console.log("OSH Agriculture AI Global CLI\n\nLocal isolated mode (SQLite):\nnpx osh-agriculture-ai-global install\nnpx osh-agriculture-ai-global start\nnpx osh-agriculture-ai-global status\nnpx osh-agriculture-ai-global stop\nnpx osh-agriculture-ai-global update\n\nShared central server mode (Windows + existing PostgreSQL):\nnpx osh-agriculture-ai-global server-install\nnpx osh-agriculture-ai-global server-start\nnpx osh-agriculture-ai-global server-status\nnpx osh-agriculture-ai-global server-stop\nnpx osh-agriculture-ai-global server-update\n\nOptions: --no-open");
    return;
  }
  if (command === "install") await install();
  else if (command === "start") { if (!fs.existsSync(p.app)) throw new Error("Avval install buyrug‘ini bajaring."); await startWorker(); await serve(); }
  else if (command === "stop") { await stopServer(); await stopWorker(); }
  else if (command === "status") await status();
  else if (command === "update") await update();
  else if (command === "server-install" || command === "server-start") await runCentralScript("start");
  else if (command === "server-status") await runCentralScript("status");
  else if (command === "server-stop") await runCentralScript("stop");
  else if (command === "server-update") {
    await runCentralScript("stop");
    await fsp.rm(p.source, { recursive: true, force: true });
    await downloadSource();
    await runCentralScript("start");
  }
  else throw new Error("Noma’lum buyruq. --help ni ko‘ring.");
}
main().catch(e => { console.error("\nXATO: " + e.message); process.exitCode = 1; });
