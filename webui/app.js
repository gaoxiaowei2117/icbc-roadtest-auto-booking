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
  try {
    const s = await getJSON("/api/status");
    const ind = $("#monitor-indicator");
    ind.textContent = s.monitor_running ? "● 监控中" : "● 已停止";
    ind.className = "indicator " + (s.monitor_running ? "on" : "off");
    $("#status-body").innerHTML = renderStatus(s);
    const c = await getJSON("/api/console");
    const pre = $("#console");
    pre.textContent = c.lines.length ? c.lines.join("\n") : "—";
    pre.scrollTop = pre.scrollHeight;
  } catch (err) {
    const ind = $("#monitor-indicator");
    ind.textContent = "● 连接失败";
    ind.className = "indicator off";
  }
}
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function renderStatus(s) {
  const booking = s.booking ? (s.booking.status || "unknown") : "未预约";
  const ls = s.log_summary;
  const log = ls
    ? `${ls.errors} 错误 / ${ls.warnings} 警告 / ${ls.no_appointments} 次无名额`
    : "无日志";
  return `预约状态:${esc(booking)}<br>上次运行:${esc(s.last_run || "从未")}<br>最近日志:${log}`;
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
  try {
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
  } catch (err) {
    $("#readiness").textContent = "⚠️ 无法加载配置:" + err;
  }
}
function renderField(f) {
  const row = document.createElement("div");
  row.className = "field";
  const span = document.createElement("span");
  span.textContent = f.label;
  row.appendChild(span);

  if (f.type === "multi_select") {
    const group = document.createElement("div");
    group.className = "multi-select";
    group.dataset.id = f.id;
    group.dataset.type = f.type;
    const selected = new Set((f.value || []).map(String));
    (f.options || []).forEach(([val, lbl]) => {
      const item = document.createElement("label");
      item.className = "ms-item";
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = val;
      cb.checked = selected.has(String(val));
      item.appendChild(cb);
      item.appendChild(document.createTextNode(lbl));
      group.appendChild(item);
    });
    row.appendChild(group);
    return row;
  }

  if (f.type === "time_range") {
    const wrap = document.createElement("div");
    wrap.className = "time-range";
    wrap.dataset.id = f.id;
    wrap.dataset.type = f.type;
    let start = "", end = "";
    if (f.value) {
      const first = String(f.value).split(",")[0].trim();
      const m = first.match(/^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$/);
      if (m) {
        start = m[1].padStart(2, "0") + ":" + m[2];
        end = m[3].padStart(2, "0") + ":" + m[4];
      }
    }
    const s = document.createElement("input");
    s.type = "time"; s.value = start; s.className = "tr-start";
    const dash = document.createElement("span");
    dash.className = "tr-sep";
    dash.textContent = "—";
    const e = document.createElement("input");
    e.type = "time"; e.value = end; e.className = "tr-end";
    wrap.appendChild(s);
    wrap.appendChild(dash);
    wrap.appendChild(e);
    row.appendChild(wrap);
    return row;
  }

  const input = document.createElement("input");
  if (f.type === "bool") {
    input.type = "checkbox";
    input.checked = !!f.value;
  } else if (f.type === "date") {
    input.type = "date";
    input.value = f.value == null ? "" : f.value;
  } else {
    input.type = "text";
    input.value = f.value == null ? "" : f.value;
  }
  input.dataset.id = f.id;
  input.dataset.type = f.type;
  row.appendChild(input);
  return row;
}
$("#btn-save").addEventListener("click", async () => {
  try {
    const changes = {};
    // 单值字段(text / date / int / bool):dataset.id 直接挂在 input 上
    document.querySelectorAll("#config-form input[data-id]").forEach((i) => {
      changes[i.dataset.id] =
        i.dataset.type === "bool" ? i.checked : i.value;
    });
    // 多选字段:dataset.id 挂在容器上,值收集勾选项
    document.querySelectorAll("#config-form .multi-select").forEach((g) => {
      const picked = Array.from(g.querySelectorAll("input[type=checkbox]"))
        .filter((cb) => cb.checked)
        .map((cb) => cb.value);
      changes[g.dataset.id] = picked;
    });
    // 时间范围字段:拼成 "HH:MM-HH:MM";若两端任一为空,存空串
    document.querySelectorAll("#config-form .time-range").forEach((g) => {
      const s = g.querySelector(".tr-start").value;
      const e = g.querySelector(".tr-end").value;
      changes[g.dataset.id] = (s && e) ? `${s}-${e}` : "";
    });
    const res = await postJSON("/api/config", changes);
    $("#save-msg").textContent = `已保存 ${res.applied.length} 项`;
    loadConfig();
  } catch (err) {
    $("#save-msg").textContent = "保存失败:" + err;
  }
});

// ── 初始化 ──
switchTab("monitor");
loadConfig();
