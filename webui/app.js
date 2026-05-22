const $ = (sel) => document.querySelector(sel);

async function getJSON(url) {
  const resp = await fetch(url);
  return resp.json();
}
async function postJSON(url, body) {
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  return resp.json();
}

// ── 标签切换 ──
let pollTimer = null;
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab.dataset.tab));
});
function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.tab === name));
  $("#tab-monitor").classList.toggle("hidden", name !== "monitor");
  $("#tab-config").classList.toggle("hidden", name !== "config");
  if (name === "monitor") startPolling();
  else stopPolling();
}

// ── 监控页轮询 ──
function startPolling() {
  if (pollTimer) return;
  refreshStatus();
  pollTimer = setInterval(refreshStatus, 2500);
}
function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}
async function refreshStatus() {
  const s = await getJSON("/api/status");
  const ind = $("#monitor-indicator");
  ind.textContent = s.monitor_running ? "● 监控中" : "● 已停止";
  ind.className = "indicator " + (s.monitor_running ? "on" : "off");
  $("#status-body").innerHTML = renderStatus(s);
  const c = await getJSON("/api/console");
  const pre = $("#console");
  pre.textContent = c.lines.length ? c.lines.join("\n") : "—";
  pre.scrollTop = pre.scrollHeight;
}
function renderStatus(s) {
  const booking = s.booking ? (s.booking.status || "unknown") : "未预约";
  const ls = s.log_summary;
  const log = ls
    ? `${ls.errors} 错误 / ${ls.warnings} 警告 / ${ls.no_appointments} 次无名额`
    : "无日志";
  return `预约状态:${booking}<br>上次运行:${s.last_run || "从未"}<br>最近日志:${log}`;
}

// ── 启动 / 停止 ──
$("#btn-start").addEventListener("click", async () => {
  await postJSON("/api/monitor/start");
  refreshStatus();
});
$("#btn-stop").addEventListener("click", async () => {
  await postJSON("/api/monitor/stop");
  refreshStatus();
});

// ── 配置表单 ──
async function loadConfig() {
  const cfg = await getJSON("/api/config");
  const form = $("#config-form");
  form.innerHTML = "";
  const groups = {};
  cfg.fields.forEach((f) => {
    (groups[f.group] = groups[f.group] || []).push(f);
  });
  Object.keys(groups).forEach((g) => {
    const fs = document.createElement("fieldset");
    const legend = document.createElement("legend");
    legend.textContent = g;
    fs.appendChild(legend);
    groups[g].forEach((f) => fs.appendChild(renderField(f)));
    form.appendChild(fs);
  });
  const r = $("#readiness");
  r.textContent = cfg.readiness.length
    ? "⚠️ 还需填写:" + cfg.readiness.join("、")
    : "✅ 必填项已完成";
}
function renderField(f) {
  const row = document.createElement("label");
  row.className = "field";
  const span = document.createElement("span");
  span.textContent = f.label;
  const input = document.createElement("input");
  if (f.type === "bool") {
    input.type = "checkbox";
    input.checked = !!f.value;
  } else {
    input.type = "text";
    input.value = f.value == null ? "" : f.value;
  }
  input.dataset.id = f.id;
  input.dataset.type = f.type;
  row.appendChild(span);
  row.appendChild(input);
  return row;
}
$("#btn-save").addEventListener("click", async () => {
  const changes = {};
  document.querySelectorAll("#config-form input").forEach((i) => {
    changes[i.dataset.id] =
      i.dataset.type === "bool" ? i.checked : i.value;
  });
  const res = await postJSON("/api/config", changes);
  $("#save-msg").textContent = `已保存 ${res.applied.length} 项`;
  loadConfig();
});

// ── 初始化 ──
switchTab("monitor");
loadConfig();
