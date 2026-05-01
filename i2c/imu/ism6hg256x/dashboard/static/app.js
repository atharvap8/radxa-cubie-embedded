/* ==============================================================
   Radxa Cubie A7A — Command Center  (app.js)
   Window manager + application modules
   ============================================================== */

(() => {
"use strict";

const desktop = document.getElementById("desktop");
const taskbarItems = document.getElementById("taskbar-items");
let winId = 0;
let zIdx = 10;
const wins = {};  // id -> { el, title, app, minimized, maximized, prev }

/* ---------- helpers ---------- */
const h = (tag, attrs, ...ch) => {
  const el = document.createElement(tag);
  if (attrs) Object.entries(attrs).forEach(([k,v]) => {
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v);
  });
  ch.forEach(c => { if (typeof c === "string") el.appendChild(document.createTextNode(c)); else if (c) el.appendChild(c); });
  return el;
};
const wsUrl = (path) => `ws://${location.host}${path}`;
const apiGet = (url) => fetch(url).then(r => r.json());

/* ================ WINDOW MANAGER ================ */

function createWindow(title, appClass, opts = {}) {
  const id = ++winId;
  const w = opts.width || 700, ht = opts.height || 480;
  const x = 40 + (id % 6) * 30, y = 30 + (id % 6) * 26;

  const el = h("div", { class: `window focused app-${appClass}`, "data-id": id });
  el.style.cssText = `left:${x}px;top:${y}px;width:${w}px;height:${ht}px;z-index:${++zIdx}`;

  // Header
  const header = h("div", { class: "win-header" });
  const dots = h("div", { class: "win-dots" });
  const btnClose = h("button", { class: "win-dot close", onclick: () => closeWin(id) }, "×");
  const btnMin   = h("button", { class: "win-dot minimize", onclick: () => minimizeWin(id) }, "−");
  const btnMax   = h("button", { class: "win-dot maximize", onclick: () => maximizeWin(id) }, "+");
  dots.append(btnClose, btnMin, btnMax);
  const titleEl = h("span", { class: "win-title" }, title);
  header.append(dots, titleEl);

  const body = h("div", { class: `win-body ${opts.padded ? "padded" : ""}` });
  const resize = h("div", { class: "win-resize" });
  el.append(header, body, resize);

  desktop.appendChild(el);

  const win = { id, el, body, title, app: appClass, minimized: false, maximized: false, prev: null, onClose: null, onResize: null };
  wins[id] = win;

  // Focus
  el.addEventListener("mousedown", () => focusWin(id));
  // Drag
  initDrag(header, el, win);
  // Resize
  initResize(resize, el, win);

  updateTaskbar();
  focusWin(id);
  return win;
}

function focusWin(id) {
  Object.values(wins).forEach(w => w.el.classList.remove("focused"));
  const w = wins[id];
  if (!w) return;
  w.el.classList.add("focused");
  w.el.style.zIndex = ++zIdx;
  updateTaskbar();
}

function closeWin(id) {
  const w = wins[id];
  if (!w) return;
  if (w.onClose) w.onClose();
  w.el.remove();
  delete wins[id];
  updateTaskbar();
}

function minimizeWin(id) {
  const w = wins[id];
  if (!w) return;
  w.minimized = true;
  w.el.classList.add("minimized");
  updateTaskbar();
}

function restoreWin(id) {
  const w = wins[id];
  if (!w) return;
  w.minimized = false;
  w.el.classList.remove("minimized");
  focusWin(id);
}

function maximizeWin(id) {
  const w = wins[id];
  if (!w) return;
  if (w.maximized) {
    w.maximized = false;
    w.el.classList.remove("maximized");
    if (w.prev) {
      w.el.style.left = w.prev.x + "px"; w.el.style.top = w.prev.y + "px";
      w.el.style.width = w.prev.w + "px"; w.el.style.height = w.prev.h + "px";
    }
  } else {
    w.prev = { x: w.el.offsetLeft, y: w.el.offsetTop, w: w.el.offsetWidth, h: w.el.offsetHeight };
    w.maximized = true;
    w.el.classList.add("maximized");
  }
  if (w.onResize) w.onResize();
}

function initDrag(handle, el, win) {
  let sx, sy, ox, oy;
  handle.addEventListener("mousedown", e => {
    if (e.target.classList.contains("win-dot")) return;
    if (win.maximized) return;
    sx = e.clientX; sy = e.clientY;
    ox = el.offsetLeft; oy = el.offsetTop;
    const move = e2 => { el.style.left = (ox + e2.clientX - sx) + "px"; el.style.top = (oy + e2.clientY - sy) + "px"; };
    const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  });
}

function initResize(handle, el, win) {
  handle.addEventListener("mousedown", e => {
    if (win.maximized) return;
    const sx = e.clientX, sy = e.clientY;
    const ow = el.offsetWidth, oh = el.offsetHeight;
    const move = e2 => {
      el.style.width = Math.max(320, ow + e2.clientX - sx) + "px";
      el.style.height = Math.max(200, oh + e2.clientY - sy) + "px";
      if (win.onResize) win.onResize();
    };
    const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
    e.preventDefault();
  });
}

function updateTaskbar() {
  taskbarItems.innerHTML = "";
  Object.values(wins).forEach(w => {
    const btn = h("div", {
      class: `tb-item ${!w.minimized && w.el.classList.contains("focused") ? "active" : ""}`,
      onclick: () => w.minimized ? restoreWin(w.id) : focusWin(w.id),
    }, w.title);
    taskbarItems.appendChild(btn);
  });
}

/* ================ APPS ================ */

/* ---- Terminal ---- */
function openTerminal() {
  const win = createWindow("Terminal", "terminal", { width: 780, height: 460 });
  const term = new Terminal({
    fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
    theme: { background: "#0d0d0d", foreground: "#e2e4ea", cursor: "#6c8aff", selectionBackground: "rgba(108,138,255,0.3)" },
    cursorBlink: true, scrollback: 5000,
  });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open(win.body);
  setTimeout(() => fit.fit(), 50);

  const ws = new WebSocket(wsUrl("/ws/terminal"));
  ws.onopen = () => {
    const dims = fit.proposeDimensions();
    if (dims) ws.send(`\x01RESIZE:${dims.cols},${dims.rows}`);
  };
  ws.onmessage = e => term.write(e.data);
  ws.onclose = () => term.write("\r\n\x1b[31m[session closed]\x1b[0m\r\n");
  term.onData(d => { if (ws.readyState === 1) ws.send(d); });

  win.onResize = () => { fit.fit(); const d = fit.proposeDimensions(); if (d && ws.readyState === 1) ws.send(`\x01RESIZE:${d.cols},${d.rows}`); };
  win.onClose = () => ws.close();
}

/* ---- File Browser ---- */
function openFiles() {
  const win = createWindow("Files", "files", { width: 650, height: 500 });
  let currentPath = "/home/radxa";

  const toolbar = h("div", { class: "fb-toolbar" });
  const pathInput = h("input", { class: "fb-path", value: currentPath });
  const goBtn = h("button", { class: "fb-btn", onclick: () => navigate(pathInput.value) }, "Go");
  const upBtn = h("button", { class: "fb-btn", onclick: () => navigate(currentPath + "/..") }, "Up");
  toolbar.append(upBtn, pathInput, goBtn);

  const listEl = h("div", { style: "flex:1;overflow:auto" });
  win.body.style.display = "flex";
  win.body.style.flexDirection = "column";
  win.body.append(toolbar, listEl);

  async function navigate(path) {
    const data = await apiGet(`/api/files?path=${encodeURIComponent(path)}`);
    if (data.error) { listEl.innerHTML = `<div style="padding:14px;color:var(--red)">${data.error}</div>`; return; }
    currentPath = data.path;
    pathInput.value = currentPath;
    listEl.innerHTML = "";
    const list = h("ul", { class: "fb-list" });
    data.entries.forEach(e => {
      const icon = e.dir ? "📁" : "📄";
      const size = e.dir ? "" : formatSize(e.size);
      const row = h("li", { class: "fb-entry", onclick: () => e.dir ? navigate(e.path) : previewFile(e.path) },
        h("span", { class: "fb-icon" }, icon),
        h("span", { class: "fb-name" }, e.name),
        h("span", { class: "fb-size" }, size),
      );
      list.appendChild(row);
    });
    listEl.appendChild(list);
  }

  async function previewFile(path) {
    const data = await apiGet(`/api/file-content?path=${encodeURIComponent(path)}`);
    if (data.error) return;
    const pw = createWindow(path.split("/").pop(), "files", { width: 600, height: 400 });
    pw.body.innerHTML = `<pre class="fb-preview">${escHtml(data.content)}</pre>`;
  }

  navigate(currentPath);
}

/* ---- GPIO Monitor ---- */
function openGpio() {
  const win = createWindow("GPIO Monitor", "gpio", { width: 560, height: 420, padded: false });
  let timer;

  async function refresh() {
    const data = await apiGet("/api/gpio");
    win.body.innerHTML = "";
    if (data.chips && data.chips.length) {
      data.chips.forEach(c => {
        win.body.appendChild(h("div", { class: "gpio-chip" },
          `${c.name}  label=${c.label || "?"}  base=${c.base || "?"}  ngpio=${c.ngpio || "?"}`));
      });
    }
    if (data.pins && data.pins.length) {
      const grid = h("div", { class: "gpio-grid" });
      data.pins.forEach(p => {
        const led = h("div", { class: `gpio-led ${p.val === 1 ? "high" : "low"}` });
        const label = `${p.name} ${p.dir || ""} ${p.val !== undefined && p.val !== null ? p.val : ""}`;
        grid.appendChild(h("div", { class: "gpio-pin" }, led, h("span", null, label)));
      });
      win.body.appendChild(grid);
    } else if (!data.pins || !data.pins.length) {
      win.body.appendChild(h("div", { class: "gpio-chip" }, "No GPIO pins currently exported. Use the Terminal to export pins via sysfs or gpioset."));
    }
  }

  refresh();
  timer = setInterval(refresh, 2000);
  win.onClose = () => clearInterval(timer);
}

/* ---- IMU Visualizer ---- */
function openImu() {
  const win = createWindow("IMU Visualizer", "imu", { width: 680, height: 520 });

  // Layout wrapper
  const wrapper = h("div", { class: "imu-wrapper" });

  // Control bar
  const controls = h("div", { class: "imu-controls" });
  const btnInit   = h("button", { class: "imu-ctrl-btn init",   onclick: doInit },   "Init");
  const btnDeinit = h("button", { class: "imu-ctrl-btn deinit", onclick: doDeinit }, "Deinit");
  const btnReset  = h("button", { class: "imu-ctrl-btn reset",  onclick: doReset },  "Reset Orientation");
  const statusEl  = h("span", { class: "imu-status" }, "Checking...");
  controls.append(btnInit, btnDeinit, btnReset, statusEl);

  // 3D scene container
  const sceneDiv = h("div", { class: "imu-scene" });
  const canvas = h("canvas", { class: "imu-canvas" });
  const overlay = h("div", { class: "imu-overlay" });
  const statR = h("div", { class: "imu-stat" }, "Roll: --");
  const statP = h("div", { class: "imu-stat" }, "Pitch: --");
  const statY = h("div", { class: "imu-stat" }, "Yaw: --");
  overlay.append(statR, statP, statY);
  sceneDiv.append(canvas, overlay);
  wrapper.append(controls, sceneDiv);
  win.body.appendChild(wrapper);

  // Three.js scene
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(50, 1.5, 0.1, 100);
  camera.position.set(0, 3, 6);
  camera.lookAt(0, 0, 0);
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setClearColor(0x0c0e14, 1);
  scene.add(new THREE.GridHelper(8, 16, 0x6c8aff, 0x222244));

  const geo = new THREE.BoxGeometry(1.6, 1.6, 1.6);
  const mats = [
    new THREE.MeshStandardMaterial({ color: 0xe63946 }),
    new THREE.MeshStandardMaterial({ color: 0x2ec4b6 }),
    new THREE.MeshStandardMaterial({ color: 0x6c8aff }),
    new THREE.MeshStandardMaterial({ color: 0xf4a261 }),
    new THREE.MeshStandardMaterial({ color: 0xa78bfa }),
    new THREE.MeshStandardMaterial({ color: 0x06d6a0 }),
  ];
  const cube = new THREE.Mesh(geo, mats);
  cube.position.y = 2;
  scene.add(cube);
  cube.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: 0x000000 })));
  scene.add(new THREE.AmbientLight(0xffffff, 0.5));
  const dl = new THREE.DirectionalLight(0xffffff, 0.8); dl.position.set(5, 8, 5); scene.add(dl);

  function resize() {
    const w = sceneDiv.clientWidth, ht = sceneDiv.clientHeight;
    if (w && ht) { camera.aspect = w / ht; camera.updateProjectionMatrix(); renderer.setSize(w, ht); }
  }
  setTimeout(resize, 60);
  win.onResize = resize;

  let running = true;
  function animate() { if (!running) return; requestAnimationFrame(animate); renderer.render(scene, camera); }
  animate();

  // IMU connection state
  let ws = null;

  function setStatus(text, ok) {
    statusEl.innerHTML = ok ? `<span class="online">${text}</span>` : `<span class="offline">${text}</span>`;
  }

  async function refreshStatus() {
    try {
      const d = await apiGet("/api/imu/status");
      if (!d.driver) { setStatus("Driver not found", false); return; }
      setStatus(d.active ? "Online (0x6A on i2c-7)" : "Idle", d.active);
    } catch { setStatus("Server unreachable", false); }
  }

  async function doInit() {
    const r = await fetch("/api/imu/init", { method: "POST" }).then(x => x.json());
    if (r.ok) { setStatus("Online (0x6A on i2c-7)", true); connectWs(); }
    else { setStatus(r.msg, false); }
  }

  async function doDeinit() {
    if (ws) { ws.close(); ws = null; }
    const r = await fetch("/api/imu/deinit", { method: "POST" }).then(x => x.json());
    setStatus("Idle", false);
  }

  async function doReset() {
    await fetch("/api/imu/reset", { method: "POST" });
  }

  function connectWs() {
    if (ws) { ws.close(); ws = null; }
    ws = new WebSocket(wsUrl("/ws/imu"));
    ws.onmessage = e => {
      const d = JSON.parse(e.data);
      if (d.error) { setStatus(d.error, false); return; }
      const deg = Math.PI / 180;
      cube.rotation.set(d.r * deg, d.y * deg, d.p * deg);
      statR.textContent = `Roll: ${d.r.toFixed(1)}`;
      statP.textContent = `Pitch: ${d.p.toFixed(1)}`;
      statY.textContent = `Yaw: ${d.y.toFixed(1)}`;
    };
    ws.onclose = () => { ws = null; };
  }

  // On open, check status and auto-connect if already initialised
  refreshStatus().then(() => {
    apiGet("/api/imu/status").then(d => { if (d.active) connectWs(); });
  });

  win.onClose = () => { running = false; if (ws) ws.close(); renderer.dispose(); };
}

/* ---- rsetup (board configuration) ---- */
function openRsetup() {
  const win = createWindow("rsetup", "terminal", { width: 820, height: 520 });
  const term = new Terminal({
    fontFamily: "'JetBrains Mono', monospace", fontSize: 13,
    theme: { background: "#0d0d0d", foreground: "#e2e4ea", cursor: "#6c8aff", selectionBackground: "rgba(108,138,255,0.3)" },
    cursorBlink: true, scrollback: 5000,
  });
  const fit = new FitAddon.FitAddon();
  term.loadAddon(fit);
  term.open(win.body);
  setTimeout(() => fit.fit(), 50);

  const ws = new WebSocket(wsUrl("/ws/terminal"));
  ws.onopen = () => {
    const dims = fit.proposeDimensions();
    if (dims) ws.send(`\x01RESIZE:${dims.cols},${dims.rows}`);
    setTimeout(() => ws.send("sudo rsetup\n"), 300);
  };
  ws.onmessage = e => term.write(e.data);
  ws.onclose = () => term.write("\r\n\x1b[31m[session closed]\x1b[0m\r\n");
  term.onData(d => { if (ws.readyState === 1) ws.send(d); });

  win.onResize = () => { fit.fit(); const d = fit.proposeDimensions(); if (d && ws.readyState === 1) ws.send(`\x01RESIZE:${d.cols},${d.rows}`); };
  win.onClose = () => ws.close();
}

/* ---- Debug Logger ---- */
function openLogger() {
  const win = createWindow("Debug Logger", "logger", { width: 700, height: 380 });
  const container = h("div", { class: "log-entries" });
  win.body.appendChild(container);

  const ws = new WebSocket(wsUrl("/ws/logs"));
  ws.onmessage = e => {
    const d = JSON.parse(e.data);
    const line = h("div", { class: "log-line" },
      h("span", { class: "log-time" }, d.time),
      h("span", { class: `log-lvl ${d.level}` }, d.level),
      h("span", { class: "log-msg" }, d.msg),
    );
    container.appendChild(line);
    container.scrollTop = container.scrollHeight;
  };
  win.onClose = () => ws.close();
}

/* ---- System Info ---- */
function openSysinfo() {
  const win = createWindow("System Info", "sysinfo", { width: 520, height: 340, padded: false });
  let timer;

  async function refresh() {
    const d = await apiGet("/api/sysinfo");
    const upH = Math.floor(d.uptime / 3600), upM = Math.floor((d.uptime % 3600) / 60);
    const memUsed = d.mem_total - d.mem_avail;
    win.body.innerHTML = "";
    const grid = h("div", { class: "si-grid" });
    const cards = [
      ["Hostname", d.hostname, ""],
      ["CPU Temp", d.cpu_temp !== null ? d.cpu_temp + " °C" : "N/A", ""],
      ["Memory", `${memUsed} / ${d.mem_total} MB`, `${Math.round(memUsed/d.mem_total*100)}% used`],
      ["Uptime", `${upH}h ${upM}m`, ""],
      ["Load (1/5/15)", d.load.join("  /  "), ""],
      ["IMU", d.imu ? "Available" : "Not found", ""],
    ];
    cards.forEach(([label, value, sub]) => {
      grid.appendChild(h("div", { class: "si-card" },
        h("div", { class: "si-label" }, label),
        h("div", { class: "si-value" }, String(value)),
        sub ? h("div", { class: "si-sub" }, sub) : null,
      ));
    });
    win.body.appendChild(grid);
  }

  refresh();
  timer = setInterval(refresh, 3000);
  win.onClose = () => clearInterval(timer);
}

/* ================ UTILITIES ================ */

function formatSize(bytes) {
  if (bytes == null) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

function escHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* ================ DOCK BINDINGS ================ */

const appMap = {
  terminal: openTerminal,
  files: openFiles,
  gpio: openGpio,
  imu: openImu,
  rsetup: openRsetup,
  logger: openLogger,
  sysinfo: openSysinfo,
};

document.querySelectorAll(".dock-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const app = btn.dataset.app;
    if (appMap[app]) appMap[app]();
  });
});

/* ================ TASKBAR CLOCK + SYSINFO ================ */

function updateClock() {
  const now = new Date();
  document.getElementById("tb-clock").textContent =
    now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
setInterval(updateClock, 1000);
updateClock();

async function updateTaskbarInfo() {
  try {
    const d = await apiGet("/api/sysinfo");
    document.getElementById("tb-cpu").textContent = d.cpu_temp !== null ? d.cpu_temp + " °C" : "-- °C";
    document.getElementById("tb-mem").textContent = (d.mem_total - d.mem_avail) + " / " + d.mem_total + " MB";
  } catch {}
}
setInterval(updateTaskbarInfo, 5000);
updateTaskbarInfo();

/* ---- auto-open terminal on load ---- */
openTerminal();

})();
