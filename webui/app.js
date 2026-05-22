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

// ── i18n ──
const I18N = {
  zh: {
    title: "🚗 ICBC 自动预约控制面板",
    tab_monitor: "监控",
    tab_config: "配置",
    status_running: "● 监控中",
    status_stopped: "● 已停止",
    status_lost: "● 连接失败",
    card_status: "状态",
    card_console: "实时输出",
    card_config: "配置",
    btn_start: "启动监控",
    btn_stop: "停止监控",
    btn_save: "保存配置",
    label_program: "程序状态:",
    label_running: "运行中",
    label_stopped: "已停止",
    label_booking: "预约状态:",
    label_last_run: "上次运行:",
    label_recent_log: "最近日志:",
    booking_none: "未预约",
    last_run_never: "从未",
    log_template: (e, w, n) => `${e} 错误 / ${w} 警告 / ${n} 次无名额`,
    log_none: "无日志",
    saved: (n) => `已保存 ${n} 项`,
    save_failed: (e) => `保存失败:${e}`,
    load_failed: (e) => `⚠️ 无法加载配置:${e}`,
    readiness_missing: (items) => `⚠️ 还需填写:${items.join("、")}`,
    readiness_ok: "✅ 必填项已完成",
    hint_close: "关闭面板程序会同时停止监控(仅关闭浏览器标签页不影响,服务仍在后台运行)。",
    fallback_unknown_option: (v) => `(当前: ${v} — 不在列表)`,
    lang_other_label: "EN",
  },
  en: {
    title: "🚗 ICBC Auto-Booking Control Panel",
    tab_monitor: "Monitor",
    tab_config: "Config",
    status_running: "● Running",
    status_stopped: "● Stopped",
    status_lost: "● Connection lost",
    card_status: "Status",
    card_console: "Live output",
    card_config: "Configuration",
    btn_start: "Start monitor",
    btn_stop: "Stop monitor",
    btn_save: "Save",
    label_program: "Program: ",
    label_running: "Running",
    label_stopped: "Stopped",
    label_booking: "Booking: ",
    label_last_run: "Last run: ",
    label_recent_log: "Recent log: ",
    booking_none: "Not booked",
    last_run_never: "Never",
    log_template: (e, w, n) => `${e} errors / ${w} warnings / ${n} empty checks`,
    log_none: "No log",
    saved: (n) => `Saved ${n} field${n === 1 ? "" : "s"}`,
    save_failed: (e) => `Save failed: ${e}`,
    load_failed: (e) => `⚠️ Cannot load config: ${e}`,
    readiness_missing: (items) => `⚠️ Still need to fill: ${items.join(", ")}`,
    readiness_ok: "✅ Required fields complete",
    hint_close: "Closing this program also stops a running monitor. Closing just the browser tab does not — the server keeps running.",
    fallback_unknown_option: (v) => `(current: ${v} — not in list)`,
    lang_other_label: "中",
  },
};

let LANG = (localStorage.getItem("ui-lang") === "en") ? "en" : "zh";
const t = (key, ...args) => {
  const v = I18N[LANG][key];
  return typeof v === "function" ? v(...args) : v;
};

function applyStaticI18n() {
  document.title = t("title");
  document.documentElement.lang = LANG === "en" ? "en" : "zh";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    if (I18N[LANG][key] !== undefined) el.textContent = t(key);
  });
  document.getElementById("lang-toggle").textContent = t("lang_other_label");
}

function setLang(lang) {
  LANG = lang;
  localStorage.setItem("ui-lang", lang);
  applyStaticI18n();
  // Re-render dynamic content for the new language.
  refreshStatus();
  loadConfig();
}

document.getElementById("lang-toggle").addEventListener("click", () => {
  setLang(LANG === "zh" ? "en" : "zh");
});

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
    ind.textContent = s.monitor_running ? t("status_running") : t("status_stopped");
    ind.className = "indicator " + (s.monitor_running ? "on" : "off");
    $("#status-body").innerHTML = renderStatus(s);
    $("#btn-start").disabled = !!s.monitor_running;
    $("#btn-stop").disabled = !s.monitor_running;
    const c = await getJSON("/api/console");
    const pre = $("#console");
    pre.textContent = c.lines.length ? c.lines.join("\n") : "—";
    pre.scrollTop = pre.scrollHeight;
  } catch (err) {
    const ind = $("#monitor-indicator");
    ind.textContent = t("status_lost");
    ind.className = "indicator off";
    $("#btn-start").disabled = true;
    $("#btn-stop").disabled = true;
  }
}
function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function renderStatus(s) {
  const running = s.monitor_running
    ? `<span class="status-on">● ${t("label_running")}</span>`
    : `<span class="status-off">● ${t("label_stopped")}</span>`;
  const booking = s.booking ? (s.booking.status || "unknown") : t("booking_none");
  const ls = s.log_summary;
  const log = ls ? t("log_template", ls.errors, ls.warnings, ls.no_appointments)
                 : t("log_none");
  return `${t("label_program")}${running}<br>`
       + `${t("label_booking")}${esc(booking)}<br>`
       + `${t("label_last_run")}${esc(s.last_run || t("last_run_never"))}<br>`
       + `${t("label_recent_log")}${log}`;
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
function fieldLabel(f) {
  return LANG === "en" ? (f.label_en || f.label) : f.label;
}
function fieldGroup(f) {
  return LANG === "en" ? (f.group_en || f.group) : f.group;
}
function fieldOptions(f) {
  return LANG === "en" ? (f.options_en || f.options) : f.options;
}

async function loadConfig() {
  try {
    const cfg = await getJSON("/api/config");
    const form = $("#config-form");
    form.innerHTML = "";
    const groups = {};
    cfg.fields.forEach((f) => {
      const g = fieldGroup(f);
      (groups[g] = groups[g] || []).push(f);
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
      ? t("readiness_missing", cfg.readiness)
      : t("readiness_ok");
  } catch (err) {
    $("#readiness").textContent = t("load_failed", err);
  }
}
function renderField(f) {
  const row = document.createElement("div");
  row.className = "field";
  const span = document.createElement("span");
  span.textContent = fieldLabel(f);
  row.appendChild(span);

  if (f.type === "multi_select") {
    const group = document.createElement("div");
    group.className = "multi-select";
    group.dataset.id = f.id;
    group.dataset.type = f.type;
    const selected = new Set((f.value || []).map(String));
    fieldOptions(f).forEach(([val, lbl]) => {
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

  if (f.type === "single_select") {
    const sel = document.createElement("select");
    sel.dataset.id = f.id;
    sel.dataset.type = f.type;
    const current = f.value == null ? "" : String(f.value);
    const opts = fieldOptions(f);
    const known = new Set(opts.map(([val]) => String(val)));
    if (current && !known.has(current)) {
      const opt = document.createElement("option");
      opt.value = current;
      opt.textContent = t("fallback_unknown_option", current);
      opt.selected = true;
      sel.appendChild(opt);
    }
    opts.forEach(([val, lbl]) => {
      const opt = document.createElement("option");
      opt.value = val;
      opt.textContent = lbl;
      if (String(val) === current) opt.selected = true;
      sel.appendChild(opt);
    });
    row.appendChild(sel);
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
    document.querySelectorAll(
      "#config-form input[data-id], #config-form select[data-id]"
    ).forEach((el) => {
      changes[el.dataset.id] =
        el.dataset.type === "bool" ? el.checked : el.value;
    });
    document.querySelectorAll("#config-form .multi-select").forEach((g) => {
      const picked = Array.from(g.querySelectorAll("input[type=checkbox]"))
        .filter((cb) => cb.checked)
        .map((cb) => cb.value);
      changes[g.dataset.id] = picked;
    });
    document.querySelectorAll("#config-form .time-range").forEach((g) => {
      const s = g.querySelector(".tr-start").value;
      const e = g.querySelector(".tr-end").value;
      changes[g.dataset.id] = (s && e) ? `${s}-${e}` : "";
    });
    const res = await postJSON("/api/config", changes);
    $("#save-msg").textContent = t("saved", res.applied.length);
    loadConfig();
  } catch (err) {
    $("#save-msg").textContent = t("save_failed", err);
  }
});

// ── 初始化 ──
applyStaticI18n();
switchTab("monitor");
loadConfig();
